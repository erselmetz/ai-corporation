export async function loadAgentAssignmentImpact(agentId, fetchImpl = globalThis.fetch) {
  const paths = [
    "/api/tasks",
    "/api/chat/conversations",
    "/api/employee-chat/conversations",
  ];
  const results = await Promise.all(paths.map(async (path) => {
    const response = await fetchImpl(path, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      const reason = response.status === 401
        ? "Sign in through local owner access"
        : response.status === 403
          ? "This session cannot read affected-work details"
          : "Could not load affected work";
      const error = new Error(`${reason}; no assignment was changed.`);
      error.status = response.status;
      throw error;
    }
    return response.json();
  }));
  const [tasks, coordinatorChats, employeeChats] = results;
  if (
    !Array.isArray(tasks.items) ||
    !Array.isArray(coordinatorChats.items) ||
    !Array.isArray(employeeChats.items)
  ) {
    throw new Error("Affected-work data was invalid; no assignment was changed.");
  }
  const assignedTasks = tasks.items.filter((item) => item.assigned_agent === agentId);
  const coordinatorConversations = coordinatorChats.items.filter(
    (item) => item.coordinator?.id === agentId,
  );
  const employeeConversations = employeeChats.items.filter(
    (item) => item.agent?.id === agentId,
  );
  return {
    taskCount: assignedTasks.length,
    runningTaskCount: assignedTasks.filter((item) => item.status === "running").length,
    coordinatorConversationCount: coordinatorConversations.length,
    employeeConversationCount: employeeConversations.length,
    openEmployeeConversationCount: employeeConversations.filter(
      (item) => item.status === "open",
    ).length,
  };
}

export function assignmentImpactText(impact) {
  return [
    `Assigned Tasks: ${impact.taskCount} (${impact.runningTaskCount} running).`,
    `Coordinator conversations: ${impact.coordinatorConversationCount}.`,
    `Individual Employee conversations: ${impact.employeeConversationCount} (${impact.openEmployeeConversationCount} open).`,
    "Task ownership is unchanged. Active Agent calls block reassignment; existing conversations keep their snapshot and must be reopened under a changed assignment.",
  ].join(" ");
}
