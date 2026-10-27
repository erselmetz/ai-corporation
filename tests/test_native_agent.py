from copy import deepcopy
import pytest
from app.application.services.native_agent import NativeAgentService
from app.application.services.owned_chat import ChatConflict
from test_native_tools import tools


@pytest.fixture
def agent(tools,monkeypatch):
    service,app,actor,scope,policy,approvals,opened=tools
    app._native_tool_service=service
    monkeypatch.setattr('app.application.services.native_agent.build_chat_messages',
        lambda text,history,**kwargs:[{'role':'system','content':'Native test assistant'},*history,{'role':'user','content':text}])
    cid=app.owned_chat().start(actor.identity,'local_worker')['conversation'].id
    provider=app._orchestrator.providers.get('ollama')
    decisions=[];calls=[]
    def step(model,messages,catalog,**kwargs):
        calls.append(deepcopy(messages));return decisions.pop(0)
    monkeypatch.setattr(provider,'generate_native_step',step)
    return NativeAgentService(app),tools,cid,decisions,calls


def request_tool(name,args):
    return {'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':name,'arguments':args}}]},'thinking':''}


def test_agent_releases_model_slot_for_exact_review_and_saves_only_raw_history(agent):
    loop,(tools,app,actor,scope,policy,approvals,opened),cid,decisions,calls=agent
    text='Please open the public site'
    decisions.extend([request_tool('open_url',{'url':'https://example.com/'}),
                      {'message':{'role':'assistant','content':'Browser handoff was submitted.'},'thinking':''}])
    run=loop.start(actor,scope,cid,text,policy=policy,approvals=approvals)
    assert run['state']=='review' and opened==[] and run['steps']==1
    assert app.native_runtime().snapshot(actor.identity)['operations']==[]
    with pytest.raises(ChatConflict):app.owned_chat().delete(actor.identity,cid)
    run=loop.advance(actor,scope,run['id'],policy=policy,approvals=approvals,confirmed_digest=run['action']['approval_digest'])
    assert run['state']=='completed' and run['steps']==3 and opened==['https://example.com/']
    record=app.owned_chat().get(actor.identity,cid)['conversation']
    assert [m.role.value for m in record.messages]==['user','assistant']
    assert record.messages[0].content==text and 'Page loading was not verified' in record.messages[-1].content
    assert any(m['role']=='tool' for m in calls[-1])


def test_duplicate_tool_is_blocked_after_first_confirmed_execution(agent):
    loop,(tools,app,actor,scope,policy,approvals,opened),cid,decisions,calls=agent
    decisions.extend([request_tool('open_url',{'url':'https://example.com/'}),request_tool('open_url',{'url':'https://example.com/'})])
    run=loop.start(actor,scope,cid,'Open site once',policy=policy,approvals=approvals)
    run=loop.advance(actor,scope,run['id'],policy=policy,approvals=approvals,confirmed_digest=run['action']['approval_digest'])
    assert run['state']=='failed' and 'duplicate' in run['answer']
    assert opened==['https://example.com/'] and len(run['receipts'])==1
    assert app.owned_chat().get(actor.identity,cid)['conversation'].messages==()


def test_owner_denial_and_stop_resume_never_replay_pending_agent_actions(agent):
    loop,(tools,app,actor,scope,policy,approvals,opened),cid,decisions,calls=agent
    decisions.append(request_tool('open_url',{'url':'https://example.com/'}))
    run=loop.start(actor,scope,cid,'Open site',policy=policy,approvals=approvals)
    denied=loop.cancel(actor,scope,run['id'],approvals=approvals)
    assert denied['state']=='cancelled' and opened==[]
    decisions.append(request_tool('open_url',{'url':'https://example.com/'}))
    run=loop.start(actor,scope,cid,'New request',policy=policy,approvals=approvals)
    app.native_runtime().stop_window(actor.identity,scope.window_id);app.native_runtime().resume(actor.identity,scope.window_id)
    fresh=app.native_runtime().scope(actor.identity,scope.window_id)
    run=loop.advance(actor,fresh,run['id'],policy=policy,approvals=approvals,confirmed_digest=run['action']['approval_digest'])
    assert run['state']=='stopped' and opened==[]
    assert app.owned_chat().delete(actor.identity,cid) is not None


def test_step_limit_blocks_a_proposed_tool_before_any_side_effect(agent):
    loop,(tools,app,actor,scope,policy,approvals,opened),cid,decisions,calls=agent
    decisions.append(request_tool('open_url',{'url':'https://example.com/'}))
    run=loop.start(actor,scope,cid,'Open site',policy=policy,approvals=approvals,max_steps=1)
    assert run['state']=='failed' and run['steps']==1 and opened==[] and run['action'] is None


def test_auto_safe_exact_read_still_consumes_step_budget_and_returns_real_result(agent):
    loop,(tools,app,actor,scope,policy,approvals,opened),cid,decisions,calls=agent
    decisions.extend([request_tool('calculate',{'expression':'0.1+0.2'}),
                      {'message':{'role':'assistant','content':'The exact answer is 0.3.'},'thinking':''}])
    run=loop.start(actor,scope,cid,'Calculate this',policy=policy,approvals=approvals,ask_first=False)
    assert run['state']=='completed' and run['steps']==3 and opened==[]
    assert run['receipts'][0]['message']=='0.3'


def test_final_write_report_uses_receipts_instead_of_unconfirmed_model_actions(agent,tmp_path):
    loop,(tools,app,actor,scope,policy,approvals,opened),cid,decisions,calls=agent
    root=tools.files.register(actor.identity,scope.window_id,tmp_path,consent=True)['id']
    decisions.extend([request_tool('write_file',{'root_id':root,'path':'reviewed.txt','content':'Approved content'}),
        {'message':{'role':'assistant','content':'I wrote the file, opened YouTube and deleted the other files.'},'thinking':''}])
    run=loop.start(actor,scope,cid,'Write the reviewed file only',policy=policy,approvals=approvals)
    assert run['state']=='review'
    run=loop.advance(actor,scope,run['id'],policy=policy,approvals=approvals,confirmed_digest=run['action']['approval_digest'])
    assert run['state']=='completed' and (tmp_path/'reviewed.txt').read_text()=='Approved content'
    assert opened==[] and run['answer']=='File write confirmed: reviewed.txt'
    assert app.owned_chat().get(actor.identity,cid)['conversation'].messages[-1].content==run['answer']


def test_unverified_handoff_stops_before_any_further_model_or_tool_call(agent):
    loop,(tools,app,actor,scope,policy,approvals,opened),cid,decisions,calls=agent
    tools.browser_open=lambda url:False
    decisions.append(request_tool('open_url',{'url':'https://example.com/'}))
    run=loop.start(actor,scope,cid,'Open the site',policy=policy,approvals=approvals)
    run=loop.advance(actor,scope,run['id'],policy=policy,approvals=approvals,confirmed_digest=run['action']['approval_digest'])
    assert run['state']=='unverified' and run['steps']==2 and len(calls)==1 and not opened
    assert 'page loading is unknown' in run['answer']
