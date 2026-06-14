const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("cretop", {
  getDefaults: () => ipcRenderer.invoke("app:get-defaults"),
  openChrome: () => ipcRenderer.invoke("app:open-chrome"),
  checkScrapling: () => ipcRenderer.invoke("app:check-scrapling"),
  pickExcel: () => ipcRenderer.invoke("app:pick-excel"),
  pickCaptureOutput: (currentPath) => ipcRenderer.invoke("app:pick-capture-output", currentPath),
  captureTable: (payload) => ipcRenderer.invoke("app:capture-table", payload),
});
