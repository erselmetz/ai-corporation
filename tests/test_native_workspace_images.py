"""Per-window local vision selection preserves consent, scope and assignment."""
import base64
from test_chat_workspaces import Provider,Authentication
from test_chat_images import png
from app.runtime.factory import create_corporation_runtime
from app.api.app import create_app
from fastapi.testclient import TestClient


class VisionProvider(Provider):
    supports_image_input=True
    def __init__(self):super().__init__();self.images=[];self.vision=True
    def supports_model_image_input(self,model):return self.vision if model=='other:7b' else False
    def generate_chat_with_images(self,model,messages,images,**kwargs):
        self.images.append((model,messages,[image.id for image in images]));return 'Observed selected test image.'


def test_workspace_vision_needs_fresh_per_turn_consent_and_uses_its_own_model():
    runtime=create_corporation_runtime();runtime.providers.remove('ollama');provider=VisionProvider();runtime.providers.register('ollama',provider)
    with TestClient(create_app(application_service=runtime.application_service,authentication_backend=Authentication())) as client:
        headers={'x-test-owner':'alice','X-Chat-Workspace':'vision-window'}
        created=client.post('/api/chat/workspaces',headers={'x-test-owner':'alice'},json={
            'id':'vision-window','agent_id':'local_worker','provider_id':'ollama','model_id':'other:7b'})
        assert created.status_code==200,created.text
        cid=client.post('/api/chat/conversations',headers=headers,json={'agent_id':'local_worker'}).json()['conversation']['id']
        upload=client.post('/api/chat/conversations/'+cid+'/images',headers=headers,json={
            'media_type':'image/png','data_base64':base64.b64encode(png()).decode()})
        assert upload.status_code==200 and upload.json()['provider_transfer_supported'] is True
        iid=upload.json()['image']['id'];path='/api/chat/conversations/'+cid+'/messages'
        body={'text':'Describe the selected image','image_ids':[iid]}
        assert client.post(path,headers=headers,json=body).status_code==403 and provider.images==[]
        assert client.post(path,headers={**headers,'X-Chat-Workspace':'different-window'},json={**body,'image_consent':True}).status_code==404
        result=client.post(path,headers=headers,json={**body,'image_consent':True})
        assert result.status_code==200,result.text
        assert result.json()['image_transfer']['model_id']=='other:7b'
        assert provider.images[0][0]=='other:7b' and provider.images[0][2]==[iid]
        assert runtime.agents.get('local_worker').model=='llama3.2:3b'  # Fake route only; no installed model call.
        assert client.get('/api/chat/conversations/'+cid+'/images',headers=headers).json()['items']==[]
        history=client.get('/api/chat/conversations/'+cid,headers=headers).json()['conversation']['messages']
        assert [m['content'] for m in history]==['Describe the selected image','Observed selected test image.']
