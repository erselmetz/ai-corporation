// Browser contract fixtures run by pytest/CDP, with no filesystem or Node runtime.
const cases = [];
function fail(message) { throw new Error(message || "Contract assertion failed"); }
function deep(a, b, seen = new WeakMap()) {
  if (Object.is(a,b)) return true;
  if (!a || !b || typeof a !== "object" || typeof b !== "object") return false;
  if (Object.getPrototypeOf(a) !== Object.getPrototypeOf(b)) return false;
  if (seen.get(a) === b) return true;
  seen.set(a,b);
  if (a instanceof Date) return a.getTime() === b.getTime();
  if (a instanceof RegExp) return a.toString() === b.toString();
  if (a instanceof Set) return a.size === b.size && [...a].every(value => [...b].some(other => deep(value,other,seen)));
  if (a instanceof Map) return a.size === b.size && [...a].every(([key,value]) => b.has(key) && deep(value,b.get(key),seen));
  const keys=Reflect.ownKeys(a), other=Reflect.ownKeys(b);
  return keys.length === other.length && keys.every(key => other.includes(key) && deep(a[key],b[key],seen));
}
export const assert = {
  equal(a,b,message) { if (!Object.is(a,b)) fail(message || `Expected ${String(a)} to equal ${String(b)}`); },
  deepEqual(a,b,message) { if (!deep(a,b)) fail(message || `Values differ: ${JSON.stringify(a)} / ${JSON.stringify(b)}`); },
  ok(value,message) { if (!value) fail(message); },
  match(value,pattern,message) { pattern.lastIndex=0; if (typeof value !== "string" || !pattern.test(value)) fail(message || `Pattern ${pattern} did not match ${String(value)}`); },
  doesNotMatch(value,pattern,message) { pattern.lastIndex=0; if (typeof value !== "string" || pattern.test(value)) fail(message || `Unexpected match ${pattern}`); },
  throws(fn,pattern) { let error; try { fn(); } catch (caught) { error=caught; } if (!error) fail("Expected an exception"); if (pattern) this.match(String(error.message),pattern); },
};
export function test(name,fn) { cases.push({name,fn}); }
export async function readFile(input,encoding) {
  if (encoding !== "utf8" && encoding !== "utf-8") throw new Error("Only UTF-8 fixture source reads are allowed");
  const url=new URL(String(input),location.href);
  if (url.origin !== location.origin) throw new Error("Fixture source reads must remain on loopback origin");
  const result=await fetch(url);if (!result.ok) throw new Error(`Fixture source unavailable: ${url.pathname}`);
  return result.text();
}
export function runInNewContext(source,context) {
  const bindings = { ...context, globalThis: context };
  return Function(...Object.keys(bindings),source).call(context,...Object.values(bindings));
}
globalThis.setImmediate = callback => setTimeout(callback,0);
export async function run() {
  const results=[];
  for (const {name,fn} of cases) {
    try { await fn();results.push({name,passed:true}); }
    catch (error) { results.push({name,passed:false,message:String(error.stack || error)}); }
  }
  return results;
}
