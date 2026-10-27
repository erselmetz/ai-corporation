import json
from app.qt_desktop.failures import record_failure,MAX_BYTES,MAX_RECORDS


def test_local_records_whitelist_only_categories_and_bound_count(tmp_path):
    for _ in range(25):assert record_failure(tmp_path,stage='startup',error=ValueError('secret prompt and C:/private/path'))
    text=(tmp_path/'native-failures.json').read_text(encoding='utf-8');data=json.loads(text)
    assert len(data['records'])==MAX_RECORDS and len(text)<MAX_BYTES
    assert 'secret' not in text and 'path' not in text and 'prompt' not in text
    assert all(set(item)=={'at','stage','category'} and item['category']=='invalid_state' for item in data['records'])


def test_oversized_and_nonwhitelist_existing_records_fail_closed_without_overwrite(tmp_path):
    path=tmp_path/'native-failures.json'
    for original in ['x'*(MAX_BYTES+1),json.dumps({'version':1,'records':[{'message':'private'}]})]:
        path.write_text(original,encoding='utf-8')
        assert not record_failure(tmp_path,stage='ui',error=RuntimeError('private'))
        assert path.read_text(encoding='utf-8')==original
    assert not record_failure(tmp_path,stage='untrusted-stage',error=ValueError())


def test_unhandled_ui_error_requests_stop_without_logging_exception_or_replaying(tmp_path):
    from types import SimpleNamespace
    from app.qt_desktop.failures import ui_exception_handler
    stopped=[];messages=[]
    window=SimpleNamespace(closed=False,status=SimpleNamespace(setText=messages.append))
    manager=SimpleNamespace(windows=[window],stop_all=lambda:stopped.append(True))
    hook=ui_exception_handler(tmp_path,lambda:manager)
    hook(ValueError,ValueError('api_key=private C:/private/path'),None)
    assert stopped==[True] and len(messages)==1 and 'Stop was requested' in messages[0]
    payload=(tmp_path/'native-failures.json').read_text(encoding='utf-8')
    assert 'private' not in payload and 'api_key' not in payload
    assert json.loads(payload)['records'][0]['stage']=='ui'
