import { run } from "./harness.mjs";
// A module worker has no ambient DOM, matching the original contract fixtures.
// Real-page DOM/CSP tests run separately against the actual public/Advanced pages.
self.onmessage = async ({data}) => {
  try {
    await import('/tests/'+data.filename);
    self.postMessage({results:await run()});
  } catch (error) { self.postMessage({error:String(error.stack || error)}); }
};
