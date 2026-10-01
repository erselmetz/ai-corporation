const states = new Map([
  ["pending", "Pending: execution has not started."],
  ["running", "Running: task execution is in progress."],
  ["completed", "Completed: task execution finished successfully."],
  ["failed", "Failed: task execution did not complete successfully."],
]);

export function mountTaskProgress({ documentRef, fetchImpl }) {
  const panel = documentRef.getElementById("task-progress");
  const state = documentRef.getElementById("task-progress-state");
  const taskInput = documentRef.getElementById("activity-task-id");
  const refresh = documentRef.getElementById("activity-refresh");
  if (!panel || !state || !taskInput || !refresh) return null;
  let revision = 0;

  async function loadProgress() {
    const current = ++revision;
    const taskId = taskInput.value.trim();
    panel.replaceChildren();
    state.textContent = taskId ? "Loading Task progress…" : "Enter a Task ID above and refresh to inspect current progress.";
    if (!taskId) return false;
    try {
      const response = await fetchImpl(`/api/tasks/${encodeURIComponent(taskId)}`, {
        credentials: "same-origin", headers: { Accept: "application/json" },
      });
      if (current !== revision) return false;
      if (!response.ok) {
        state.textContent = response.status === 401 ? "Sign-in required to read Task progress."
          : response.status === 403 ? "Task progress requires task:read permission."
          : response.status === 404 ? "Task not found."
          : "Task progress could not be loaded. Please retry.";
        return false;
      }
      const task = await response.json();
      if (current !== revision) return false;
      if (!task || task.id !== taskId || !states.has(task.status)
          || !(task.assigned_agent === null || typeof task.assigned_agent === "string")) {
        state.textContent = "Task progress response was invalid.";
        return false;
      }
      const heading = documentRef.createElement("h3");
      heading.textContent = `Task ${task.id}`;
      const progress = documentRef.createElement("p");
      progress.textContent = states.get(task.status);
      const agent = documentRef.createElement("p");
      agent.textContent = `Assigned Agent: ${task.assigned_agent ?? "Not assigned"}`;
      panel.append(heading, progress, agent);
      state.textContent = "Current lifecycle snapshot. Refresh to check for changes; no percentage or provider telemetry is available.";
      return true;
    } catch {
      if (current === revision) state.textContent = "Task progress could not be loaded. Please retry.";
      return false;
    }
  }
  refresh.addEventListener("click", () => void loadProgress());
  taskInput.addEventListener("input", () => {
    ++revision;
    panel.replaceChildren();
    state.textContent = "Task selection changed. Refresh to inspect current progress.";
  });
  const initialLoad = loadProgress();
  return { initialLoad, loadProgress };
}
