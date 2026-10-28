"""Small explicit native page/action catalog. Endpoints retain authorization."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Action:
    title: str
    method: str
    path: str
    dto: str = ''
    notice: str = 'Review the fields. This action uses the existing owner permission and validation checks.'
    defaults: tuple = ()

@dataclass(frozen=True)
class Page:
    endpoint: str
    actions: tuple = ()
    detail: str = ''

def A(title, method, path, dto='', notice='', **defaults):
    return Action(title,method,path,dto,notice or 'Review and confirm this exact action. No automatic retry.',tuple(defaults.items()))

CONNECTION='/api/local/provider-connections'
CLOUD='Your prompt may be sent to any provider enabled in that router. Test sends Hi with a one-token limit. No automatic fallback or retries.'
PAGES={
 'Employees':Page('/api/employees',(A('Create Employee','POST','/api/employees','models.EmployeeCreateRequest'),A('Remove Employee','DELETE','/api/employees/{id}')), '/api/employees/{id}'),
 'Positions':Page('/api/positions',(A('Create position','POST','/api/positions','models.PositionCreateRequest'),A('Edit position','PUT','/api/positions/{id}','models.PositionUpdateRequest'),A('Deactivate','POST','/api/positions/{id}/deactivate','models.PositionDeactivateRequest'),A('Remove position','DELETE','/api/positions/{id}')), '/api/positions/{id}'),
 'Projects':Page('/api/projects',(A('Create project','POST','/api/projects','models.ProjectCreateRequest'),),'/api/projects/{id}'),
 'Tasks':Page('/api/tasks',(A('Create Task','POST','/api/tasks','models.TaskCreateRequest'),A('Preview route','POST','/api/tasks/{id}/dry-run')), '/api/tasks/{id}'),
 'Workflows':Page('/api/local/workflows',(A('Pause','POST','/api/local/workflows/{id}/pause','workflows.ConfirmRequest'),A('Resume','POST','/api/local/workflows/{id}/resume','workflows.ConfirmRequest'),A('Cancel','POST','/api/local/workflows/{id}/cancel','workflows.ConfirmRequest'),A('Create workflow','POST','/api/local/workflows','workflows.WorkflowCreateRequest')), '/api/local/workflows/{id}'),
 'Workflow map':Page('/api/local/workflows/map'),
 'Structure':Page('/api/structure-map'),
 'Software inventory':Page('/api/local/inventory'),
 'Readiness':Page('/api/local/readiness'),
 'Preferences':Page('/api/local/preferences',(A('Edit response preferences','PUT','/api/local/preferences','local_preferences.PreferenceUpdate'),A('Reset preferences','POST','/api/local/preferences/reset'))),
 'Documentation':Page('/api/documentation',(),'/api/documentation/{id}'),
 'Agents':Page('/api/agents',(A('Edit profile','PUT','/api/agents/{id}/profile','agent_profiles.AgentProfileUpdate'),A('Pause or resume','PUT','/api/agents/{id}/pause','agent_profiles.AgentPauseUpdate'),A('Reset profile','POST','/api/agents/{id}/reset'),A('Duplicate Agent','POST','/api/agents/{id}/duplicate','agent_profiles.AgentDuplicateRequest')), '/api/agents/{id}/profile'),
 'Activity':Page('/api/activity'),
 'Session grants':Page('/api/capabilities/grants',(A('Grant scoped capability','POST','/api/capabilities/grants','capability_grants.GrantRequest'),A('Revoke grant','POST','/api/capabilities/grants/{id}/revoke'))),
 'Capability policy':Page('/api/capabilities/grants/policy',(A('Enable or disable capability','PUT','/api/capabilities/grants/policy/{id}','capability_grants.CapabilityEnableRequest'),)),
 'Approvals':Page('/api/capabilities/approvals',(A('Approve exact request','POST','/api/capabilities/approvals/{id}/approve','capability_approvals.ApprovalDecision'),A('Deny exact request','POST','/api/capabilities/approvals/{id}/deny','capability_approvals.ApprovalDecision')), '/api/capabilities/approvals/{id}'),
 'Providers':Page(CONNECTION,(
    A('Add local Ollama','POST',CONNECTION+'/ollama','provider_connections.OllamaConnectionRequest',base_url='http://127.0.0.1:11434',request_slots=1),
    A('Add OpenAI-compatible endpoint','POST',CONNECTION+'/openai-compatible','provider_connections.CompatibleRequest'),
    A('Add Free pool','POST',CONNECTION+'/openai-compatible','provider_connections.CompatibleRequest','1. Install FreeLLMAPI separately from its official release and verify the download. 2. Start it yourself. 3. Add here, Test explicitly, then enable. Optional, experimental, no SLA; personal experimentation only.',preset=True,name='Free pool',base_url='http://127.0.0.1:3001/v1'),
    A('Add Gemini','POST',CONNECTION+'/gemini','provider_connections.GeminiConnectionRequest','Contacts Google for model discovery. Credentials stay in memory.',request_slots=1),
    A('Test endpoint','POST',CONNECTION+'/{id}/test','provider_connections.CompatibleTest',CLOUD),
    A('Enable and Brain privacy','PATCH',CONNECTION+'/{id}/privacy','provider_connections.CompatiblePrivacy'),
    A('Refresh local or Gemini catalog','POST',CONNECTION+'/{id}/refresh'),
    A('Assign tested model','PUT',CONNECTION+'/assignment','provider_connections.ProviderAssignmentRequest'),
    A('Load local model','POST',CONNECTION+'/{id}/models/load','provider_connections.ModelOperationRequest'),
    A('Unload local model','POST',CONNECTION+'/{id}/models/unload','provider_connections.ModelOperationRequest'),
    A('Remove connection','DELETE',CONNECTION+'/{id}'))),
 'Online providers':Page('/api/local/online-provider',(
    A('Discover Gemini models','POST','/api/local/online-provider/catalog','local_online_provider.CatalogRequest','Contacts Google. Your key is never placed in the detail panel.'),
    A('Connect Gemini','PUT','/api/local/online-provider/connection','local_online_provider.ConnectRequest'),
    A('Erase Gemini credential','DELETE','/api/local/online-provider/credential'))),
 'Privacy and capabilities':Page('/api/capability-packs',(A('Install reviewed pack','POST','/api/capability-packs/{id}/install','capability_packs.PackInstall','Downloads only the previewed verified pack. Review source, total size and manifest digest before confirming.'),A('Self-test pack','POST','/api/capability-packs/{id}/self-test'))),
 'Brain settings':Page('/api/memory/owner/native-graph'),
 'Automation':Page('/api/local/automation',(A('Set exact browser origin allowlist','PUT','/api/local/automation/browser/origin','local_automation.OriginPolicyUpdate'),A('Set exact process allowlist','PUT','/api/local/automation/desktop/process','local_automation.ProcessPolicyUpdate'))),
 'Local speech':Page('/api/local/voice',(A('Select installed speech model','POST','/api/local/voice/local-model','local_voice.LocalSpeechModelRequest'),A('Preview speech model download','GET','/api/local/voice/local-model-preview'),A('Install reviewed speech model','POST','/api/local/voice/local-model-install','local_voice.LocalSpeechModelInstall','Downloads only the separately previewed pinned local speech model after explicit confirmation. No microphone is opened.'),A('Test local speech output','POST','/api/local/voice/test-output'),A('Stop speech output','POST','/api/local/voice/stop-output'))),
 'Brain embedding':Page('/api/memory/brain/embedding/status',(A('Preview local embedding model','GET','/api/memory/brain/embedding/preview'),A('Pull reviewed local embedding model','POST','/api/memory/brain/embedding/pull','memory.BrainEmbeddingPull','Review the exact manifest digest and byte count first. This explicit action downloads only the local embedding model.'),A('Test local embedding model','POST','/api/memory/brain/embedding/self-test'))),
 'Updates':Page('/api/updates',(A('Check trusted update','GET','/api/updates/release',notice='This explicit click checks the configured trusted release source. No automatic update checks.'),A('Prepare verified installer','POST','/api/updates/release/prepare','models.ReleasePrepareRequest','Downloads only the configured verified installer; does not run it. Review version and migration before confirming.'))),
 'Employee chat':Page('/api/employee-chat/conversations',(A('Start Employee conversation','POST','/api/employee-chat/conversations','employee_chat.StartRequest'),A('Send to selected Employee','POST','/api/employee-chat/conversations/{id}/messages','employee_chat.SendRequest','Review the assigned Employee/provider and context. Cloud consent is separate and off by default.')), '/api/employee-chat/conversations/{id}'),
}
PAGES['Sage Core']=Page('/api/local/agents/sage-core')
PAGES['Local models']=Page('/api/local/models/local_worker',(A('Select installed Coordinator model','PUT','/api/local/models/local_worker','local_models.SelectionRequest'),))
PAGES['Assignment recommendations']=Page('/api/local/assignment-policy',(A('Disable recommendations','DELETE','/api/local/assignment-policy'),))
PAGES['Provider connections']=PAGES['Providers']
