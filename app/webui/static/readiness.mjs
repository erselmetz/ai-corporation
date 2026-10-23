import { formatDetails } from "./ui-details.mjs";

const state = document.querySelector("#readiness-state");
const report = document.querySelector("#readiness-report");

document.querySelector("#readiness-refresh").addEventListener("click", async () => {
  state.textContent = "Reading local evidence…";
  report.textContent = "";
  try {
    const response = await fetch("/api/local/readiness", {
      credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json" },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "Local readiness evidence could not be read.");
    report.textContent = formatDetails(body);
    state.textContent = "Snapshot refreshed. UNKNOWN values mean no supported evidence was available.";
  } catch (error) {
    state.textContent = error.message;
  }
});
