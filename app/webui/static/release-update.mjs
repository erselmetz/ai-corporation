function setState(element, message, kind = "") {
  element.textContent = message;
  element.className = `section-state ${kind}`.trim();
}

function validRelease(value) {
  return Boolean(value && typeof value === "object"
    && typeof value.version === "string" && /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(value.version)
    && typeof value.available === "boolean"
    && typeof value.release_notes === "string" && value.release_notes.length <= 12000
    && typeof value.installer_name === "string" && /^ERSELMETZ-AI-Setup-\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?-win-x64\.exe$/.test(value.installer_name)
    && typeof value.installer_sha256 === "string" && /^[a-f0-9]{64}$/.test(value.installer_sha256)
    && Number.isInteger(value.from_configuration) && Number.isInteger(value.to_configuration)
    && typeof value.migration_preview === "string" && value.migration_preview.length <= 1200);
}

export function mountReleaseUpdatePage({ documentRef = globalThis.document, fetchImpl = globalThis.fetch } = {}) {
  const check = documentRef.getElementById("release-check");
  const state = documentRef.getElementById("release-state");
  const preview = documentRef.getElementById("release-preview");
  const version = documentRef.getElementById("release-version");
  const notes = documentRef.getElementById("release-notes");
  const migration = documentRef.getElementById("release-migration");
  const prepare = documentRef.getElementById("release-prepare");
  const prepareState = documentRef.getElementById("release-prepare-state");
  if (![check, state, preview, version, notes, migration, prepare, prepareState].every(Boolean)) return null;
  let checkedRelease = null;
  let busy = false;

  async function checkRelease() {
    if (busy) return false;
    busy = true;
    check.disabled = true;
    prepare.disabled = true;
    preview.hidden = true;
    checkedRelease = null;
    setState(state, "Checking the signed release…");
    try {
      const response = await fetchImpl("/api/updates/release", { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!response.ok) {
        setState(state, response.status === 401 ? "Sign in to check releases." : response.status === 403 ? "This account cannot inspect releases." : "The trusted release check failed.", "error-state");
        return false;
      }
      const result = await response.json();
      if (!validRelease(result)) { setState(state, "The signed release response was invalid.", "error-state"); return false; }
      checkedRelease = result;
      version.textContent = `Version ${result.version}${result.available ? " is available" : " is already installed or older"}`;
      notes.textContent = result.release_notes;
      migration.textContent = `Configuration ${result.from_configuration} → ${result.to_configuration}. ${result.migration_preview}`;
      preview.hidden = false;
      setState(state, result.available ? "Signature and release origin verified." : "Signature verified; no newer release is available.", "success-state");
      if (result.available) {
        try {
          const session = await fetchImpl("/api/local/session", { credentials: "same-origin", headers: { Accept: "application/json" } });
          const sessionData = session.ok ? await session.json() : null;
          prepare.disabled = !Array.isArray(sessionData?.permissions) || !sessionData.permissions.includes("updates:manage");
          if (prepare.disabled) setState(prepareState, "Preparing a verified installer requires updates:manage permission.");
        } catch { prepare.disabled = true; }
      }
      return true;
    } catch {
      setState(state, "The trusted release check failed.", "error-state");
      return false;
    } finally {
      busy = false;
      check.disabled = false;
    }
  }

  async function prepareRelease() {
    if (busy || !checkedRelease?.available || prepare.disabled) return false;
    busy = true;
    prepare.disabled = true;
    setState(prepareState, "Downloading and verifying the installer, then creating a database backup…");
    try {
      const sessionResponse = await fetchImpl("/api/local/session", { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!sessionResponse.ok) throw new Error("Sign in again before preparing an update.");
      const session = await sessionResponse.json();
      const response = await fetchImpl("/api/updates/release/prepare", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Local-CSRF": session.csrf },
        body: JSON.stringify({ version: checkedRelease.version }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "The release could not be prepared safely.");
      setState(prepareState, `${result.message} Installer: ${result.installer_path}. Recovery backup: ${result.backup_path}. SHA-256: ${result.installer_sha256}`, "success-state");
      return true;
    } catch (error) {
      setState(prepareState, error instanceof Error ? error.message : "The release could not be prepared safely.", "error-state");
      return false;
    } finally {
      busy = false;
      prepare.disabled = !checkedRelease?.available;
    }
  }

  check.addEventListener("click", () => void checkRelease());
  prepare.addEventListener("click", () => void prepareRelease());
  return { checkRelease, prepareRelease };
}
