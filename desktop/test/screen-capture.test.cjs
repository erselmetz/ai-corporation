"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { createDisplayMediaRequestHandler } = require("../screen-capture.cjs");

test("trusted request receives only the exact source selected by the owner", async () => {
  const sources = [{ id: "screen:1", name: "Display 1" }, { id: "window:2", name: "Editor" }];
  let selected = null;
  let result = "unset";
  const handler = createDisplayMediaRequestHandler({
    isTrusted: request => request.trusted,
    getSources: async () => sources,
    chooseSource: async available => {
      assert.deepEqual(available, sources);
      selected = sources[1];
      return selected;
    },
  });
  await handler({ trusted: true }, value => { result = value; });
  assert.deepEqual(result, { video: selected });
});

test("untrusted, canceled, stale source, empty list, and errors fail closed", async () => {
  let enumerations = 0;
  const source = { id: "screen:1", name: "Display 1" };
  const handler = createDisplayMediaRequestHandler({
    isTrusted: request => request.trusted,
    getSources: async () => { enumerations += 1; return [source]; },
    chooseSource: async () => null,
  });
  let result = "unset";
  await handler({ trusted: false }, value => { result = value; });
  assert.equal(result, null);
  assert.equal(enumerations, 0);
  await handler({ trusted: true }, value => { result = value; });
  assert.equal(result, null);

  const stale = createDisplayMediaRequestHandler({
    isTrusted: () => true, getSources: async () => [source],
    chooseSource: async () => ({ id: "screen:foreign" }),
  });
  await stale({}, value => { result = value; });
  assert.equal(result, null);

  const error = createDisplayMediaRequestHandler({
    isTrusted: () => true, getSources: async () => { throw new Error("private system detail"); },
    chooseSource: async () => source,
  });
  await error({}, value => { result = value; });
  assert.equal(result, null);
});

test("the handler never selects a source when source inventory is empty", async () => {
  let chooserCalled = false;
  const handler = createDisplayMediaRequestHandler({
    isTrusted: () => true, getSources: async () => [],
    chooseSource: async () => { chooserCalled = true; return null; },
  });
  let result = "unset";
  await handler({}, value => { result = value; });
  assert.equal(result, null);
  assert.equal(chooserCalled, false);
});
