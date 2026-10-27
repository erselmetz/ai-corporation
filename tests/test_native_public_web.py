"""Public-web network boundaries without any external network requests."""
from email.message import Message
from io import BytesIO
import socket
import pytest
import app.native_io as native


def response(text=b'Public page',status=200,**headers):
    class Response(BytesIO):
        def getheader(self,name,default=None):return self.headers.get(name,default)
    result=Response(text);result.status=status;result.headers=Message()
    result.headers['Content-Type']='text/plain; charset=utf-8'
    for key,value in headers.items():
        name=key.replace('_','-')
        if name in result.headers:result.headers.replace_header(name,str(value))
        else:result.headers[name]=str(value)
    return result


def reader(monkeypatch,responses,*,peer='8.8.8.8',dns=None):
    calls=[];closed=[]
    class Socket:
        def getpeername(self):return (peer,443)
        def close(self):closed.append(True)
    class Connection:
        def __init__(self,host,port,timeout):self.sock=None;calls.append(('connection',host,port))
        def request(self,method,target,headers):calls.append(('request',method,target,headers))
        def getresponse(self):return responses.pop(0)
        def close(self):
            if self.sock:self.sock.close()
    class TLS:
        def wrap_socket(self,raw,server_hostname):calls.append(('tls',server_hostname));return raw
    def resolve(host,port,**kwargs):
        calls.append(('dns',host))
        return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(dns.get(host,'8.8.8.8') if dns else '8.8.8.8',port))]
    def dial(address,timeout):calls.append(('dial',address));return Socket()
    monkeypatch.setattr(native.http.client,'HTTPConnection',Connection)
    monkeypatch.setattr(native.ssl,'create_default_context',lambda:TLS())
    return native.PublicWebReader(resolver=resolve,dial=dial),calls,closed


def test_dns_is_pinned_and_tls_verifies_original_hostname(monkeypatch):
    web,calls,closed=reader(monkeypatch,[response(b'<script>untrusted action</script><p>Actual text</p>',Content_Type='text/html')])
    result=web.read('https://public.example/Case?q=Value')
    assert result['text']=='Actual text' and result['untrusted'] is True
    assert ('dial',('8.8.8.8',443)) in calls and ('tls','public.example') in calls
    request=next(c for c in calls if c[0]=='request')
    assert request[2]=='/Case?q=Value' and request[3]['Host']=='public.example'
    assert closed


def test_redirect_to_private_destination_is_rejected_before_second_connection(monkeypatch):
    web,calls,closed=reader(monkeypatch,[response(status=302,Location='http://private.example/secret')],dns={'private.example':'127.0.0.1'})
    with pytest.raises(native.NativeIOError,match='new exact destination approval'):web.read('https://public.example/')
    assert len([c for c in calls if c[0]=='dial'])==1 and closed
    assert ('dns','private.example') not in calls


def test_connected_peer_must_equal_validated_public_address(monkeypatch):
    web,calls,closed=reader(monkeypatch,[],peer='127.0.0.1')
    with pytest.raises(native.NativeIOError,match='approved public address'):web.read('https://public.example/')
    assert not any(c[0]=='request' for c in calls) and closed


@pytest.mark.parametrize('headers',[{'Content_Length':524289},{'Content_Encoding':'gzip'}, {'Content_Type':'application/octet-stream'}])
def test_unsupported_or_oversized_response_is_not_consumed(monkeypatch,headers):
    reply=response(b'Private or oversized content',**headers)
    web,calls,closed=reader(monkeypatch,[reply])
    with pytest.raises(native.NativeIOError):web.read('https://public.example/')
    assert reply.tell()==0 and closed


def test_stream_size_is_bounded_even_without_content_length(monkeypatch):
    web,calls,closed=reader(monkeypatch,[response(b'x'*524289)])
    with pytest.raises(native.NativeIOError,match='512 KB'):web.read('https://public.example/')
    assert closed
