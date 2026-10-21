const fields = {
  response_mode: "preference-mode", locale: "preference-locale", detail_level: "preference-detail",
  autonomy_level: "preference-autonomy",
  voice_mode: "preference-voice-mode", voice_language: "preference-voice-language", voice_id: "preference-voice-id",
};
const form = document.querySelector("#preferences-form");
const state = document.querySelector("#preferences-state");
const csrf = async () => {
  const response = await fetch("/api/local/session", { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new Error("Sign in through Owner sign-in to manage preferences.");
  return (await response.json()).csrf;
};
const show = preferences => {
  for (const [key, id] of Object.entries(fields)) document.getElementById(id).value = preferences[key] ?? "";
};
async function load() {
  try {
    const response = await fetch("/api/local/preferences", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error(response.status === 401 ? "Sign in through Owner sign-in to manage preferences." : "Preferences could not be loaded.");
    const payload = await response.json(); show(payload.preferences);
    document.querySelector("#preferences-retention").textContent = payload.retention;
    state.textContent = "Preferences loaded. Autonomy never changes permissions or consent.";
  } catch (error) { state.textContent = error.message; }
}
form.addEventListener("submit", async event => {
  event.preventDefault();
  try {
    const headers = { "Content-Type": "application/json", "X-Local-CSRF": await csrf() };
    const body = Object.fromEntries(Object.entries(fields).map(([key, id]) => [key, document.getElementById(id).value]));
    const response = await fetch("/api/local/preferences", { method: "PUT", credentials: "same-origin", headers, body: JSON.stringify(body) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Preferences could not be saved.");
    show(payload.preferences); state.textContent = "Preferences saved. No permissions, assignments, or consent changed.";
  } catch (error) { state.textContent = error.message; }
});
document.querySelector("#preferences-reset").addEventListener("click", async () => {
  try {
    const response = await fetch("/api/local/preferences/reset", { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Local-CSRF": await csrf() }, body: "{}" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Preferences could not be reset.");
    show(payload.preferences); state.textContent = "Preferences reset to defaults. Capability permissions and consent are unchanged.";
  } catch (error) { state.textContent = error.message; }
});
document.querySelector("#preferences-export").addEventListener("click", async event => {
  event.preventDefault();
  try {
    const response = await fetch(event.currentTarget.href, { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) throw new Error(response.status === 401 ? "Sign in through Owner sign-in to export preferences." : "Preferences could not be exported.");
    const blob = await response.blob(); const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url; link.download = "erselmetz-ai-preferences.json"; link.click(); URL.revokeObjectURL(url);
    state.textContent = "Presentation preferences exported. No chat content or credentials are included.";
  } catch (error) { state.textContent = error.message; }
});
void load();
