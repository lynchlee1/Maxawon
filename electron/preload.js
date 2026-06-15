const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("cretop", {
  getDefaults: () => ipcRenderer.invoke("app:get-defaults"),
  openChrome: () => ipcRenderer.invoke("app:open-chrome"),
  closeAppChrome: () => ipcRenderer.invoke("app:close-app-chrome"),
  closeAllChrome: () => ipcRenderer.invoke("app:close-all-chrome"),
  pickCaptureOutput: (currentPath) => ipcRenderer.invoke("app:pick-capture-output", currentPath),
  captureTable: (payload) => ipcRenderer.invoke("app:capture-table", payload),
});
