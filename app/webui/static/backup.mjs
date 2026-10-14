const state = document.querySelector("#backup-state");
const previewOutput = document.querySelector("#backup-preview-result");
const inspectOutput = document.querySelector("#backup-inspect-result");
const privateToggle = document.querySelector("#backup-private");
const fileInput = document.querySelector("#backup-file");
let verifiedFile = null;
let verifiedPassphrase = null;

async function csrf() {
  const response = await fetch("/api/local/session", { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new Error("Sign in with the local owner account first.");
  return (await response.json()).csrf;
}

async function jsonResponse(response, fallback) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || fallback);
  return payload;
}

function readable(payload) {
  return JSON.stringify(payload, null, 2);
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.querySelector("#diagnostics-export").addEventListener("click", async () => {
  state.textContent = "Preparing safe diagnostic metadata…";
  try {
    const response = await fetch("/api/local/backup/diagnostics", { credentials: "same-origin", cache: "no-store" });
    if (!response.ok) await jsonResponse(response, "Diagnostics could not be exported.");
    download(await response.blob(), "erselmetz-ai-diagnostics.json");
    state.textContent = "Safe diagnostic metadata exported. No records, paths, logs, credentials, providers, or hardware claims are included.";
  } catch (error) { state.textContent = error.message; }
});

function selectedFile() {
  const file = fileInput.files?.[0];
  const passphrase = document.querySelector("#restore-passphrase").value;
  if (!file) throw new Error("Choose a backup file first.");
  if (file.size > 72 * 1024 * 1024) throw new Error("Backup file exceeds the 72 MiB limit.");
  if (passphrase.length < 12 || passphrase.length > 1024) throw new Error("Enter the backup passphrase (12–1024 characters).");
  return { file, passphrase };
}

fileInput.addEventListener("change", () => {
  verifiedFile = null;
  verifiedPassphrase = null;
  inspectOutput.textContent = "";
});

document.querySelector("#backup-preview").addEventListener("click", async () => {
  state.textContent = "Preparing data preview…";
  try {
    const response = await fetch(`/api/local/backup/preview?include_private_data=${privateToggle.checked}`, {
      credentials: "same-origin", cache: "no-store",
    });
    const result = await jsonResponse(response, "Backup preview is unavailable.");
    previewOutput.textContent = readable(result);
    state.textContent = "Preview ready. No data was exported.";
  } catch (error) { state.textContent = error.message; }
});

document.querySelector("#backup-export").addEventListener("click", async () => {
  const passphrase = document.querySelector("#backup-passphrase").value;
  if (passphrase.length < 12 || passphrase.length > 1024) {
    state.textContent = "Enter a passphrase between 12 and 1024 characters.";
    return;
  }
  state.textContent = "Encrypting the selected local data…";
  try {
    const response = await fetch("/api/local/backup/export", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Local-CSRF": await csrf() },
      body: JSON.stringify({ passphrase, include_private_data: privateToggle.checked }),
    });
    if (!response.ok) await jsonResponse(response, "Backup could not be created.");
    const blob = await response.blob();
    const filename = `erselmetz-ai-${new Date().toISOString().replaceAll(":", "-")}.erselbackup`;
    if (typeof window.showSaveFilePicker === "function") {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [{ description: "ERSELMETZ AI encrypted backup", accept: { "application/vnd.erselmetz.backup": [".erselbackup"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
    } else {
      download(blob, filename);
    }
    state.textContent = "Encrypted backup created. Keep the file and passphrase safe; the app cannot recover the passphrase.";
  } catch (error) {
    if (error.name !== "AbortError") state.textContent = error.message;
  }
});

document.querySelector("#backup-inspect").addEventListener("click", async () => {
  try {
    const selected = selectedFile();
    const form = new FormData();
    form.set("file", selected.file);
    form.set("passphrase", selected.passphrase);
    const response = await fetch("/api/local/backup/inspect", {
      method: "POST", credentials: "same-origin",
      headers: { "X-Local-CSRF": await csrf() }, body: form,
    });
    const result = await jsonResponse(response, "Backup could not be verified.");
    inspectOutput.textContent = readable(result);
    verifiedFile = selected.file;
    verifiedPassphrase = selected.passphrase;
    state.textContent = "Backup integrity and restore compatibility verified. No data was changed.";
  } catch (error) {
    verifiedFile = null;
    verifiedPassphrase = null;
    state.textContent = error.message;
  }
});

document.querySelector("#backup-restore").addEventListener("click", async () => {
  try {
    const selected = selectedFile();
    if (verifiedFile !== selected.file || verifiedPassphrase !== selected.passphrase) {
      throw new Error("Verify this exact file and passphrase before restoring.");
    }
    if (document.querySelector("#restore-confirmation").value !== "RESTORE") {
      throw new Error("Type RESTORE to confirm replacement of the supported app data.");
    }
    if (!window.confirm("Restore this verified backup? A local encrypted pre-restore copy will be created, and the app must restart.")) return;
    const form = new FormData();
    form.set("file", selected.file);
    form.set("passphrase", selected.passphrase);
    form.set("confirmation", "RESTORE");
    const response = await fetch("/api/local/backup/restore", {
      method: "POST", credentials: "same-origin",
      headers: { "X-Local-CSRF": await csrf() }, body: form,
    });
    const result = await jsonResponse(response, "Restore could not be applied.");
    state.textContent = `Restore verified and applied. Encrypted recovery copy: ${result.recovery_copy}. Restart ERSELMETZ AI before continuing.`;
  } catch (error) { state.textContent = error.message; }
});
