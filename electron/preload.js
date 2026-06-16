const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("maxawon", {
  getDefaults: () => ipcRenderer.invoke("app:get-defaults"),
  openChrome: () => ipcRenderer.invoke("app:open-chrome"),
  closeAppChrome: () => ipcRenderer.invoke("app:close-app-chrome"),
  closeAllChrome: () => ipcRenderer.invoke("app:close-all-chrome"),
  pickCaptureOutput: (currentPath) => ipcRenderer.invoke("app:pick-capture-output", currentPath),
  captureTable: (payload) => ipcRenderer.invoke("app:capture-table", payload),
  checkForUpdates: () => ipcRenderer.invoke("app:check-for-updates"),
  downloadUpdate: () => ipcRenderer.invoke("app:download-update"),
  installUpdate: () => ipcRenderer.invoke("app:install-update"),
  onUpdateStatus: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("update:status", listener);
    return () => ipcRenderer.removeListener("update:status", listener);
  },
});
