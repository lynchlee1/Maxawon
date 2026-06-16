const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("maxawon", {
  getDefaults: () => ipcRenderer.invoke("app:get-defaults"),
  openChrome: () => ipcRenderer.invoke("app:open-chrome"),
  closeAppChrome: () => ipcRenderer.invoke("app:close-app-chrome"),
  closeAllChrome: () => ipcRenderer.invoke("app:close-all-chrome"),
  pickCaptureOutput: (currentPath) => ipcRenderer.invoke("app:pick-capture-output", currentPath),
  captureTable: (payload) => ipcRenderer.invoke("app:capture-table", payload),
  pickPptTemplate: () => ipcRenderer.invoke("app:pick-ppt-template"),
  pickPptExcel: () => ipcRenderer.invoke("app:pick-ppt-excel"),
  pickPptOutput: (currentPath) => ipcRenderer.invoke("app:pick-ppt-output", currentPath),
  pickWeeklyMezzOutput: (currentPath) => ipcRenderer.invoke("app:pick-weekly-mezz-output", currentPath),
  pptFetchCompany: (stockCode) => ipcRenderer.invoke("app:ppt-fetch-company", stockCode),
  pptReadExcel: (excelPath) => ipcRenderer.invoke("app:ppt-read-excel", excelPath),
  pptBuildData: (payload) => ipcRenderer.invoke("app:ppt-build-data", payload),
  pptSelectTemplateDir: () => ipcRenderer.invoke("app:ppt-select-template-dir"),
  pptGetGeminiSettings: () => ipcRenderer.invoke("app:ppt-get-gemini-settings"),
  pptSaveGeminiSettings: (settings) => ipcRenderer.invoke("app:ppt-save-gemini-settings", settings),
  pptGenerateGemini: (payload) => ipcRenderer.invoke("app:ppt-generate-gemini", payload),
  generatePpt: (payload) => ipcRenderer.invoke("app:generate-ppt", payload),
  weeklyMezzCollect: (payload) => ipcRenderer.invoke("app:weekly-mezz-collect", payload),
  checkForUpdates: () => ipcRenderer.invoke("app:check-for-updates"),
  downloadUpdate: () => ipcRenderer.invoke("app:download-update"),
  installUpdate: () => ipcRenderer.invoke("app:install-update"),
  onUpdateStatus: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("update:status", listener);
    return () => ipcRenderer.removeListener("update:status", listener);
  },
});
