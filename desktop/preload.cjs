const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopBridge", Object.freeze({
  getSetupState: () => ipcRenderer.invoke("desktop:get-setup-state"),
  start: (password, confirmation) => ipcRenderer.invoke("desktop:start", { password, confirmation }),
  onStartupState: (callback) => {
    if (typeof callback !== "function") return () => {};
    const listener = (_event, message) => callback(String(message).slice(0, 180));
    ipcRenderer.on("desktop:startup-state", listener);
    return () => ipcRenderer.removeListener("desktop:startup-state", listener);
  },
}));
