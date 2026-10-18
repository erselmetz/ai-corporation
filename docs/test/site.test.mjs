import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import { createDocumentationServer } from "../server.mjs";
import { taskGroups, tasks, foundationTasks, post100Tasks, nextTask, roadmapRules, recommendedOrder } from "../tasks-data.mjs";
import { renderTaskDirectory, renderStatusSummary, renderRecommendedOrder } from "../roadmap-status.js";

const pages = [
  "index.html",
  "documentation.html",
  "architecture.html",
  "organization.html",
  "how-it-works.html",
  "integrations.html",
  "security.html",
  "roadmap.html",
  "tasks.html",
  "updates.html",
  "about.html",
];

let server;
let baseUrl;

class StatusElement {
  constructor(tag) { this.tag = tag; this.children = []; this.ownerDocument = this; this.textContent = ""; }
  createElement(tag) { return new StatusElement(tag); }
  append(...nodes) { this.children.push(...nodes); }
}

before(async () => {
  server = createDocumentationServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  assert.ok(address && typeof address === "object");
  baseUrl = `http://127.0.0.1:${address.port}`;
});

after(async () => {
  if (server?.listening) {
    await new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }
});

describe("documentation site", () => {
  it("serves every page and navigation links target existing pages", async () => {
    for (const filename of pages) {
      const response = await fetch(`${baseUrl}/${filename}`);
      assert.equal(response.status, 200, `${filename} should load`);
      assert.match(response.headers.get("content-type") ?? "", /text\/html/);
      const html = await response.text();
      for (const target of ["index.html", "documentation.html", "architecture.html", "roadmap.html", "tasks.html", "updates.html", "about.html"]) {
        assert.ok(html.includes(`href="${target}"`), `${filename} should link to primary page ${target}`);
      }
      if (filename === "documentation.html") {
        for (const target of pages) assert.ok(html.includes(`href="${target}"`), `overview should link to ${target}`);
      }
    }
  });

  it("serves required page assets and does not expose paths outside the allowlist", async () => {
    for (const asset of ["site.css", "tasks-data.mjs", "tasks-page.js", "roadmap-status.js"]) {
      assert.equal((await fetch(`${baseUrl}/${asset}`)).status, 200);
    }
    assert.equal((await fetch(`${baseUrl}/../README.md`)).status, 404);
    assert.equal((await fetch(`${baseUrl}/README.md`)).status, 404);
  });

  it("resolves local public links including generated task and category anchors", async () => {
    const generatedIds = new Set([
      ...tasks.map(task => `task-${task.number}`),
      ...taskGroups.map(group => `tasks-${group.range.replace("â€“", "-")}`),
    ]);
    const contents = new Map();
    for (const page of pages) contents.set(page, await (await fetch(`${baseUrl}/${page}`)).text());
    for (const [page, html] of contents) {
      for (const [, link] of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
        if (/^[a-z][a-z0-9+.-]*:/i.test(link)) continue;
        const [filename, anchor] = link.split("#");
        const target = filename || page;
        const response = await fetch(`${baseUrl}/${target}`);
        assert.equal(response.status, 200, `${page}: ${link}`);
        if (anchor) {
          const destination = contents.get(target) ?? await response.text();
          assert.ok(destination.includes(`id="${anchor}"`) ||
            (target === "tasks.html" && generatedIds.has(anchor)), `${page}: missing ${link}`);
        }
      }
    }
  });

  it("preserves foundation tasks 1â€“100 and adds contiguous post-100 contracts", () => {
    assert.equal(tasks.length, 190);
    assert.equal(foundationTasks.length, 100);
    assert.deepEqual(tasks.map((task) => task.number), Array.from({ length: 190 }, (_, i) => i + 1));
    assert.equal(taskGroups.flatMap(group => group.tasks).length, 190);
  });

  it("records verified, deferred, and planned work without treating deferral as completion", () => {
    assert.equal(tasks.filter(task => task.status === "completed").length, 186);
    assert.equal(tasks.filter(task => task.status === "deferred").length, 2);
    assert.equal(tasks.filter(task => task.status === "planned").length, 1);
    assert.equal(tasks.filter(task => task.status === "design_only").length, 1);
    assert.equal(tasks.find(task => task.number === 134).status, "deferred");
    assert.equal(tasks.find(task => task.number === 170).status, "deferred");
    assert.equal(tasks.find(task => task.number === 171).status, "completed");
    assert.equal(tasks.find(task => task.number === 172).status, "completed");
    assert.equal(tasks.find(task => task.number === 173).status, "completed");
    assert.equal(tasks.find(task => task.number === 173).checkpoint, "task-173-memory-knowledge-relationship-explorer");
    assert.equal(tasks.find(task => task.number === 174).status, "completed");
    assert.equal(tasks.find(task => task.number === 175).status, "completed");
    assert.equal(tasks.find(task => task.number === 175).checkpoint, "task-175-ai-usability-accessibility-regression-evaluation");
    assert.equal(tasks.find(task => task.number === 176).status, "completed");
    assert.equal(tasks.find(task => task.number === 176).checkpoint, "task-176-zero-config-first-run-ai-acceptance");
    assert.equal(tasks.find(task => task.number === 177).status, "completed");
    assert.equal(tasks.find(task => task.number === 177).checkpoint, "task-177-auto-rag-trace");
    assert.equal(tasks.find(task => task.number === 181).status, "completed");
    assert.equal(tasks.find(task => task.number === 182).status, "completed");
    assert.equal(tasks.find(task => task.number === 182).checkpoint, "task-182-reviewed-chat-tools");
    assert.equal(tasks.find(task => task.number === 183).status, "completed");
    assert.equal(tasks.find(task => task.number === 183).checkpoint, "task-183-visible-chat-workflow-scaffolding");
    assert.equal(tasks.find(task => task.number === 185).status, "completed");
    assert.equal(tasks.find(task => task.number === 185).checkpoint, "task-185-local-recovery-and-update-controls");
    assert.equal(tasks.find(task => task.number === 186).status, "completed");
    assert.equal(tasks.find(task => task.number === 186).checkpoint, "task-186-globe-visual-map");
    assert.equal(tasks.find(task => task.number === 187).checkpoint, "task-187-opt-in-local-voice-input");
    assert.equal(tasks.find(task => task.number === 188).checkpoint, "task-188-opt-in-local-voice-output");
    assert.equal(tasks.find(task => task.number === 181).checkpoint, "task-181-consent-based-model-routing");
    assert.equal(tasks.find(task => task.number === 174).checkpoint, "task-174-unified-multimodal-capability-controls");
    assert.equal(tasks.find(task => task.number === 172).checkpoint, "task-172-interactive-3d-corporation-execution-map");
    assert.equal(tasks.find(task => task.number === 171).checkpoint, "task-171-unified-settings-operator-controls");
    assert.equal(tasks.find(task => task.number === 135).status, "completed");
    assert.equal(tasks.find(task => task.number === 156).status, "completed");
    assert.equal(tasks.find(task => task.number === 157).status, "completed");
    assert.equal(tasks.find(task => task.number === 158).status, "completed");
    assert.equal(tasks.find(task => task.number === 158).checkpoint, "task-158-automation-review-traces");
    assert.equal(tasks.find(task => task.number === 157).checkpoint, "task-157-scoped-desktop-automation");
    assert.match(tasks.find(task => task.number === 157).decisions.join(" "), /Windows UI Automation through the optional pywinauto UIA backend/);
    assert.equal(tasks.find(task => task.number === 156).checkpoint, "task-156-scoped-browser-automation");
    assert.match(tasks.find(task => task.number === 156).limitations.join(" "), /DNS-to-address pinning is not implemented/);
    assert.equal(tasks.find(task => task.number === 136).status, "completed");
    assert.equal(tasks.find(task => task.number === 138).status, "completed");
    assert.equal(tasks.find(task => task.number === 139).status, "completed");
    assert.equal(tasks.find(task => task.number === 150).status, "completed");
    assert.equal(tasks.find(task => task.number === 150).checkpoint, "task-150-bounded-image-input-vision-context");
    assert.equal(tasks.find(task => task.number === 151).status, "completed");
    assert.equal(tasks.find(task => task.number === 151).checkpoint, "task-151-explicit-screen-capture-provider");
    assert.equal(tasks.find(task => task.number === 152).status, "completed");
    assert.equal(tasks.find(task => task.number === 152).checkpoint, "task-152-bounded-optional-image-processing");
    assert.deepEqual(tasks.find(task => task.number === 152).dependsOn, [150]);
    assert.equal(tasks.find(task => task.number === 153).status, "completed");
    assert.equal(tasks.find(task => task.number === 153).checkpoint, "task-153-bounded-ocr-provider-contract");
    assert.deepEqual(tasks.find(task => task.number === 153).dependsOn, [150, 152]);
    assert.equal(tasks.find(task => task.number === 154).status, "completed");
    assert.equal(tasks.find(task => task.number === 154).checkpoint, "task-154-explicit-optional-tesseract-backend");
    assert.deepEqual(tasks.find(task => task.number === 154).dependsOn, [153]);
    assert.equal(tasks.find(task => task.number === 155).status, "completed");
    assert.equal(tasks.find(task => task.number === 155).checkpoint, "task-155-one-use-camera-vision-chat");
    assert.deepEqual(tasks.find(task => task.number === 155).dependsOn, [144, 150, 153]);
    assert.equal(tasks.find(task => task.number === 156).status, "completed");
    assert.equal(tasks.find(task => task.number === 156).checkpoint, "task-156-scoped-browser-automation");
    assert.deepEqual(tasks.find(task => task.number === 156).dependsOn, [90, 140, 141, 142, 144]);
    assert.equal(tasks.find(task => task.number === 159).status, "completed");
    assert.equal(tasks.find(task => task.number === 159).checkpoint, "task-159-shared-visual-design-system");
    assert.equal(tasks.find(task => task.number === 160).status, "completed");
    assert.equal(tasks.find(task => task.number === 160).checkpoint, "task-160-operational-command-center-dashboard");
    assert.equal(tasks.find(task => task.number === 161).status, "completed");
    assert.equal(tasks.find(task => task.number === 161).checkpoint, "task-161-knowledge-resource-visualization");
    assert.equal(tasks.find(task => task.number === 162).checkpoint, "task-162-three-dimensional-map-review");
    assert.equal(tasks.find(task => task.number === 162).status, "completed");
    assert.equal(tasks.find(task => task.number === 163).status, "completed");
    assert.equal(tasks.find(task => task.number === 164).status, "completed");
    assert.equal(tasks.find(task => task.number === 165).status, "completed");
    assert.equal(tasks.find(task => task.number === 165).checkpoint, "task-165-coordinator-presence-orchestration");
    assert.match(tasks.find(task => task.number === 165).limitations.join(" "), /no assignment-reason field/);
    assert.equal(tasks.find(task => task.number === 166).status, "completed");
    assert.equal(tasks.find(task => task.number === 166).checkpoint, "task-166-opt-in-proactive-suggestions");
    assert.match(tasks.find(task => task.number === 166).decisions.join(" "), /disabled by default/);
    assert.match(tasks.find(task => task.number === 166).limitations.join(" "), /not notifications or background suppression/);
    assert.equal(tasks.find(task => task.number === 167).status, "completed");
    assert.equal(tasks.find(task => task.number === 167).checkpoint, "task-167-trusted-updates-config-migration");
    assert.deepEqual(tasks.find(task => task.number === 167).dependsOn, [126, 127, 129, 131]);
    assert.match(tasks.find(task => task.number === 167).limitations.join(" "), /not Windows Authenticode-signed/);
    assert.equal(tasks.find(task => task.number === 168).status, "completed");
    assert.equal(tasks.find(task => task.number === 168).checkpoint, "task-168-encrypted-data-portability");
    assert.deepEqual(tasks.find(task => task.number === 168).dependsOn, [118, 130, 143, 167]);
    assert.match(tasks.find(task => task.number === 168).limitations.join(" "), /passphrase is not stored and cannot be recovered/);
    assert.equal(tasks.find(task => task.number === 169).status, "completed");
    assert.equal(tasks.find(task => task.number === 169).checkpoint, "task-169-crash-recovery-performance-readiness");
    assert.match(tasks.find(task => task.number === 169).decisions.join(" "), /no numerical hardware-support thresholds/);
    assert.match(tasks.find(task => task.number === 169).limitations.join(" "), /model workload and hardware fit remain UNKNOWN/);
    const task170 = tasks.find(task => task.number === 170);
    assert.equal(task170.status, "deferred");
    assert.ok(!task170.dependsOn.includes(134));
    assert.match(task170.decisions.join(" "), /exclude app-managed capability-pack installation\/loading/);
    assert.match(task170.limitations.join(" "), /No independent security\/privacy reviewer/);
    const task175 = tasks.find(task => task.number === 175);
    assert.equal(task175.status, "completed");
    assert.ok(!task175.dependsOn.includes(134));
    assert.match(task175.acceptance.join(" "), /capability packs are unavailable/);
    assert.match(task175.decisions.join(" "), /Task 134 is deferred and excluded/);
    assert.match(task175.validation.join(" "), /3\.56:1 against.*four media indicators.*all announced changes/);
    assert.match(task175.limitations.join(" "), /No representative new or experienced owner participated/);
    assert.equal(tasks.find(task => task.number === 163).status, "completed");
    assert.equal(tasks.find(task => task.number === 163).checkpoint, "task-163-original-assistant-identity");
    assert.match(tasks.find(task => task.number === 163).decisions.join(" "), /do not grant permissions/);
    const visualizationReview = tasks.find(task => task.number === 162);
    assert.match(visualizationReview.decisions.join(" "), /p95 <= 16.7 ms.*p99 <= 33.3 ms/);
    assert.match(visualizationReview.decisions.join(" "), /WCAG 2.2 AA/);
    assert.match(visualizationReview.limitations.join(" "), /not achieved measurements/);
    assert.equal(tasks.find(task => task.number === 158).checkpoint, "task-158-automation-review-traces");
    assert.equal(nextTask.number, 189);
    assert.ok(tasks.slice(0, 133).every(task => task.status === "completed"));
    assert.ok(tasks.slice(133).some(task => task.status === "planned"));
    assert.equal(tasks[51].number, 52);
    assert.equal(tasks[51].title, "Activity / Logs UI");
    assert.equal(tasks[51].status, "completed");
    assert.equal(tasks[78].title, "Automated Patch Development");
    assert.equal(tasks[78].description, "Develop proposed changes in an isolated, disposable work area.");
    assert.equal(tasks[78].status, "completed");
    assert.equal(tasks[79].title, "Automated Testing Workflow");
    assert.equal(tasks[79].description, "Run explicitly selected tests and report the actual results for a proposed change.");
    assert.equal(tasks[79].status, "completed");
    assert.equal(tasks[80].title, "Automated Code Review");
    assert.equal(tasks[80].description, "Review proposed changes for correctness, regressions, and policy compliance.");
    assert.equal(tasks[80].status, "completed");
    assert.equal(tasks[81].title, "Maintenance Sandbox");
    assert.equal(tasks[81].description, "Keep maintenance experiments isolated from the active Corporation and host state.");
    assert.equal(tasks[81].status, "completed");
    assert.equal(tasks[82].title, "Human Approval Workflow");
    assert.equal(tasks[82].description, "Require explicit human review and approval before protected changes are applied.");
    assert.equal(tasks[82].status, "completed");
    assert.equal(tasks[83].title, "Git Checkpoint Integration");
    assert.equal(tasks[83].status, "completed");
    assert.equal(tasks[84].title, "Controlled Self-Maintenance");
    assert.equal(tasks[84].description, "Orchestrate a bounded, auditable maintenance flow without unrestricted self-modification.");
    assert.equal(tasks[84].status, "completed");
    assert.equal(tasks[85].title, "MCP Integration");
    assert.equal(tasks[85].status, "completed");
    assert.equal(tasks[86].title, "GitHub Integration");
    assert.equal(tasks[86].status, "completed");
    assert.equal(tasks[87].title, "Browser/Web Research Capability");
    assert.equal(tasks[87].status, "completed");
    assert.equal(tasks[88].title, "Coding Tool Integration");
    assert.equal(tasks[88].status, "completed");
    assert.equal(tasks[89].title, "Computer-Use Capability");
    assert.equal(tasks[89].description, "Explore permissioned computer interaction with explicit user-visible safeguards.");
    assert.equal(tasks[89].status, "completed");
    assert.equal(tasks[90].title, "External Service Integration");
    assert.equal(tasks[90].description, "Connect selected services through scoped credentials and auditable adapters.");
    assert.equal(tasks[90].status, "completed");
    assert.equal(tasks[91].title, "Capability Registry");
    assert.equal(tasks[91].description, "Describe available capabilities, ownership, requirements, and policy boundaries.");
    assert.equal(tasks[91].status, "completed");
    assert.equal(tasks[92].title, "Capability Discovery");
    assert.equal(tasks[92].description, "Identify candidate capabilities without granting or activating them automatically.");
    assert.equal(tasks[92].status, "completed");
    assert.equal(tasks[93].title, "Capability Evaluation");
    assert.equal(tasks[93].description, "Evaluate evidence, risks, fit, and operational requirements before adoption.");
    assert.equal(tasks[93].status, "completed");
    assert.equal(tasks[94].title, "Controlled Capability Integration");
    assert.equal(tasks[94].description, "Integrate approved capabilities through testing, review, and explicit change control.");
    assert.equal(tasks[94].status, "completed");
    assert.equal(tasks[95].title, "Corporation Planning System");
    assert.equal(tasks[95].description, "Support transparent organization-level planning with traceable priorities and constraints.");
    assert.equal(tasks[95].status, "completed");
    assert.equal(tasks[96].title, "Organization-Level Orchestration");
    assert.equal(tasks[96].description, "Coordinate work across organizational responsibilities and approved workflows.");
    assert.equal(tasks[96].status, "completed");
    assert.equal(tasks[97].title, "Adaptive Workforce");
    assert.equal(tasks[97].description, "Adjust organizational capacity and role assignments under explicit governance.");
    assert.equal(tasks[97].status, "completed");
    assert.deepEqual(
      tasks.slice(52, 99).map(({ number, status }) => [number, status]),
      Array.from({ length: 47 }, (_, index) => [index + 53, "completed"]),
    );
    assert.equal(tasks[98].title, "Self-Improvement Pipeline");
    assert.equal(tasks[98].description, "Evolve the controlled proposal, sandbox, testing, review, and approval pipeline.");
    assert.equal(tasks[98].status, "completed");
    assert.equal(tasks[99].title, "ERSELMETZ AI Platform");
    assert.equal(tasks[99].description, "Develop a coherent, governed platform for operating a virtual/simulated AI organization.");
    assert.equal(tasks[99].status, "completed");
    assert.equal(tasks[129].title, "Optional vector memory and RAG foundation");
    assert.equal(tasks[129].status, "completed");
    assert.equal(tasks[129].title, "Optional vector memory and RAG foundation");
    assert.equal(tasks[129].status, "completed");
  });

  it("renders every authoritative task in home, roadmap, changelog, and task status views", async () => {
    const indexes = [];
    for (const page of ["home", "roadmap", "changelog"]) {
      const index = new StatusElement("ol");
      renderTaskDirectory(index, tasks);
      indexes.push({ page, index });
    }
    const summary = new StatusElement("p");
    renderStatusSummary(summary, tasks);
    const order = new StatusElement("ol");
    renderRecommendedOrder(order, tasks, recommendedOrder);
    assert.match(summary.textContent, /190 tasks/);
    assert.equal(order.children.length, recommendedOrder.length);
    for (const page of ["index.html", "roadmap.html", "updates.html"]) {
      const html = await (await fetch(`${baseUrl}/${page}`)).text();
      assert.match(html, /src="roadmap-status.js"/);
      assert.match(html, /id="task-status-index"/);
      assert.match(html, /id="task-status-summary"/);
    }
    const taskPage = await (await fetch(`${baseUrl}/tasks.html`)).text();
    assert.match(taskPage, /src="tasks-page.js"/);
    assert.match(taskPage, /id="roadmap-groups"/);
    for (const { page, index } of indexes) {
      for (const task of tasks) {
        const rendered = index.children.find(item => item.id === `task-${task.number}`);
        assert.ok(rendered, `Task ${task.number} missing from ${page} status index`);
        const expectedStatus = task.status === "design_only" ? "Design only" : task.status === "deferred" ? "Deferred — incomplete" : task.status === "completed" ? "Completed" : "Planned";
        assert.ok(rendered.children[0].textContent.startsWith(`Task ${task.number}: ${task.title}`));
        assert.ok(rendered.children[0].textContent.endsWith(expectedStatus), `Task ${task.number} status mismatch: ${rendered.children[0].textContent}`);
      }
    }
  });

  it("summarizes the roadmap while preserving the full task contracts", async () => {
    const response = await fetch(`${baseUrl}/tasks.html`);
    const html = await response.text();
    assert.match(html, /id="task-page-status"/);
    assert.doesNotMatch(html, /173 complete; 2 deferred; 3 planned/);
    assert.match(html, /id="next-task"/);
    assert.match(html, /id="roadmap-rules"/);
  });

  it("keeps public overview pages concise and aligned with the latest roadmap status", async () => {
    const [home, documentation, architecture, roadmap, updates] = await Promise.all(
      ["index.html", "documentation.html", "architecture.html", "roadmap.html", "updates.html"].map(async page => (await fetch(`${baseUrl}/${page}`)).text()));
    assert.match(home, /Latest completed task/);
    assert.match(home, /Next acceptance gate/);
    assert.doesNotMatch(home, /Task 134/);
    assert.match(home, /Changelog/);
    assert.match(documentation, /local-first application with a Python backend and an Electron desktop interface/);
    assert.match(architecture, /Python service owns AI and application logic/);
    assert.match(updates, /Task 179/);
    assert.match(updates, /task-182-reviewed-chat-tools/);
    assert.match(updates, /Task 182.*SCOPED DEVELOPMENT ACCEPTANCE.*bounded arithmetic.*documentation:read.*untrusted/);
    assert.match(updates, /task-186-globe-visual-map.*SCOPED DEVELOPMENT ACCEPTANCE.*deterministic.*not geographic/);
    assert.match(updates, /task-187-opt-in-local-voice-input.*SCOPED DEVELOPMENT ACCEPTANCE.*10 seconds.*permission/);
    assert.match(updates, /task-188-opt-in-local-voice-output.*SCOPED DEVELOPMENT ACCEPTANCE.*device-local.*Stop\/clear-queue/);
    assert.match(updates, /task-185-local-recovery-and-update-controls.*SCOPED DEVELOPMENT ACCEPTANCE.*no background check.*defaults to keeping/);
    assert.match(updates, /task-183-visible-chat-workflow-scaffolding.*SCOPED DEVELOPMENT ACCEPTANCE/);
    assert.match(updates, /Task 178.*2026-10-17/);
    assert.match(updates, /Task 176.*2026-10-18.*COMPLETED SCOPED DEVELOPMENT ACCEPTANCE/);
    assert.match(updates, /real Gemini, and Ollama install\/model-download paths remain unverified follow-up/);
    assert.match(updates, /task-179-roadmap-sync/);
    assert.match(roadmap, /Recommended order/);
    assert.match(roadmap, /Next acceptance gate/);
    assert.match(roadmap, /Safety boundaries/);
    assert.doesNotMatch(roadmap, /Task 130.*semantic/i);
    assert.equal(nextTask?.number, 189);
    assert.equal(tasks.find(task => task.number === 178)?.status, "completed");
  });

  it("publishes release limitations without implying stable status or independent review", async () => {
    const security = await (await fetch(`${baseUrl}/security.html`)).text();
    assert.match(security, /local acceptance evidence only/);
    assert.match(security, /not a public stable release/);
    assert.match(security, /Task 134 remains deferred/);
    assert.match(security, /independent security\/privacy reviewer/);
    assert.match(security, /not that independent review/);
  });

  it("requires explicit post-100 acceptance, prior dependencies and truthful checkpoint evidence", () => {
    assert.equal(tasks.find(task => task.number === 153).status, "completed");
    assert.equal(tasks.find(task => task.number === 153).checkpoint, "task-153-bounded-ocr-provider-contract");
    assert.deepEqual(tasks.find(task => task.number === 153).dependsOn, [150, 152]);
    assert.equal(tasks.find(task => task.number === 154).status, "completed");
    assert.equal(tasks.find(task => task.number === 154).checkpoint, "task-154-explicit-optional-tesseract-backend");
    assert.deepEqual(tasks.find(task => task.number === 154).dependsOn, [153]);
    assert.equal(tasks.find(task => task.number === 155).status, "completed");
    assert.equal(tasks.find(task => task.number === 155).checkpoint, "task-155-one-use-camera-vision-chat");
    assert.equal(tasks.find(task => task.number === 156).checkpoint, "task-156-scoped-browser-automation");
    assert.deepEqual(tasks.find(task => task.number === 155).dependsOn, [144, 150, 153]);
    assert.equal(tasks.find(task => task.number === 159).status, "completed");
    assert.equal(tasks.find(task => task.number === 159).checkpoint, "task-159-shared-visual-design-system");
    assert.equal(tasks.find(task => task.number === 160).status, "completed");
    assert.equal(tasks.find(task => task.number === 160).checkpoint, "task-160-operational-command-center-dashboard");
    assert.equal(tasks.find(task => task.number === 161).status, "completed");
    assert.equal(tasks.find(task => task.number === 161).checkpoint, "task-161-knowledge-resource-visualization");
    assert.equal(tasks.find(task => task.number === 162).checkpoint, "task-162-three-dimensional-map-review");
    assert.equal(tasks.find(task => task.number === 162).status, "completed");
    assert.equal(tasks.find(task => task.number === 158).checkpoint, "task-158-automation-review-traces");
    assert.equal(nextTask.number, 189);
    const task122 = post100Tasks.find(task => task.number === 122);
    assert.equal(task122.status, "completed");
    assert.equal(task122.checkpoint, "task-122-isolated-adaptation-validation");
    assert.match(task122.validation.join(" "), /1043 passed, 3 skipped/);
    assert.match(task122.limitations.join(" "), /Default sandbox image policy is empty/);
    assert.deepEqual(post100Tasks.filter(task => task.status === "completed").map(task => task.checkpoint), ["f4e5b54", "1552893", "d1ca364", "task-104-local-model-setup", "task-105-gemini-online-chat", "task-106-secure-chat-onboarding", "task-107-editable-corporation-positions", "task-108-manual-ai-connection-assignment-individual-chat", "task-109-capability-based-assignment-policy", "task-110-chat-proposals-pending-task-review", "task-111-controlled-worker-dispatch", "task-112-multiple-provider-connections", "task-113-workflow-review-reporting", "task-114-corporation-structure-map", "task-115-workflow-map-progress-evidence", "task-116-accessible-3d-visualization", "task-117-owned-chat-knowledge",
      "task-118-durable-chat-history", "task-119-local-model-resource-controls",
      "task-120-supported-streaming-truthful-stop",
      "task-121-chat-driven-github-study", "task-122-isolated-adaptation-validation",
      "task-123-approved-local-activation", "task-124-read-only-software-inventory",
      "task-125-managed-vscode-user-lifecycle", "task-126-local-application-lifecycle",
      "task-127-windows-electron-installer", "task-128-optional-voice-interaction",
      "task-129-command-center-release-acceptance", "task-130-semantic-memory-rag-foundation",
      "task-131-supported-packaging-distribution-strategy", "task-132-guided-first-run-setup", "task-133-provider-model-setup-guidance", "task-135-semantic-retrieval-evaluation", "task-136-hybrid-lexical-semantic-retrieval", "task-137-semantic-index-lifecycle-observability", "task-138-owner-reviewed-knowledge-proposals", "task-139-versioned-documentation-review", "task-140-central-capability-permissions", "task-141-capability-grants-session-policy", "task-142-action-risk-approval-policy", "task-143-capability-audit-retention", "task-144-emergency-stop-capture-indicators", "task-145-bounded-speech-input-contracts", "task-146-optional-local-speech-recognition", "task-147-reviewed-speech-input-in-conversations", "task-148-offline-text-to-speech-provider", "task-149-bounded-local-voice-queue-controls", "task-150-bounded-image-input-vision-context", "task-151-explicit-screen-capture-provider", "task-152-bounded-optional-image-processing", "task-153-bounded-ocr-provider-contract", "task-154-explicit-optional-tesseract-backend", "task-155-one-use-camera-vision-chat", "task-156-scoped-browser-automation", "task-157-scoped-desktop-automation", "task-158-automation-review-traces", "task-159-shared-visual-design-system", "task-160-operational-command-center-dashboard", "task-161-knowledge-resource-visualization", "task-162-three-dimensional-map-review", "task-163-original-assistant-identity", "task-164-owner-response-preferences", "task-165-coordinator-presence-orchestration", "task-166-opt-in-proactive-suggestions", "task-167-trusted-updates-config-migration", "task-168-encrypted-data-portability", "task-169-crash-recovery-performance-readiness", "task-171-unified-settings-operator-controls", "task-172-interactive-3d-corporation-execution-map", "task-173-memory-knowledge-relationship-explorer", "task-174-unified-multimodal-capability-controls", "task-175-ai-usability-accessibility-regression-evaluation", "task-176-zero-config-first-run-ai-acceptance", "task-177-auto-rag-trace", "task-178-nav-fix", "task-179-roadmap-sync", "task-180-hardware-profile-ai-acceptance", "task-181-consent-based-model-routing", "task-182-reviewed-chat-tools", "task-183-visible-chat-workflow-scaffolding", "task-184-operator-state-ai-acceptance", "task-185-local-recovery-and-update-controls", "task-186-globe-visual-map", "task-187-opt-in-local-voice-input", "task-188-opt-in-local-voice-output"]);
    const task143 = post100Tasks.find(task => task.number === 143);
    assert.equal(task143.status, "completed");
    assert.equal(task143.checkpoint, "task-143-capability-audit-retention");
    assert.match(task143.validation.join(" "), /1138 passed, 6 skipped/);
    assert.match(task143.limitations.join(" "), /unencrypted at rest/);
    const task145 = post100Tasks.find(task => task.number === 145);
    assert.equal(task145.status, "completed");
    assert.equal(task145.checkpoint, "task-145-bounded-speech-input-contracts");
    assert.match(task145.validation.join(" "), /8 passed/);
    assert.match(task145.limitations.join(" "), /browser or remote provider/);
    const task146 = post100Tasks.find(task => task.number === 146);
    assert.equal(task146.status, "completed");
    assert.equal(task146.checkpoint, "task-146-optional-local-speech-recognition");
    assert.deepEqual(task146.dependsOn, [145]);
    assert.match(task146.decisions.join(" "), /does not install, catalog, download, or activate third-party packs/);
    assert.match(task146.validation.join(" "), /22 passed/);
    assert.match(task146.limitations.join(" "), /Cancellation is cooperative/);
    const task147 = post100Tasks.find(task => task.number === 147);
    assert.equal(task147.status, "completed");
    assert.equal(task147.checkpoint, "task-147-reviewed-speech-input-in-conversations");
    assert.deepEqual(task147.dependsOn, [128, 145, 146]);
    assert.match(task147.validation.join(" "), /29 passed/);
    assert.match(task147.limitations.join(" "), /not persisted message metadata/);
    const task148 = post100Tasks.find(task => task.number === 148);
    assert.equal(task148.status, "completed");
    assert.equal(task148.checkpoint, "task-148-offline-text-to-speech-provider");
    assert.deepEqual(task148.dependsOn, [128, 140, 141, 144]);
    assert.match(task148.decisions.join(" "), /localService=true/);
    assert.match(task148.validation.join(" "), /174 passed/);
    assert.match(task148.limitations.join(" "), /page-local/);
    const task149 = post100Tasks.find(task => task.number === 149);
    assert.equal(task149.status, "completed");
    assert.equal(task149.checkpoint, "task-149-bounded-local-voice-queue-controls");
    assert.deepEqual(task149.dependsOn, [134, 142, 143, 144, 148]);
    assert.match(task149.decisions.join(" "), /Remote voices remain unavailable/);
    assert.match(task149.validation.join(" "), /19 passed/);
    assert.match(task149.limitations.join(" "), /three pending replies and 16 KiB/);
    const task151 = post100Tasks.find(task => task.number === 151);
    assert.equal(task151.status, "completed");
    assert.equal(task151.checkpoint, "task-151-explicit-screen-capture-provider");
    assert.deepEqual(task151.dependsOn, [144, 150]);
    assert.match(task151.decisions.join(" "), /Electron-owned native chooser/);
    assert.match(task151.validation.join(" "), /1162 passed, 6 skipped/);
    assert.match(task151.limitations.join(" "), /Region selection is not available/);
    const task152 = post100Tasks.find(task => task.number === 152);
    assert.equal(task152.status, "completed");
    assert.equal(task152.checkpoint, "task-152-bounded-optional-image-processing");
    assert.deepEqual(task152.dependsOn, [150]);
    assert.match(task152.decisions.join(" "), /separately installed optional dependency/);
    assert.match(task152.validation.join(" "), /1170 passed, 6 skipped/);
    assert.match(task152.limitations.join(" "), /not a security sandbox/);
    const task144 = post100Tasks.find(task => task.number === 144);
    assert.equal(task144.status, "completed");
    assert.equal(task144.checkpoint, "task-144-emergency-stop-capture-indicators");
    assert.match(task144.validation.join(" "), /165 passed/);
    assert.match(task144.validation.join(" "), /1141 passed, 6 skipped/);
    assert.match(task144.limitations.join(" "), /resets after restart/);
    const task127 = post100Tasks.find(task => task.number === 127);
    assert.equal(task127.status, "completed");
    assert.equal(task127.checkpoint, "task-127-windows-electron-installer");
    assert.match(task127.validation.join(" "), /Windows x64 NSIS package/);
    assert.match(task127.limitations.join(" "), /unsigned local Windows x64 installer/);
    const task124 = post100Tasks.find(task => task.number === 124);
    assert.equal(task124.status, "completed");
    assert.match(task124.validation.join(" "), /Focused inventory.*28 passed/);
    assert.match(task124.limitations.join(" "), /Windows programs/);
    const task125 = post100Tasks.find(task => task.number === 125);
    assert.equal(task125.status, "completed");
    assert.equal(task125.checkpoint, "task-125-managed-vscode-user-lifecycle");
    assert.match(task125.validation.join(" "), /1065 passed, 3 skipped/);
    assert.match(task125.limitations.join(" "), /downgrade\/rollback after update is not treated as verified recovery/);
    const task126 = post100Tasks.find(task => task.number === 126);
    assert.equal(task126.status, "completed");
    assert.equal(task126.checkpoint, "task-126-local-application-lifecycle");
    assert.match(task126.validation.join(" "), /Eleven deterministic lifecycle and credential tests passed/);
    assert.match(task126.limitations.join(" "), /Electron packaging.*Task 127/);
    const task128 = post100Tasks.find(task => task.number === 128);
    assert.equal(task128.status, "completed");
    assert.equal(task128.checkpoint, "task-128-optional-voice-interaction");
    assert.match(task128.validation.join(" "), /1093 passed, 3 skipped/);
    assert.match(task128.limitations.join(" "), /not an enforceable cap on Google's account billing/);
    const task129 = post100Tasks.find(task => task.number === 129);
    assert.equal(task129.status, "completed");
    assert.equal(task129.checkpoint, "task-129-command-center-release-acceptance");
    assert.match(task129.validation.join(" "), /Windows 11 x64/);
    assert.match(task129.validation.join(" "), /206A36D5C94FD76B2696C01F95CD842C24E3A79FD05FEB7FDB45F3DA101DC091/);
    assert.match(task129.limitations.join(" "), /capacity remain UNKNOWN/);
    assert.match(task129.limitations.join(" "), /production completeness/);
    const task131 = post100Tasks.find(task => task.number === 131);
    assert.equal(task131.status, "completed");
    assert.equal(task131.checkpoint, "task-131-supported-packaging-distribution-strategy");
    assert.match(task131.validation.join(" "), /build prerequisites, update source, signing expectations, and recovery limits/);
    assert.match(task131.limitations.join(" "), /Only Windows 11 x64 has local acceptance evidence/);
    const task132 = post100Tasks.find(task => task.number === 132);
    assert.equal(task132.status, "completed");
    assert.equal(task132.checkpoint, "task-132-guided-first-run-setup");
    const task133 = post100Tasks.find(task => task.number === 133);
    assert.equal(task133.status, "completed");
    assert.equal(task133.checkpoint, "task-133-provider-model-setup-guidance");
    assert.match(task133.validation.join(" "), /Next.js static production build/);
    assert.match(task133.limitations.join(" "), /software concurrency only/);
    const task134 = post100Tasks.find(task => task.number === 134);
    assert.equal(task134.status, "deferred");
    assert.match(task134.limitations.join(" "), /no verified first-party pack artifact source/);
    const task135 = post100Tasks.find(task => task.number === 135);
    assert.equal(task135.status, "completed");
    assert.equal(task135.checkpoint, "task-135-semantic-retrieval-evaluation");
    assert.deepEqual(task135.dependsOn, [66, 117, 130]);
    assert.ok(!task135.dependsOn.includes(134));
    assert.deepEqual(task135.decisions, []);
    assert.match(task135.validation.join(" "), /Recall@5 1.0, Precision@5 1.0, MRR 1.0/);
    assert.match(task135.limitations.join(" "), /do not measure relevance quality/);
    assert.match(task132.validation.join(" "), /Next.js static production build/);
    assert.match(task132.limitations.join(" "), /installer signature or package integrity/);
    for (const task of post100Tasks) {
      assert.ok(task.acceptance.length > 0 && task.outOfScope.length > 0);
      assert.ok(Array.isArray(task.decisions));
      assert.ok(task.dependsOn.length > 0 || task.number === 179);
      assert.equal(new Set(task.dependsOn).size, task.dependsOn.length);
      assert.ok(task.dependsOn.every(number => Number.isInteger(number) && number >= 1 && number <= tasks.length && number !== task.number));
      if (task.status === "completed") {
        assert.match(task.checkpoint, /^(?:[a-f0-9]{7,40}|task-[1-9][0-9]*-[a-z][a-z0-9-]*)$/);
        assert.ok(task.validation.length > 0 && task.limitations.length > 0);
      } else {
        assert.equal(task.checkpoint, null);
        if ([175, 176, 177, 178, 179, 180, 182, 183, 184].includes(task.number)) {
          assert.ok(task.validation.length > 0 && task.limitations.length > 0);
        } else {
          assert.deepEqual(task.validation, []);
        }
      }
    }
    assert.match(roadmapRules.completion, /acceptance evidence/);
    assert.match(roadmapRules.decisions, /owner approval/);
    assert.match(roadmapRules.handoff, /Identical|identical/);
    assert.match(roadmapRules.boundaries, /file-based\/read-only/);
  });

  it("records approved future multi-provider, self-maintenance, voice and desktop direction without reopening completed work", () => {
    const byNumber = new Map(post100Tasks.map(task => [task.number, task]));
    assert.equal(byNumber.get(109).status, "completed");
    assert.match(byNumber.get(109).decisions.join(" "), /review-only/);
    assert.match(byNumber.get(112).acceptance.join(" "), /multiple independently identified connections/);
    assert.match(byNumber.get(112).acceptance.join(" "), /configured global\/provider\/model request-slot limits/);
    assert.match(byNumber.get(113).acceptance.join(" "), /local-first/);
    assert.match(byNumber.get(113).acceptance.join(" "), /pre-authorized destination/);
    assert.match(byNumber.get(113).acceptance.join(" "), /two-local\/three-online/);
    assert.match(byNumber.get(116).description, /Three\.js 3D-first/);
    assert.match(byNumber.get(119).acceptance.join(" "), /share a configured provider\/model/);
    assert.match(byNumber.get(122).acceptance.join(" "), /independent review/);
    assert.match(byNumber.get(123).acceptance.join(" "), /owner-approved artifact/);
    assert.match(byNumber.get(126).acceptance.join(" "), /GUI first-run owner setup/);
    assert.match(byNumber.get(127).decisions.join(" "), /Electron 44\.7\.0.*Next\.js 16\.4\.0.*exported statically/);
    assert.match(byNumber.get(128).acceptance.join(" "), /interrupt capture, playback and speech requests/);
    assert.match(byNumber.get(129).acceptance.join(" "), /concurrent local\/online work/);
  });

  it("serves only read methods", async () => {
    const response = await fetch(baseUrl, { method: "POST" });
    assert.equal(response.status, 405);
    assert.equal(response.headers.get("allow"), "GET, HEAD");
  });
});
