// Browser fixture: Python/CDP runner; original assertion behavior retained.
import { assert } from "/__contracts/harness.mjs";
import { test } from "/__contracts/harness.mjs";
import { formatDetails } from "../app/webui/static/ui-details.mjs";

test("review details retain nested evidence and exact values without a JSON envelope", () => {
  const digest = "a".repeat(64);
  const text = formatDetails({ target_digest: digest, confirmed: false, items: [{ name: "<script>inert</script>", count: 0 }], note: null });
  assert.match(text, new RegExp(`Target digest: ${digest}`));
  assert.match(text, /Confirmed: No/);
  assert.match(text, /Name: <script>inert<\/script>/);
  assert.match(text, /Count: 0/);
  assert.match(text, /Note: Not recorded/);
  assert.doesNotMatch(text, /"target_digest"|\{\s*"/);
});

test("empty lists and plain strings have explicit readable output", () => {
  assert.equal(formatDetails({ items: [] }), "Items:\n  None");
  assert.equal(formatDetails("Evidence is unavailable."), "Evidence is unavailable.");
});
