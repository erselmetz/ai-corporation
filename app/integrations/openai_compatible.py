"""Opt-in text-only cloud endpoints. No router installation, fallback or retries."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager,nullcontext
from contextvars import ContextVar
import hashlib
import ipaddress
import json
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

import httpx

from app.chat_prompt import validate_chat_messages
from app.providers.base import AIProvider
from app.resources.context import check_native_stop

MAX_INPUT=32768
MAX_RESPONSE=524288
CONSENT_TEXT='Your prompt may be sent to any provider enabled in that router.'
_approval=ContextVar('compatible_cloud_approval',default=(False,None))
_receipt=ContextVar('compatible_cloud_receipt',default=None)
_identifier=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,255}$')
_secret=re.compile(r'(?i)\b(?:AIza[A-Za-z0-9_-]{35}|sk-[A-Za-z0-9_-]{12,}|gsk_[A-Za-z0-9_-]{12,}|hf_[A-Za-z0-9]{12,}|xox[baprs]-[A-Za-z0-9-]{12,}|(?:AKIA|ASIA)[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9_]{12,}|github_pat_[A-Za-z0-9_]{12,}|eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)|\bBearer\s+[^\s"\']+|(?<![A-Za-z0-9])(?:api[ _-]?key|password|secret|access[_-]?token)["\']?\s*[:=]\s*["\']?[^\s"\',;]+')
_private_key=re.compile(r'(?s)-----BEGIN [A-Z0-9 ]{0,32}PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]{0,32}PRIVATE KEY-----|\Z)')


class EndpointError(ValueError):
    def __init__(self,state,message):
        self.state=state
        super().__init__(message)


class OutboundPreview(Exception):
    def __init__(self,preview):self.preview=preview


@contextmanager
def approved_turn(consent=False,digest=None,metadata=None):
    token=_approval.set((consent is True,digest));trace=_receipt.set({} if metadata is None else metadata)
    try:yield
    finally:_approval.reset(token);_receipt.reset(trace)


def last_receipt():return _receipt.get()


def approval_matches(preview):
    consent,digest=_approval.get()
    return consent is True and digest==preview['digest']


def endpoint_url(value,*,remote_confirmed=False):
    try:
        if not isinstance(value,str) or len(value)>2048 or any(ord(c)<33 for c in value) or '\\' in value:raise ValueError()
        parsed=urlsplit(value);port=parsed.port
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:raise ValueError()
        if port is not None and not 1<=port<=65535:raise ValueError()
        host=parsed.hostname
        # Literal loopback and the reserved localhost name only; arbitrary DNS
        # names are never silently promoted to local based on a lookup.
        try:local=ipaddress.ip_address(host).is_loopback
        except ValueError:local=host=='localhost'
        if not local and (remote_confirmed is not True or parsed.scheme!='https'):
            raise EndpointError('confirmation_required','Non-loopback endpoints require explicit confirmation and HTTPS. Plain HTTP can expose prompts and keys.')
        if not parsed.path.rstrip('/').endswith('/v1'):raise ValueError()
        return value.rstrip('/')
    except EndpointError:raise
    except (ValueError,TypeError):raise EndpointError('invalid','Use an http(s) endpoint ending in /v1, without credentials, query or fragment.') from None


def redact(text,key=''):
    if key:text=text.replace(key,'[REDACTED]')
    return _secret.sub('[REDACTED]',_private_key.sub('[REDACTED PRIVATE KEY]',text))


class OpenAICompatibleProvider(AIProvider):
    is_local=False
    requires_explicit_cloud_consent=True
    requires_outbound_preview=True
    supports_streaming=True
    supports_image_input=False

    def __init__(self,base_url,api_key='',*,remote_confirmed=False,enabled=False,allow_brain_context=False,preset=False,transport=None):
        self.base_url=endpoint_url(base_url,remote_confirmed=remote_confirmed)
        if not isinstance(api_key,str) or len(api_key)>4096 or any(ord(c)<33 or ord(c)>126 for c in api_key):
            raise EndpointError('invalid','The API key contains unsupported characters.')
        self._key=api_key;self.enabled=enabled is True;self.allow_brain_context=allow_brain_context is True;self.preset=preset is True
        self._nonce=secrets.token_hex(32);self._lock=threading.RLock();self._calls=0;self.call_limit=5
        self._transport=transport;self.models=();self.state='Not tested';self.last_test=None;self.selected_model=None

    def __repr__(self):return '<OpenAICompatibleProvider cloud text-only>'

    def settings(self):
        return {'base_url':self.base_url,'enabled':self.enabled,'allow_brain_context':self.allow_brain_context,
                'experimental':self.preset,'default_model':'auto' if self.preset else self.selected_model,'state_label':self.state,
                'calls_used':self._calls,'calls_limit':self.call_limit,'cost':'Unknown; configure router/upstream billing limits separately.',
                'consent_text':CONSENT_TEXT,'supports_embeddings':False,'supports_images':False}

    def configure(self,enabled,allow_brain_context):
        with self._lock:
            self.enabled=enabled is True;self.allow_brain_context=allow_brain_context is True;self._nonce=secrets.token_hex(32)

    def erase(self):
        with self._lock:
            self._key='';self.enabled=False;self.models=();self._nonce=secrets.token_hex(32)

    def _headers(self):return {'Accept':'application/json','Authorization':'Bearer '+self._key} if self._key else {'Accept':'application/json'}

    def _client(self):return httpx.Client(transport=self._transport,trust_env=False,follow_redirects=False,timeout=httpx.Timeout(20,connect=5))

    def _check(self,response):
        status=response.status_code
        if status==401 or status==403:raise EndpointError('Key rejected','The endpoint rejected the key. Check its API access settings.')
        if status==429:raise EndpointError('Reachable','The endpoint is rate limited (429). Wait before choosing Retry; nothing was retried automatically.')
        if status>=500:raise EndpointError('Reachable','The endpoint is temporarily unavailable (5xx). Nothing was retried automatically.')
        if not 200<=status<300:raise EndpointError('Reachable','The endpoint rejected this request. Check its URL and supported model. Redirects are not followed.')

    def _read(self,response):
        data=bytearray()
        for part in response.iter_bytes():
            check_native_stop()
            if len(data)+len(part)>MAX_RESPONSE:raise EndpointError('Reachable','The endpoint response exceeded the safety limit.')
            data.extend(part)
        try:return json.loads(data)
        except (ValueError,UnicodeError):raise EndpointError('Reachable','The endpoint returned an unreadable response.') from None

    def list_models(self):
        check_native_stop()
        try:
            with self._client() as client,client.stream('GET',self.base_url+'/models',headers=self._headers()) as response:
                self._check(response);data=self._read(response)
            entries=data.get('data') if isinstance(data,dict) else None
            if not isinstance(entries,list) or len(entries)>1000:raise EndpointError('Reachable','The endpoint returned an invalid model catalog.')
            models=tuple(dict.fromkeys(item['id'] for item in entries if isinstance(item,dict) and isinstance(item.get('id'),str) and _identifier.fullmatch(item['id']) and redact(item['id'],self._key)==item['id']))[:100]
            self.models=models;self.state='Reachable' if models else 'No models'
            return models
        except httpx.TimeoutException:raise EndpointError('Not reachable','The endpoint timed out. Check that your separately installed router is running.') from None
        except httpx.HTTPError:raise EndpointError('Not reachable','The endpoint is not reachable. Check its address and start the router separately.') from None

    def supports_model_chat(self,model):return model in self.models or (self.preset and model=='auto')

    def preview_outbound(self,model,messages,*,brain=False):
        if not self.enabled:raise EndpointError('disabled','This cloud endpoint is off. Enable it explicitly in Providers.')
        if not _identifier.fullmatch(model) or not self.supports_model_chat(model):raise EndpointError('No models','Choose a model from a successful endpoint test.')
        if (brain or any('BEGIN UNTRUSTED RETRIEVED KNOWLEDGE' in str(m.get('content','')) for m in messages)) and not self.allow_brain_context:raise EndpointError('context_disabled','Allow Brain context is off for this provider.')
        messages=validate_chat_messages(messages)
        clean=[{'role':m['role'],'content':redact(m['content'],self._key)} for m in messages]
        encoded=json.dumps(clean,ensure_ascii=False,separators=(',',':')).encode()
        if len(encoded)>MAX_INPUT:raise EndpointError('input_too_large','This cloud prompt exceeds 32 KB. Start a shorter chat or reduce selected context.')
        digest=hashlib.sha256(self._nonce.encode()+model.encode()+encoded).hexdigest()
        return {'kind':'outbound_preview','digest':digest,'messages':clean,'requested_model':model,'destination':self.base_url,
                'warning':CONSENT_TEXT,'bytes':len(encoded),'redacted':clean!=messages}

    def _payload(self,model,messages,*,stream=False,testing=False):
        check_native_stop()
        if testing:
            clean=[{'role':'user','content':'Hi'}]
        else:
            preview=self.preview_outbound(model,messages)
            consent,digest=_approval.get()
            if consent is not True or digest!=preview['digest']:raise EndpointError('consent_required','Review the exact redacted outbound prompt and approve this cloud turn first.')
            clean=preview['messages']
        from app.agent_runtime import runtime_output_token_budget,check_runtime_step
        check_runtime_step()
        with self._lock:
            if self._calls>=self.call_limit:raise EndpointError('call_limit','The five-call endpoint allowance for this app run is exhausted. No request was sent.')
            self._calls+=1
        return {'model':model,'messages':clean,'stream':stream,'max_tokens':1 if testing else min(1024,runtime_output_token_budget())}

    def _record(self,response,started):
        via=response.headers.get('X-Routed-Via','') if response is not None else ''
        reported=via if _identifier.fullmatch(via) and '/' in via and redact(via,self._key)==via else None
        parts=reported.split('/',1) if reported else (None,None)
        receipt={'served_provider':parts[0],'served_model':parts[1],'routed_via':reported,
                 'latency_ms':round((time.perf_counter()-started)*1000,2),'retries':0,
                 'attribution':'Router-reported response header; unknown when absent.'}
        current=_receipt.get()
        if isinstance(current,dict):current.clear();current.update(receipt)
        return receipt

    def _completion(self,model,messages,*,testing=False):
        payload=self._payload(model,messages,testing=testing);started=time.perf_counter()
        self._record(None,started)
        try:
            with self._client() as client,client.stream('POST',self.base_url+'/chat/completions',headers=self._headers(),json=payload) as response:
                self._record(response,started)
                self._check(response);data=self._read(response);self._record(response,started)
            choices=data.get('choices') if isinstance(data,dict) else None
            message=choices[0].get('message') if isinstance(choices,list) and choices and isinstance(choices[0],dict) else None
            # No endpoint output is executable authority. Until a validated cloud
            # tool loop exists, tool proposals fail closed rather than executing.
            if isinstance(message,dict) and (message.get('tool_calls') or message.get('function_call')):raise EndpointError('tool_proposal','The endpoint proposed a tool. No tool ran; use the existing reviewed local tool workflow.')
            content=message.get('content') if isinstance(message,dict) else None
            # A valid one-token probe can exhaust its allowance on reasoning or
            # return an empty text token. This proves protocol reachability only,
            # never answer quality. Real user turns still require bounded text.
            if testing and isinstance(message,dict) and 'content' in message and (content is None or content==''):return ''
            if not isinstance(content,str) or not content.strip() or len(content.encode())>8192:raise EndpointError('Reachable','The endpoint returned no bounded text answer.')
            return redact(content,self._key)
        except httpx.TimeoutException:
            self._record(None,started)
            raise EndpointError('Not reachable','The endpoint timed out. No retry or alternate provider was used.') from None
        except httpx.HTTPError:
            self._record(None,started)
            raise EndpointError('Not reachable','The endpoint connection failed. No retry or alternate provider was used.') from None

    def test_connection(self,*,consent=False,reserve=None,model_id=None):
        if consent is not True:raise EndpointError('consent_required','Test sends the fixed text Hi with a one-token limit. Approve that cloud test first.')
        try:
            models=self.list_models()
            if not models:return {'state_label':'No models','models':[],'chat_test':False}
            model=model_id or ('auto' if self.preset else models[0])
            if model not in models and not (self.preset and model=='auto'):raise EndpointError('No models','Choose a model in the current catalog before testing it.')
            with (reserve(model) if reserve is not None else nullcontext()),approved_turn():
                self._completion(model,(),testing=True)
                self.last_test=dict(last_receipt() or {})
            self.state='Reachable'
            self.selected_model=model
            return {'state_label':self.state,'models':list(models),'chat_test':True,'receipt':self.last_test}
        except EndpointError as error:
            self.state=error.state if error.state in {'Not reachable','Reachable','Key rejected','No models'} else 'Reachable'
            return {'state_label':self.state,'models':list(self.models),'chat_test':False,'message':str(error)}

    def generate(self,model,prompt):
        from app.chat_prompt import build_chat_messages
        return self.generate_chat(model,build_chat_messages(prompt))
    def generate_chat(self,model,messages):return self._completion(model,messages)
    async def agenerate_chat(self,model,messages):return await asyncio.to_thread(self.generate_chat,model,messages)

    def generate_chat_stream(self,model,messages):
        payload=self._payload(model,messages,stream=True);started=time.perf_counter();total=0;finished=False;answer=''
        self._record(None,started)
        try:
            with self._client() as client,client.stream('POST',self.base_url+'/chat/completions',headers=self._headers(),json=payload) as response:
                self._record(response,started)
                self._check(response)
                for line in self._stream_lines(response,started):
                    from app.agent_runtime import check_runtime_step
                    check_runtime_step();total+=len(line.encode())
                    if total>MAX_RESPONSE or time.perf_counter()-started>20:raise EndpointError('Reachable','The stream exceeded its safety limit; no retry occurred.')
                    if not line.startswith('data:'):continue
                    raw=line[5:].strip()
                    if raw=='[DONE]':finished=True;break
                    try:
                        data=json.loads(raw);choice=data['choices'][0];delta=choice.get('delta',{})
                        if delta.get('tool_calls') or delta.get('function_call'):raise EndpointError('tool_proposal','The endpoint proposed a tool. No tool ran; use the reviewed local workflow.')
                        content=delta.get('content')
                        if content is not None and not isinstance(content,str):raise ValueError()
                    except EndpointError:raise
                    except (ValueError,KeyError,IndexError,TypeError):raise EndpointError('Reachable','The endpoint returned an unreadable stream.') from None
                    if content:
                        answer+=content
                        if len(answer.encode())>8192:raise EndpointError('Reachable','The streamed answer exceeded 8 KB.')
                self._record(response,started)
                if not finished:raise EndpointError('Reachable','The endpoint stream ended without completion. No retry occurred.')
                # Buffer the bounded SSE text so split secrets/tool proposals cannot
                # escape before validation. Expose only sanitized text chunks.
                answer=redact(answer,self._key)
                if not answer.strip():raise EndpointError('Reachable','The endpoint returned no text answer.')
                for offset in range(0,len(answer),512):yield answer[offset:offset+512]
        except httpx.TimeoutException:raise EndpointError('Not reachable','The endpoint stream timed out. No retry occurred.') from None
        except httpx.HTTPError:raise EndpointError('Not reachable','The endpoint stream disconnected. No retry occurred.') from None

    def _stream_lines(self,response,started):
        pending=b'';size=0
        for part in response.iter_bytes():
            from app.agent_runtime import check_runtime_step
            from app.resources.context import check_native_stop
            check_runtime_step();check_native_stop();size+=len(part)
            if size>MAX_RESPONSE or time.perf_counter()-started>20:raise EndpointError('Reachable','The endpoint stream exceeded its safety limit.')
            pending+=part
            while b'\n' in pending:
                line,pending=pending.split(b'\n',1)
                try:yield line.rstrip(b'\r').decode('utf-8')
                except UnicodeError:raise EndpointError('Reachable','The endpoint returned an unreadable stream.') from None
        if pending:
            try:yield pending.decode('utf-8')
            except UnicodeError:raise EndpointError('Reachable','The endpoint returned an unreadable stream.') from None

    async def agenerate_chat_stream(self,model,messages):
        # Context propagation and generator cleanup stay in the same worker.
        # A bounded response is collected before exposing async chunks.
        chunks=await asyncio.to_thread(lambda:list(self.generate_chat_stream(model,messages)))
        for chunk in chunks:yield chunk
