# Task 229b - native management windows

Dedicated native Owner access and encrypted Backup/restore windows; native Providers/Free pool/Gemini, Agents, Approvals, Activity and Updates controls. Reusable declarative searchable table/detail/action forms for Tier2 and remaining management records. Markdown renders offline with external resource loading and hyperlink opening disabled. Native dialogs share theme/DPI/keyboard controls and singleton focus. No web engine dependency or size cost.

Checks: 17 passed in 54.32 seconds (native page/search/details/action cancel and confirmation/secret clearing, Settings/Advanced browser tripwires, shell and cloud review). Six fresh Qt processes produced 312 screenshots: 26 windows x two sizes x light/dark x DPI 100/125/150. Local artifacts: task229-review/screenshots/*/matrix.json. Screenshot contents are deterministic fixtures, not live-provider evidence. Visually inspected Providers dark125 and Owner access light150; scrollable actions and long Taglish text remain accessible.

No automatic downloads/tests/updates on window open. Explicit forms dispatch existing guarded handlers. Owner lock synchronously stops protected work before removing client authority; unlock verifies the owner credential and does not resume stopped operations automatically. Live owner lock end-to-end, backup file UI and provider workflows need final phase checks; screenshot existence alone does not verify them.

At this checkpoint native transport still uses the existing loopback listener. Phase C removes it, app HTML and browser-only test assets after accounting. No push/deploy.
