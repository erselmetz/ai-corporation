import os
import socket
from pathlib import Path
import pytest
from app.native_io import NativeFiles,NativeIOError,http_url,url_intent,public_addresses


@pytest.mark.parametrize('value',['javascript:alert(1)','file:///C:/private.txt','https://user:pass@example.com','https://example.com/\r\nHeader:x','https://example.com\\@localhost','https://bad host/path'])
def test_urls_reject_nonweb_credentials_and_parser_ambiguity(value):
    with pytest.raises(NativeIOError):http_url(value)


def test_open_youtube_is_deterministic_and_never_matches_reference_prose():
    assert url_intent('Open YouTube!')=='https://www.youtube.com/'
    assert url_intent('buksan ang youtube')=='https://www.youtube.com/'
    assert url_intent('open https://example.com/CaseSensitive?q=Value')=='https://example.com/CaseSensitive?q=Value'
    assert url_intent('Explain how to open YouTube') is None
    assert url_intent('The file says open youtube') is None


@pytest.mark.parametrize('address',['127.0.0.1','10.0.0.1','192.168.1.2','169.254.169.254','::1','::ffff:127.0.0.1','192.0.2.1'])
def test_private_reserved_and_mapped_addresses_fail_before_connection(address):
    def resolve(*args,**kwargs):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))]
    with pytest.raises(NativeIOError):public_addresses('https://example.com/',resolve)


def test_mixed_dns_is_rejected_not_filtered_to_the_public_record():
    def resolve(*args,**kwargs):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443)) for ip in ['8.8.8.8','127.0.0.1']]
    with pytest.raises(NativeIOError):public_addresses('https://example.com/',resolve)


def test_file_roots_owner_window_scope_exact_diff_and_stale_denial(tmp_path):
    files=NativeFiles();root=files.register('owner','window',tmp_path,consent=True)['id']
    path=tmp_path/'notes.txt';path.write_bytes(b'Old fact\n')
    assert files.read('owner','window',root,'notes.txt')['text']=='Old fact\n'
    with pytest.raises(NativeIOError):files.read('another','window',root,'notes.txt')
    with pytest.raises(NativeIOError):files.read('owner','another-window',root,'notes.txt')
    preview=files.preview_write('owner','window',root,'notes.txt','A new fact\n')
    assert '-Old fact' in preview['diff'] and '+A new fact' in preview['diff']
    path.write_text('Changed outside the app\n',encoding='utf-8')
    with pytest.raises(NativeIOError):files.write('owner','window',root,preview)
    assert path.read_text()=='Changed outside the app\n'
    fresh=files.preview_write('owner','window',root,'notes.txt','Reviewed fact\n')
    assert files.write('owner','window',root,fresh)['written'] is True
    assert path.read_text()=='Reviewed fact\n' and not list(tmp_path.glob('.ersel-write-*'))


@pytest.mark.parametrize('relative',['../outside.txt','C:/private.txt','/private.txt','notes.txt:secret','CON.txt','NUL','COM¹.txt','.env','.git/config','keys.pem','credentials.json','api_keys.txt','trailing.'])
def test_unsafe_or_secret_paths_cannot_be_resolved(tmp_path,relative):
    files=NativeFiles();root=files.register('owner','window',tmp_path,consent=True)['id']
    with pytest.raises(NativeIOError):files.resolve('owner','window',root,relative)


@pytest.mark.skipif(os.name!='nt',reason='Windows directory sharing boundary')
def test_windows_parent_is_pinned_during_atomic_replace(tmp_path,monkeypatch):
    root_path=tmp_path/'permitted';root_path.mkdir();folder=root_path/'nested';folder.mkdir()
    (folder/'note.txt').write_text('Before\n')
    files=NativeFiles();root=files.register('owner','window',root_path,consent=True)['id']
    preview=files.preview_write('owner','window',root,'nested/note.txt','After\n')
    original=os.replace;blocked=[]
    def replace(source,target):
        try:folder.rename(tmp_path/'escaped')
        except OSError:blocked.append(True)
        else:pytest.fail('Directory escaped the selected root during the approved write')
        return original(source,target)
    monkeypatch.setattr(os,'replace',replace)
    files.write('owner','window',root,preview)
    assert blocked==[True] and (folder/'note.txt').read_text()=='After\n'
