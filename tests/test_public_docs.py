"""Python coverage for public roadmap data, static serving and source generation."""
import importlib.util,json,re,threading
from pathlib import Path
from html.parser import HTMLParser
import httpx,pytest

ROOT=Path(__file__).resolve().parents[1]


def test_hosting_configuration_uses_only_explicit_static_routes_without_node_builds():
    config=json.loads((ROOT/'docs/vercel.json').read_text(encoding='utf-8'))
    assert 'builds' not in config and config['framework'] is None
    assert config['buildCommand']==config['installCommand']==''
    assert config['outputDirectory']=='.'
    routes=config['routes'];assert routes[-1]=={'src':'/(.*)','status':404}
    public=tool('serve_docs')
    for name in public.FILES:
        matched=[route for route in routes[2:-1] if re.match(route['src'],'/'+name)]
        assert len(matched)==1,name
    for name in ['package.json','server.mjs','AGENTS.md','.git/config','tasks-data.mjs/private']:
        assert not any(re.match(route['src'],'/'+name) for route in routes[2:-1])
    assert routes[0]['headers']['Content-Security-Policy']==public.CSP
    assert routes[1]['status']==405 and routes[1]['headers']['Allow']=='GET, HEAD'


def tool(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


@pytest.fixture
def docs_server():
    module=tool('serve_docs');server=module.create_server();thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with httpx.Client(base_url='http://127.0.0.1:'+str(server.server_port),trust_env=False) as client:yield module,client
    finally:server.shutdown();server.server_close();thread.join(timeout=5)


@pytest.mark.parametrize('path',['/','/index.html','/documentation.html','/architecture.html','/organization.html','/how-it-works.html',
    '/integrations.html','/security.html','/roadmap.html','/tasks.html','/updates.html','/about.html','/site.css','/tasks-data.mjs',
    '/tasks-data.json','/tasks-page.js','/roadmap-status.js','/design/task-190-code-execution-threat-model.md'])
def test_public_static_routes_and_head_have_security_headers(docs_server,path):
    module,client=docs_server;response=client.get(path)
    assert response.status_code==200 and response.content
    assert response.headers['content-security-policy']==module.CSP
    assert response.headers['x-content-type-options']=='nosniff'
    head=client.head(path);assert head.status_code==200 and not head.content
    assert head.headers['content-length']==str(len(response.content))


@pytest.mark.parametrize('path',['/.git/config','/package.json','/../AGENTS.md','/%2e%2e/AGENTS.md','/server.mjs','/not-present','/C:/Windows/win.ini'])
def test_preview_rejects_nonpublic_files_and_path_traversal(docs_server,path):
    _,client=docs_server;assert client.get(path).status_code==404


@pytest.mark.parametrize('method',['POST','PUT','PATCH','DELETE','OPTIONS','TRACE'])
def test_public_docs_preview_never_accepts_mutations(docs_server,method):
    _,client=docs_server;response=client.request(method,'/')
    assert response.status_code==405 and response.headers['allow']=='GET, HEAD'


def test_generated_static_module_matches_single_json_authority_and_detects_staleness(tmp_path):
    generator=tool('generate_docs');generator.generate(check=True)
    (tmp_path/'docs').mkdir();data=generator.source();(tmp_path/'docs/tasks-data.json').write_text(json.dumps(data),encoding='utf-8')
    generator.generate(tmp_path);generator.generate(tmp_path,check=True)
    data['post100Tasks'][0]['title']='Changed authoritative source'
    (tmp_path/'docs/tasks-data.json').write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError,match='stale'):generator.generate(tmp_path,check=True)
    generator.generate(tmp_path);generator.generate(tmp_path,check=True)


def test_roadmap_records_dependencies_histories_and_verification_labels_are_truthful():
    data=tool('generate_docs').source();records=data['post100Tasks'];by_id={record['number']:record for record in records}
    assert len(records)==len(by_id) and len([task for group in data['foundationTaskGroups'] for task in group['tasks']])==100
    assert all(record['dependsOn'] or record['number']==179 or record.get('scopeDefined') is False for record in records)
    for record in records:
        assert all(1<=number<=100 or number in by_id for number in record['dependsOn'])
        assert record['number'] not in record['dependsOn'] and len(set(record['dependsOn']))==len(record['dependsOn'])
        if record['status'] in {'completed','design_only'}:
            assert re.fullmatch(r'(?:[a-f0-9]{7,40}|task-[1-9][0-9]*(?:-[a-z][a-z0-9-]*|[abc]))',record['checkpoint'])
            assert record['validation'] and record['limitations']
        for readiness in record.get('releaseReadiness',[]):
            assert readiness['source'] in {'Source-verified','Unverified'}
            assert readiness['packaged'] in {'Packaged-verified','Unverified'}
            assert readiness['realDevice'] in {'Real-device-verified','Unverified'}
    for number in [180,184]:assert len([record for record in records if record['number']==number])==1 and by_id[number]['history']
    assert by_id[197]['status']=='completed'
    for number in [204,205,206]:assert by_id[number]['status']=='not_done'
    for number in range(213,222):assert by_id[number]['status']=='superseded' and by_id[number]['supersededBy']==[223,224,225,226,227]
    assert 'not fixed' in json.dumps(by_id[194]).lower()


def test_public_local_links_exist_and_task_anchors_have_canonical_records():
    server=tool('serve_docs');source=tool('generate_docs').source();numbers=set(range(1,101))|{t['number'] for t in source['post100Tasks']}
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.links=[];self.ids=set()
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if 'id' in attrs:self.ids.add(attrs['id'])
            for key in ['href','src']:
                if attrs.get(key):self.links.append(attrs[key])
    pages={}
    for name in server.PAGES:
        parser=Links();parser.feed((ROOT/'docs'/name).read_text(encoding='utf-8'));pages[name]=parser
    for name,parser in pages.items():
        for link in parser.links:
            if re.match(r'^[a-z][a-z0-9+.-]*:',link,re.I):continue
            filename,_,anchor=link.partition('#');filename=filename or name
            assert (ROOT/'docs'/filename).is_file(),(name,link)
            if anchor:
                if filename=='tasks.html' and re.fullmatch(r'task-\d+',anchor):assert int(anchor[5:]) in numbers
                elif filename=='tasks.html' and anchor.startswith('tasks-'):continue
                else:assert anchor in pages[filename].ids,(name,link)
