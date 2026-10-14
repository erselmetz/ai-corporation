import assert from "node:assert/strict";
import test from "node:test";
import { mountMemoryPage } from "../app/webui/static/memory.mjs";

class Element {
  constructor() { this.children=[]; this.text=""; this.value=""; this.listeners={}; this.disabled=false; this.checked=false; this.dataset={}; this.className=""; }
  get textContent() { return this.text + this.children.map(x=>x.textContent).join(""); }
  set textContent(value) { this.text=value; this.children=[]; }
  append(...items) { this.children.push(...items); }
  replaceChildren() { this.children=[]; this.text=""; }
  addEventListener(event, handler) { this.listeners[event]=handler; }
}
const item={id:"note",scope:"conversation",scope_id:"chat",type:"note",expires_at:"2026-10-03T00:00:00Z",expired:false,can_manage:true};
const record={...item,content:"canine <script>ignored</script>",revision:"a".repeat(64),source_id:"message",source_scope:"conversation",source_scope_id:"chat",source_reference:"message"};
const response=(status,data)=>({ok:status>=200&&status<300,status,json:async()=>data});
function setup(fetchImpl) {
  const ids=["memory-list","memory-state","memory-detail-state","memory-scope","memory-scope-id","memory-content","memory-expiry","memory-consent","memory-save","memory-remove","memory-refresh","semantic-memory-status","semantic-index","semantic-query","semantic-search","semantic-search-state","semantic-results","memory-map-root","memory-map-state","memory-relationship-list"];
  const elements=Object.fromEntries(ids.map(id=>[id,new Element()]));
  elements["memory-scope"].value="conversation"; elements["memory-scope-id"].value="chat";
  const controller=mountMemoryPage({documentRef:{getElementById:id=>elements[id],createElement:()=>new Element()},fetchImpl});
  return {controller,elements};
}

test("only explicitly selected owner records can be indexed and results preserve exact scope",async()=>{
  const calls=[];
  let currentRecord=record;
  const {controller,elements}=setup(async(path,options={})=>{
    calls.push({path,options});
    if(path==="/api/memory/semantic/status") return response(200,{state:"configured",model:"tiny-local",detail:"local only"});
    if(path==="/api/local/session") return response(200,{csrf:"csrf-token"});
    if(path==="/api/memory/record?scope=conversation&scope_id=chat&memory_id=note") return response(200,currentRecord);
    if(path==="/api/memory/semantic/index") return response(200,{indexed:true,memory_id:"note",chunk_count:1});
    if(path==="/api/memory/semantic/search") return response(200,{items:[{memory_id:"note",scope:"conversation",scope_id:"chat",revision:record.revision,expires_at:item.expires_at,source_reference:"message",chunk_position:0,relevance:0.8,excerpt:"<img src=x onerror=alert(1)>"}]});
    return response(200,{items:[item]});
  });
  await controller.refreshSemantic();
  assert.match(elements["semantic-memory-status"].textContent,/Configured locally/);
  await controller.load();
  await controller.select(item);
  assert.equal(elements["semantic-index"].disabled,false);
  assert.equal(await controller.indexSelected(),true);
  const indexCall=calls.find(call=>call.path==="/api/memory/semantic/index");
  assert.deepEqual(JSON.parse(indexCall.options.body),{scope:"conversation",scope_id:"chat",memory_id:"note"});
  assert.equal(indexCall.options.headers["X-Local-CSRF"],"csrf-token");
  elements["semantic-query"].value="dog";
  assert.equal(await controller.searchSemantic(),true);
  const searchCall=calls.find(call=>call.path==="/api/memory/semantic/search");
  assert.deepEqual(JSON.parse(searchCall.options.body),{query:"dog",scope:"conversation",scope_id:"chat",limit:5});
  assert.match(elements["semantic-results"].textContent,/onerror=alert/);
  assert.equal(elements["semantic-results"].children.length,1);
  assert.match(elements["memory-relationship-list"].textContent,/Semantic retrieval match/);
  assert.match(elements["memory-relationship-list"].textContent,/not rechecked since search/);
  const recheck=elements["memory-relationship-list"].children.flatMap(row=>row.children).find(child=>child.textContent==="Recheck source freshness");
  await recheck.listeners.click();
  assert.match(elements["memory-relationship-list"].textContent,/Source revision is current at recheck/);
  assert.ok(calls.some(call=>call.path==="/api/memory/record?scope=conversation&scope_id=chat&memory_id=note" && call.options.cache==="no-store"));
  currentRecord={...record,revision:"b".repeat(64)};
  const recheckChanged=elements["memory-relationship-list"].children.flatMap(row=>row.children).find(child=>child.textContent==="Recheck source freshness");
  await recheckChanged.listeners.click();
  assert.match(elements["memory-relationship-list"].textContent,/Source changed since retrieval/);
});

test("disabled capability and failed search clear stale results",async()=>{
  let enabled=false;
  const {controller,elements}=setup(async(path)=>{
    if(path==="/api/memory/semantic/status") return response(200,{state:enabled?"configured":"disabled",detail:"optional local capability"});
    if(path==="/api/local/session") return response(200,{csrf:"csrf"});
    if(path==="/api/memory/semantic/search") return response(503,{});
    return response(200,{items:[]});
  });
  await controller.refreshSemantic();
  assert.equal(elements["semantic-index"].disabled,true);
  assert.equal(elements["semantic-search"].disabled,true);
  enabled=true; await controller.refreshSemantic();
  await controller.load();
  elements["semantic-query"].value="dog";
  elements["semantic-results"].append(new Element());
  assert.equal(await controller.searchSemantic(),false);
  assert.equal(elements["semantic-results"].children.length,0);
  assert.match(elements["semantic-search-state"].textContent,/unavailable/);
  assert.doesNotMatch(elements["memory-relationship-list"].textContent,/Semantic retrieval match/);
});

test("scope changes discard pending results and never relabel a private search",async()=>{
  let finishSearch;
  const {controller,elements}=setup(async(path,options={})=>{
    if(path==="/api/memory/semantic/status") return response(200,{state:"configured",detail:"local"});
    if(path==="/api/local/session") return response(200,{csrf:"csrf"});
    if(path==="/api/memory/semantic/search") return new Promise(resolve=>{finishSearch=resolve;});
    return response(200,{items:[item]});
  });
  await controller.load(); await controller.refreshSemantic();
  elements["semantic-query"].value="private query";
  const pending=controller.searchSemantic();
  await new Promise(resolve=>setTimeout(resolve,0));
  elements["memory-scope-id"].value="another-conversation";
  elements["memory-scope-id"].listeners.input();
  finishSearch(response(200,{items:[{memory_id:"note",scope:"conversation",scope_id:"chat",revision:record.revision,expires_at:item.expires_at,source_reference:"message",chunk_position:0,relevance:0.8,excerpt:"private excerpt"}]}));
  assert.equal(await pending,false);
  assert.equal(elements["memory-relationship-list"].textContent,"");
  assert.doesNotMatch(elements["semantic-results"].textContent,/private excerpt/);
});
