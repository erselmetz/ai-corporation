const form = document.querySelector("#start-form");
const state = document.querySelector("#state");
const button = document.querySelector("#start-button");
const password = document.querySelector("#password");
const confirmation = document.querySelector("#confirmation");
const confirmationWrap = document.querySelector("#confirmation-wrap");
const heading = document.querySelector("#heading");
const intro = document.querySelector("#intro");

if (!window.desktopBridge) {
  state.textContent = "Secure desktop startup is unavailable. Close this app and contact the administrator.";
  button.disabled = true;
} else {
  window.desktopBridge.getSetupState().then((isFirstRun) => {
    if (!isFirstRun) {
      confirmationWrap.hidden = true;
      confirmation.required = false;
      password.autocomplete = "current-password";
      heading.textContent = "Welcome back";
      intro.textContent = "Enter your owner password to start the private local services.";
      button.firstChild.textContent = "Start local app ";
    }
  });
  window.desktopBridge.onStartupState((message) => { state.textContent = message; });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  state.textContent = "Starting the local services…";
  button.disabled = true;
  try {
    const result = await window.desktopBridge.start(password.value, confirmation.value);
    if (!result.started) state.textContent = result.message;
  } catch {
    state.textContent = "The local app could not start. Check that another ERSELMETZ AI controller is closed and try again.";
  } finally {
    password.value = "";
    confirmation.value = "";
    button.disabled = false;
  }
});
