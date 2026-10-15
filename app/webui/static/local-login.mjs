const form = document.querySelector("#local-login");
const password = document.querySelector("#password");
const state = document.querySelector("#login-state");
function returnDestination() {
  const origin = window.location.origin;
  if (!origin) return "/ui";
  const requested = new URLSearchParams(window.location.search ?? "").get("next");
  const candidate = requested ?? document.referrer;
  if (!candidate) return "/ui";
  try {
    const target = new URL(candidate, origin);
    if (target.origin !== origin || target.username || target.password) return "/ui";
    if (target.pathname === "/ui/login") return "/ui";
    if (target.pathname === "/ui" || target.pathname.startsWith("/ui/")
        || target.pathname === "/desktop/" || target.pathname === "/desktop/settings/") {
      return target.pathname + target.search + target.hash;
    }
  } catch { /* Invalid destinations return to Home. */ }
  return "/ui";
}
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button");
  if (button.disabled) return;
  button.disabled = true;
  state.textContent = "Signing in…";
  try {
    const request = fetch("/api/local/login", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: password.value }),
    });
    password.value = "";
    const response = await request;
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail ?? "Sign-in failed");
    window.location.assign(returnDestination());
  } catch (error) {
    state.textContent = error.message;
  } finally {
    password.value = "";
    button.disabled = false;
  }
});
document.querySelector("#local-logout").addEventListener("click", async () => {
  try {
    const session = await fetch("/api/local/session", { credentials: "same-origin" });
    if (!session.ok) throw new Error("You are signed out");
    const { csrf } = await session.json();
    const response = await fetch("/api/local/logout", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Local-CSRF": csrf },
      body: "{}",
    });
    if (!response.ok) throw new Error("Sign-out failed");
    state.textContent = "Signed out";
  } catch (error) { state.textContent = error.message; }
});
