import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { runInNewContext } from "node:vm";
import test from "node:test";
import { taskGroups, tasks, nextTask, roadmapRules, recommendedOrder } from "../tasks-data.mjs";
import { verificationLabels } from "../roadmap-status.js";

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.text = ""; }
  set textContent(value) { this.text = value; this.children = []; }
  get textContent() { return this.text + this.children.map(node => node.textContent).join(""); }
  set innerHTML(_) { throw new Error("Task contracts must be rendered as text"); }
  append(...nodes) { this.children.push(...nodes); }
}
const source = (await readFile(new URL("../tasks-page.js", import.meta.url), "utf8")).replace(/^import[^\n]+\n/gm, "");
function render() {
  const elements = Object.fromEntries(["roadmap-groups", "roadmap-summary", "category-index", "next-task", "roadmap-rules"].map(id => [id, new Element("div")]));
  runInNewContext(source, { taskGroups, tasks, nextTask, roadmapRules, recommendedOrder, verificationLabels,
    document: { querySelector: selector => elements[selector.slice(1)], createElement: tag => new Element(tag) } });
  return elements;
}

test("shows all tasks in descending order and reports the next planned task", () => {
  const elements = render();
  const groups = elements["roadmap-groups"].children;
  assert.equal(groups[0].id, "tasks-199-199");
  const items = groups.flatMap(group => group.children[1].children);
  assert.deepEqual(items.map(item => Number(item.children[0].textContent)), Array.from({ length: 199 }, (_, index) => 199 - index));
  assert.match(elements["roadmap-summary"].textContent, /199 roadmap tasks.*193 completed.*4 deferred and incomplete.*1 planned.*1 design only/);
  assert.match(elements["next-task"].textContent, /Task 199.*Owner-gated computer automation/);
  const newest = items[0];
  assert.equal(newest.children[2].textContent, "Planned");
  assert.equal(newest.children[4].textContent, "AI verification: not recorded");
  assert.equal(newest.children[5].textContent, "Real hardware/live provider: unverified");
  assert.equal(newest.id, "task-199");
  const latestCompleted = items.find(item => item.id === "task-198");
  assert.equal(latestCompleted.children[2].textContent, "Completed");
  assert.match(latestCompleted.textContent, /task-198-multimodal-capability-packs/);
  const priorCheckpoint = items.find(item => item.id === "task-191");
  assert.match(priorCheckpoint.children[4].textContent, /AI-verified/);
});

test("renders completion evidence separately from planned decision gates and exposes handoff rules", () => {
  assert.equal(tasks.find(task => task.number === 171).status, "completed");
  assert.equal(tasks.find(task => task.number === 171).checkpoint, "task-171-unified-settings-operator-controls");
  assert.match(tasks.find(task => task.number === 171).validation.join(" "), /Next.js static production build/);
  assert.match(tasks.find(task => task.number === 171).limitations.join(" "), /installer was not rebuilt/);
  assert.equal(tasks.find(task => task.number === 172).status, "completed");
  assert.equal(tasks.find(task => task.number === 191).status, "completed");
  assert.equal(tasks.find(task => task.number === 191).realWorldVerification.status, "partial");
  assert.match(tasks.find(task => task.number === 191).limitations.join(" "), /Manual clean-Windows-profile acceptance remains pending/);
  assert.equal(tasks.find(task => task.number === 192).status, "completed");
  assert.equal(tasks.find(task => task.number === 192).checkpoint, "task-192-small-model-answer-quality");
  assert.equal(tasks.find(task => task.number === 166).status, "completed");
  assert.equal(tasks.find(task => task.number === 166).checkpoint, "task-166-opt-in-proactive-suggestions");
  assert.match(tasks.find(task => task.number === 166).validation.join(" "), /194 passed/);
  assert.match(tasks.find(task => task.number === 166).limitations.join(" "), /deterministic review prompts/);
  const elements = render();
  const items = elements["roadmap-groups"].children.flatMap(group => group.children[1].children);
  const completed = items.find(item => item.id === "task-103");
  const dispatch = items.find(item => item.id === "task-111");
  const multiProvider = items.find(item => item.id === "task-112");
  const release = items.find(item => item.id === "task-129");
  const semanticMemory = items.find(item => item.id === "task-130");
  const deferred = items.find(item => item.id === "task-134");
  const scopedBrowser = items.find(item => item.id === "task-156");
  assert.equal(release.children[2].textContent, "Completed");
  assert.match(release.textContent, /task-129-command-center-release-acceptance/);
  assert.match(release.textContent, /206A36D5C94FD76B2696C01F95CD842C24E3A79FD05FEB7FDB45F3DA101DC091/);
  assert.match(release.textContent, /capacity remain UNKNOWN/);
  assert.equal(semanticMemory.children[2].textContent, "Completed");
  assert.match(semanticMemory.textContent, /task-130-semantic-memory-rag-foundation/);
  assert.match(semanticMemory.textContent, /104 passed/);
  assert.equal(deferred.children[2].textContent, `Deferred ${String.fromCharCode(0x2014)} incomplete`);
  assert.match(deferred.textContent, /no verified first-party pack artifact source/);
  assert.equal(scopedBrowser.children[2].textContent, "Completed");
  assert.match(scopedBrowser.textContent, /task-156-scoped-browser-automation/);
  assert.match(scopedBrowser.textContent, /exact HTTPS origin/);
  const scopedDesktop = items.find(item => item.id === "task-157");
  assert.equal(scopedDesktop.children[2].textContent, "Completed");
  assert.match(scopedDesktop.textContent, /task-157-scoped-desktop-automation/);
  assert.match(scopedDesktop.textContent, /Windows UI Automation/);
  assert.equal(items.find(item => item.id === "task-158").children[2].textContent, "Completed");
  assert.match(items.find(item => item.id === "task-158").textContent, /task-158-automation-review-traces/);
  assert.equal(items.find(item => item.id === "task-135").children[2].textContent, "Completed");
  const onboarding = items.find(item => item.id === "task-132");
  assert.equal(onboarding.children[2].textContent, "Completed");
  assert.match(onboarding.textContent, /task-132-guided-first-run-setup/);
  const providerGuidance = items.find(item => item.id === "task-133");
  assert.equal(providerGuidance.children[2].textContent, "Completed");
  assert.match(providerGuidance.textContent, /task-133-provider-model-setup-guidance/);
  const distribution = items.find(item => item.id === "task-131");
  assert.equal(distribution.children[2].textContent, "Completed");
  assert.match(distribution.textContent, /task-131-supported-packaging-distribution-strategy/);
  assert.equal(completed.children[2].textContent, "Completed");
  assert.match(completed.textContent, /Verified checkpoint: d1ca364/);
  assert.match(completed.textContent, /876 Python passed/);
  const localSetup = items.find(item => item.id === "task-104");
  assert.match(localSetup.textContent, /Verified checkpoint: task-104-local-model-setup/);
  assert.ok(localSetup.children[6].children.some(node => node.href === "https://github.com/erselmetz/ai-corporation/tree/task-104-local-model-setup"));
  const onlineProvider = items.find(item => item.id === "task-105");
  assert.equal(onlineProvider.children[2].textContent, "Completed");
  assert.match(onlineProvider.textContent, /task-105-gemini-online-chat/);
  const secureChatOnboarding = items.find(item => item.id === "task-106");
  assert.equal(secureChatOnboarding.children[2].textContent, "Completed");
  assert.match(secureChatOnboarding.textContent, /task-106-secure-chat-onboarding/);
  assert.match(secureChatOnboarding.textContent, /best-effort/);
  assert.equal(dispatch.children[2].textContent, "Completed");
  assert.match(dispatch.textContent, /task-111-controlled-worker-dispatch/);
  assert.match(dispatch.textContent, /Focused dispatch API.*38 passed/);
  assert.match(dispatch.textContent, /fails closed until an embedding host/);
  assert.match(dispatch.textContent, /Acceptance checks/);
  assert.match(dispatch.textContent, /Out of scope/);
  assert.equal(multiProvider.children[2].textContent, "Completed");
  assert.match(multiProvider.textContent, /task-112-multiple-provider-connections/);
  assert.match(multiProvider.textContent, /88 passed/);
  assert.match(multiProvider.textContent, /16 passed/);
  assert.match(multiProvider.textContent, /not a monetary guarantee/);
  const individualChat = items.find(item => item.id === "task-108");
  assert.equal(individualChat.children[2].textContent, "Completed");
  assert.match(individualChat.textContent, /manual and require an explicit preview\/confirmation/);
  assert.match(individualChat.textContent, /one-Gemini-Agent connection flow/);
  assert.match(individualChat.textContent, /62 passed/);
  const assignmentPolicy = items.find(item => item.id === "task-109");
  assert.equal(assignmentPolicy.children[2].textContent, "Completed");
  assert.match(assignmentPolicy.textContent, /fresh positive tested capability references/);
  assert.match(assignmentPolicy.textContent, /task-109-capability-based-assignment-policy/);
  const chatProposal = items.find(item => item.id === "task-110");
  assert.equal(chatProposal.children[2].textContent, "Completed");
  assert.match(chatProposal.textContent, /exact server-generated proposal digest/);
  assert.match(chatProposal.textContent, /chat-task:create/);
  assert.match(chatProposal.textContent, /task-110-chat-proposals-pending-task-review/);
  const streaming = items.find(item => item.id === "task-120");
  assert.equal(streaming.children[2].textContent, "Completed");
  assert.match(streaming.textContent, /task-120-supported-streaming-truthful-stop/);
  assert.match(streaming.textContent, /79 passed/);
  assert.match(streaming.textContent, /Stop only hides later chunks/);
  assert.match(streaming.textContent, /known unrelated pre-existing failures/);
  const repositoryStudy = items.find(item => item.id === "task-121");
  assert.equal(repositoryStudy.children[2].textContent, "Completed");
  assert.match(repositoryStudy.textContent, /task-121-chat-driven-github-study/);
  assert.match(repositoryStudy.textContent, /exact-repository allowlist/);
  assert.match(repositoryStudy.textContent, /unapproved/);
  assert.match(repositoryStudy.textContent, /empty GitHub repository allowlist/);
  const readiness = items.find(item => item.id === "task-169");
  assert.equal(readiness.children[2].textContent, "Completed");
  assert.match(readiness.textContent, /never replayed/i);
  assert.match(readiness.textContent, /hardware fit remain UNKNOWN/i);
  assert.match(elements["roadmap-rules"].textContent, /Do not infer approval/);
  assert.match(elements["roadmap-rules"].textContent, /without required human QA sign-off/);
  assert.match(elements["roadmap-rules"].textContent, /Do not mark tasks complete by policy change alone/);
  assert.match(elements["roadmap-rules"].textContent, /Task 190 remains design-only/);
  assert.match(elements["roadmap-rules"].textContent, /identical generated code is not guaranteed/);
});

test("publishes completed milestones and remaining phases with their current status", () => {
  const settings = tasks.find(task => task.number === 171);
  assert.equal(settings.status, "completed");
  assert.equal(settings.checkpoint, "task-171-unified-settings-operator-controls");
  assert.match(settings.validation.join(" "), /17 passed.*33 passed/);
  assert.match(settings.limitations.join(" "), /installer was not rebuilt/);
  const planned = tasks.filter(task => task.number >= 174);
  assert.deepEqual(planned.map(task => [task.number, task.status]), [
    [174, "completed"], [175, "completed"], [176, "completed"], [177, "completed"], [178, "completed"], [179, "completed"],
    [180, "completed"], [181, "completed"], [182, "completed"], [183, "completed"], [184, "completed"], [185, "completed"],
    [186, "completed"], [187, "completed"], [188, "completed"], [189, "completed"], [190, "design_only"], [191, "completed"], [192, "completed"], [193, "deferred"], [194, "deferred"], [195, "completed"],
    [196, "completed"], [197, "completed"], [198, "completed"], [199, "planned"],
  ]);
  assert.equal(tasks.find(task => task.number === 177).checkpoint, "task-177-auto-rag-trace");
  assert.equal(tasks.find(task => task.number === 178).checkpoint, "task-178-nav-fix");
  assert.equal(tasks.find(task => task.number === 181).checkpoint, "task-181-consent-based-model-routing");
  assert.equal(tasks.find(task => task.number === 182).checkpoint, "task-182-reviewed-chat-tools");
  assert.equal(tasks.find(task => task.number === 183).checkpoint, "task-183-visible-chat-workflow-scaffolding");
  assert.equal(tasks.find(task => task.number === 185).checkpoint, "task-185-local-recovery-and-update-controls");
  assert.equal(tasks.find(task => task.number === 186).checkpoint, "task-186-globe-visual-map");
  assert.equal(tasks.find(task => task.number === 187).checkpoint, "task-187-opt-in-local-voice-input");
  assert.equal(tasks.find(task => task.number === 188).checkpoint, "task-188-opt-in-local-voice-output");
  assert.equal(tasks.find(task => task.number === 189).checkpoint, "task-189-opt-in-local-vision-input");
  assert.equal(tasks.find(task => task.number === 197).checkpoint, "task-197-brain-visualization");
  assert.equal(tasks.find(task => task.number === 198).checkpoint, "task-198-multimodal-capability-packs");
  assert.match(tasks.find(task => task.number === 178).validation.join(" "), /native window level/);
  assert.match(tasks.find(task => task.number === 178).limitations.join(" "), /not been published or distributed/);
  for (const task of tasks.filter(task => task.number >= 180)) {
    assert.ok(task.acceptance.length, `Task ${task.number} has acceptance checks`);
    assert.ok(task.outOfScope.length, `Task ${task.number} has exclusions`);
    assert.ok(task.risks.length, `Task ${task.number} has risks`);
    assert.ok(task.automatedVerification.length, `Task ${task.number} has AI-run checks`);
    assert.equal(task.manualVerification, undefined);
    assert.ok(task.followUpValidation.length);
  }
  assert.deepEqual(recommendedOrder.map(({ number }) => number), [178, 176, 177, 175, 180, 184, 181, 182, 183, 185, 186, 187, 188, 189, 190, 192, 193, 194, 195, 196, 197, 198, 199]);
  const corporationMap = tasks.find(task => task.number === 172);
  assert.match(corporationMap.description, /interactive, evidence-backed 3D map/);
  assert.match(corporationMap.acceptance.join(" "), /zoom\/orbit\/pan.*filters\/layers/i);
  assert.match(corporationMap.acceptance.join(" "), /labeled 2D\/list fallback/);
  assert.match(corporationMap.outOfScope.join(" "), /Do not invent nodes, relationships, activity/);
  const memoryMap = tasks.find(task => task.number === 173);
  assert.equal(memoryMap.status, "completed");
  assert.equal(memoryMap.checkpoint, "task-173-memory-knowledge-relationship-explorer");
  assert.match(memoryMap.validation.join(" "), /104 passed.*206 passed/);
  assert.match(memoryMap.limitations.join(" "), /at most 50 records/);
  assert.match(memoryMap.acceptance.join(" "), /provenance.*retrieval matches/);
  assert.match(memoryMap.outOfScope.join(" "), /Do not broaden Task 130/);
  const multimodal = planned.find(task => task.number === 174);
  assert.match(multimodal.acceptance.join(" "), /microphone, camera, screen-capture/);
  assert.match(multimodal.outOfScope.join(" "), /Do not auto-enable/);
  const usability = planned.find(task => task.number === 175);
  assert.match(usability.acceptance.join(" "), /keyboard-only use, screen-reader semantics/);
  assert.match(usability.validation.join(" "), /Expert heuristic walkthrough.*not a representative owner study/);
  assert.match(usability.limitations.join(" "), /No representative new or experienced owner participated/);
  assert.match(usability.limitations.join(" "), /No usability or accessibility conformance claim is made/);
});
