from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic,sleep
from app.runtime.factory import create_corporation_runtime
from app.resources.context import application_service,native_scope
from app.knowledge.providers import OllamaEmbeddingProvider
from app.knowledge.shipped_pack import ShippedPack


def test_shipped_pack_takes_model_admission_before_its_matrix_lock(tmp_path):
    class Embedding(OllamaEmbeddingProvider):
        def embed_batch(self,texts):return [(1.0,0.0) for _ in texts]
        def embed_one(self,text):return (1.0,0.0)
    service=create_corporation_runtime().application_service
    runtime=service.native_runtime();first=runtime.scope('owner',runtime.register('owner')['id'])
    second=runtime.scope('owner',runtime.register('owner')['id'])
    pack=ShippedPack(Embedding('fake-local-embedding'),tmp_path)
    occupied=Event();proceed=Event()
    def run(scope,owns_chat):
        service_token=application_service.set(service);scope_token=native_scope.set(scope)
        try:
            if owns_chat:
                with service.model_request('ollama','fake-chat'):
                    occupied.set();assert proceed.wait(5);return pack.retrieve('local query')
            return pack.retrieve('local query')
        finally:native_scope.reset(scope_token);application_service.reset(service_token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(run,first,True);assert occupied.wait(5)
        b=pool.submit(run,second,False)
        try:
            end=monotonic()+5
            while not any(o['window_id']==second.window_id and o['state']=='waiting' for o in runtime.snapshot('owner')['operations']):
                assert monotonic()<end;sleep(.01)
            acquired=pack.index.lock.acquire(blocking=False)
            if acquired:pack.index.lock.release()
            assert acquired,'A waiting pack request held its matrix lock ahead of model admission'
            proceed.set()
            assert a.result(timeout=5)['mode']=='semantic' and b.result(timeout=5)['mode']=='semantic'
        finally:
            proceed.set();runtime.stop_window('owner',second.window_id)
    assert runtime.snapshot('owner')['operations']==[]
