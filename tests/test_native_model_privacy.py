import json
from threading import Event
import httpx
import pytest
from app.providers.ollama import OllamaProvider
from app.resources.context import native_scope
from app.application.services.native_runtime import NativeScope


@pytest.mark.parametrize('metadata',[{},[],{'capabilities':['embedding']},
    {'capabilities':['completion'],'remote_host':'cloud.example'}])
def test_native_answer_requires_verified_local_completion_metadata(monkeypatch,metadata):
    provider=OllamaProvider('http://127.0.0.1:11434')
    monkeypatch.setattr(provider,'_bounded_request',lambda *a,**k:json.dumps(metadata).encode())
    token=native_scope.set(NativeScope('owner','window',0,Event(),Event()))
    try:
        with pytest.raises(ValueError):provider._prepare_answer_request('local-alias',{})
    finally:native_scope.reset(token)


def test_native_metadata_outage_fails_closed_instead_of_sending_private_prompt(monkeypatch):
    provider=OllamaProvider('http://127.0.0.1:11434')
    def unavailable(*args,**kwargs):raise httpx.ConnectError('daemon unavailable')
    monkeypatch.setattr(provider,'_bounded_request',unavailable)
    token=native_scope.set(NativeScope('owner','window',0,Event(),Event()))
    try:
        with pytest.raises(ValueError,match='no message was sent'):
            provider.generate_chat('local-alias',[{'role':'system','content':'Local assistant'},
                                                 {'role':'user','content':'private prompt'}])
    finally:native_scope.reset(token)


@pytest.mark.parametrize('enabled',[False,True])
def test_only_actual_leading_tagged_thinking_is_separated_from_answer(monkeypatch,enabled):
    provider=OllamaProvider('http://127.0.0.1:11434')
    monkeypatch.setattr(provider,'_prepare_answer_request',lambda *a:{'capabilities':['completion','tools']})
    monkeypatch.setattr(provider,'_bounded_request',lambda *a,**k:json.dumps({'done':True,'message':{
        'role':'assistant','content':'<think>Actual returned model text.</think>Final answer.'}}).encode())
    result=provider.generate_native_step('local',[{'role':'system','content':'Assistant'}, {'role':'user','content':'Question'}],
        [{'function':{'name':'calculate'}}],thinking=enabled)
    assert result['message']['content']=='Final answer.'
    assert result['thinking']==('Actual returned model text.' if enabled else '')


def test_native_named_thinking_without_default_uses_a_reported_level(monkeypatch):
    provider=OllamaProvider('http://127.0.0.1:11434');bodies=[]
    monkeypatch.setattr(provider,'_prepare_answer_request',lambda *a:{'capabilities':['completion','tools','thinking'],
                                                                 'thinking':{'values':['low','high']}})
    def response(method,path,body,**kwargs):
        bodies.append(body);return json.dumps({'done':True,'message':{'role':'assistant','content':'Answer'}}).encode()
    monkeypatch.setattr(provider,'_bounded_request',response)
    provider.generate_native_step('local',[{'role':'system','content':'Assistant'}, {'role':'user','content':'Question'}],
        [{'function':{'name':'calculate'}}],thinking=True)
    assert bodies[0]['think']=='low'
