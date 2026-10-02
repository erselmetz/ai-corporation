import assert from "node:assert/strict";
import test from "node:test";
import { mountMemoryPage } from "../app/webui/static/memory.mjs";
class Element {
  constructor() { this.children=[]; this.text=""; this.value=""; this.listeners={}; }
  get textContent() { return this.text + this.children.map(x=>x.textContent).join(""); }
  set textContent(value) { this.text=value; this.children=[]; }
  append(...items) { this.children.push(...items); }
  replaceChildren() { this.children=[]; this.text=""; }
  addEventListener(event, handler) { this.listeners[event]=handler; }
}
const item={id:"note",scope:"conversation",scope_id:"chat",type:"note",expires_at:"2026-10-03T00:00:00Z",expired:false,can_manage:true};
const record={...item,content:"<script>private</script>",revision:"a".repeat(64),source_id:"message",source_scope:"conversation",source_scope_id:"chat",source_reference:"message"};
const response=(status,data)=>({ok:status>=200&&status<300,status,json:async()=>data});
function setup(fetchImpl,confirmImpl=()=>true) {
  const elements=Object.fromEntries(["memory-list","memory-state","memory-detail-state","memory-scope","memory-scope-id","memory-content","memory-expiry","memory-consent","memory-save","memory-remove","memory-refresh"].map(id=>[id,new Element()]));
  elements["memory-scope"].value="conversation"; elements["memory-scope-id"].value="chat";
  const controller=mountMemoryPage({documentRef:{getElementById:id=>elements[id],createElement:()=>new Element()},fetchImpl,confirmImpl});
  return {controller,elements};
}
test("explicit scoped reads use session credentials and render text safely",async()=>{
  const calls=[];
  const {controller,elements}=setup(async(path,options)=>{calls.push({path,options});return response(200,path.includes('/record?')?record:{items:[item]});});
  assert.equal(calls.length,0);
  assert.equal(await controller.load(),true); assert.equal(await controller.select(item),true);
  assert.equal(calls[0].path,"/api/memory?scope=conversation&scope_id=chat&limit=50");
  assert.ok(calls.every(x=>x.options.credentials==="same-origin"));
  assert.equal(elements["memory-content"].value,record.content);
  assert.equal(elements["memory-content"].children.length,0);
  assert.equal(elements["memory-consent"].checked,false);
});
test("correction sends explicit consent and revision without owner spoofing",async()=>{
  let body;
  const {controller,elements}=setup(async(path,options)=>{
    if(options.method==="PUT") {body=JSON.parse(options.body);return response(200,record);}
    return response(200,path.includes('/record?')?record:{items:[item]});
  });
  await controller.select(item);elements["memory-content"].value="corrected";elements["memory-consent"].checked=true;
  assert.equal(await controller.save(),true);
  assert.deepEqual(body,{content:"corrected",expires_at:item.expires_at,retention_opt_in:true,revision:record.revision});
  assert.equal(elements["memory-content"].value,"");assert.equal(elements["memory-save"].disabled,true);
});
for (const [status,message] of [[401,"Sign-in"],[403,"Access denied"],[500,"failed"]]) {
  test(`read failure ${status} clears previous records`,async()=>{
    let statusCode=200;
    const {controller,elements}=setup(async()=>response(statusCode,{items:[item]}));
    await controller.load();statusCode=status;assert.equal(await controller.load(),false);
    assert.equal(elements["memory-list"].children.length,0);assert.match(elements["memory-state"].textContent,new RegExp(message));
  });
}
test("stale correction conflict clears cached content",async()=>{
  const {controller,elements}=setup(async(path,options)=>response(options.method==="PUT"?409:200,path.includes('/record?')?record:{items:[item]}));
  await controller.select(item);assert.equal(await controller.save(),false);
  assert.equal(elements["memory-content"].value,"");assert.match(elements["memory-detail-state"].textContent,/Reload/);
});
test("expired metadata never fetches content and requires confirmed owner deletion",async()=>{
  const calls=[];let confirmed=false;
  const {controller,elements}=setup(async(path,options)=>{calls.push(options.method??"GET");return response(options.method?204:200,{items:[]});},()=>confirmed);
  await controller.select({...item,expired:true});assert.equal(calls.length,0);assert.equal(elements["memory-content"].disabled,true);
  assert.equal(await controller.remove(),false);confirmed=true;assert.equal(await controller.remove(),true);
  assert.deepEqual(calls,["DELETE","GET"]);
});
test("named corporation reader cannot correct or withdraw",async()=>{
  const published={...record,scope:"corporation",scope_id:"corp",can_manage:false};let calls=0;
  const {controller,elements}=setup(async()=>{calls++;return response(200,published);});
  await controller.select(published);assert.equal(await controller.save(),false);assert.equal(await controller.remove(),false);
  assert.equal(calls,1);assert.equal(elements["memory-consent"].disabled,true);
});
test("changed scope rejects in-flight content",async()=>{
  let finish;
  const {controller,elements}=setup(()=>new Promise(resolve=>{finish=resolve;}));
  const pending=controller.select(item);elements["memory-scope-id"].value="other";elements["memory-scope-id"].listeners.input();
  finish(response(200,record));assert.equal(await pending,false);assert.equal(elements["memory-content"].value,"");
});
test("pending correction cannot be submitted twice",async()=>{
  let finish;let mutations=0;
  const {controller}=setup(async(path,options)=>{
    if(options.method==="PUT") {mutations++;return new Promise(resolve=>{finish=resolve;});}
    return response(200,path.includes('/record?')?record:{items:[item]});
  });
  await controller.select(item);const pending=controller.save();assert.equal(await controller.save(),false);
  finish(response(200,record));await pending;assert.equal(mutations,1);
});
