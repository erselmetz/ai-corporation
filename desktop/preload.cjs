const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopBridge", Object.freeze({
  getWorkspaceState: () => ipcRenderer.invoke("desktop:workspace-state"),
  saveWorkspaceState: (value) => ipcRenderer.invoke("desktop:workspace-save", value),
  getSetupState: () => ipcRenderer.invoke("desktop:get-setup-state"),
  isOllamaInstalled: () => ipcRenderer.invoke("desktop:ollama-installed"),
  start: (password, confirmation) => ipcRenderer.invoke("desktop:start", { password, confirmation }),
  readCrashReports: () => ipcRenderer.invoke("desktop:read-crash-reports"),
  openDiagnosticsFolder: () => ipcRenderer.invoke("desktop:open-diagnostics-folder"),
  resetAppData: () => ipcRenderer.invoke("desktop:reset-app-data"),
  requestMicrophone: () => ipcRenderer.invoke("desktop:request-microphone"),
  requestCamera: () => ipcRenderer.invoke("desktop:request-camera"),
  previewOllamaInstaller: () => ipcRenderer.invoke("desktop:ollama-installer-preview"),
  installOllama: (preview) => ipcRenderer.invoke("desktop:ollama-installer-install", preview),
  onOllamaInstallerProgress: (callback) => {
    if (typeof callback !== "function") return () => {};
    const listener = (_event, progress) => callback({
      downloaded: Number(progress?.downloaded) || 0,
      total: Number(progress?.total) || 0,
    });
    ipcRenderer.on("desktop:ollama-installer-progress", listener);
    return () => ipcRenderer.removeListener("desktop:ollama-installer-progress", listener);
  },
  onStartupState: (callback) => {
    if (typeof callback !== "function") return () => {};
    const listener = (_event, message) => callback(String(message).slice(0, 180));
    ipcRenderer.on("desktop:startup-state", listener);
    return () => ipcRenderer.removeListener("desktop:startup-state", listener);
  },
}));
