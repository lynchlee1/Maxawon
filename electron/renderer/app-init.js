async function loadInitialSettings() {
  const defaults = await window.maxawon.getDefaults();
  applySavedFilePaths(defaults.savedFilePaths, defaults);

  const runtimeMessage = pythonRuntimeMessage(defaults.pythonRuntime);
  if (runtimeMessage) addLog(runtimeMessage);

  const weeklyMezzDates = defaultWeeklyMezzDates();
  $("#weeklyMezzFrom").value = weeklyMezzDates.from;
  $("#weeklyMezzTo").value = weeklyMezzDates.to;

  if (defaults.appVersion) {
    setText("#appVersion", `v${defaults.appVersion}`);
    setText("#currentVersion", `v${defaults.appVersion}`);
  }
  setText("#updateFeed", defaults.updateFeed);
  if (!defaults.updatesSupported) {
    setUpdateStatus({ status: "unsupported", message: "앱 업데이트 확인은 패키징된 앱에서만 사용할 수 있습니다." });
  }

  const geminiSettings = await runAction(() => window.maxawon.pptGetGeminiSettings());
  if (geminiSettings) {
    applyGeminiSettings(geminiSettings);
    applyTemplateFiles(geminiSettings);
    applySavedFilePaths(defaults.savedFilePaths, defaults);
  }
}

function bindNavigationEvents() {
  $$(".nav-button").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
  });
  $$(".ppt-tab").forEach((button) => {
    button.addEventListener("click", () => showPptTab(button.dataset.pptTab));
  });
  $$(".prompt-tab").forEach((button) => {
    button.addEventListener("click", () => showPromptPanel(button.dataset.promptTab));
  });
  $$("[data-prompt-step]").forEach((button) => {
    button.addEventListener("click", () => movePromptPanel(Number(button.dataset.promptStep)));
  });
  $$("#ppt-forger .workflow-overview-item").forEach((button) => {
    button.addEventListener("click", () => showPptTab(button.dataset.pptStep));
  });
  $$("[data-ppt-goto]").forEach((button) => {
    button.addEventListener("click", () => showPptTab(button.dataset.pptGoto));
  });
}

function bindSessionEvents() {
  $("#openChrome").addEventListener("click", async () => {
    const result = await runAction(() => window.maxawon.openChrome());
    if (result) addLog(result.message);
  });

  $("#loginDone").addEventListener("click", () => {
    setLogin("연결", true);
    addLog("사용자가 로그인 완료를 확인했습니다.");
    if (state.pendingCapture && !state.captureRunning) {
      runCapture(state.pendingCapture, true);
    }
  });

  $("#closeAppChrome").addEventListener("click", async () => {
    const result = await runAction(() => window.maxawon.closeAppChrome());
    if (!result) return;
    setLogin("미연결", false);
    addLog(result.message);
  });

  $("#closeAllChrome").addEventListener("click", async () => {
    const confirmed = window.confirm("사용자가 직접 연 Chrome까지 모두 종료합니다. 계속할까요?");
    if (!confirmed) return;

    const result = await runAction(() => window.maxawon.closeAllChrome());
    if (!result) return;
    setLogin("미연결", false);
    addLog(result.message);
  });
}

function bindCaptureEvents() {
  $("#pickOutput").addEventListener("click", async () => {
    const selected = await runAction(() => window.maxawon.pickCaptureOutput(state.captureOutput));
    if (!selected) return;
    state.captureOutput = selected;
    $("#captureOutput").value = selected;
    addLog(`조건검색 저장 파일을 변경했습니다: ${selected}`);
  });

  $("#captureTable").addEventListener("click", async () => {
    if (!state.loginDone) {
      window.alert("Maxawon에 로그인한 뒤 '로그인 완료'를 누르세요.");
      return;
    }

    const maxPagesValue = $("#maxPages").value.trim();
    const maxPages = maxPagesValue === "" ? null : Number(maxPagesValue);
    if (maxPages !== null && (!Number.isInteger(maxPages) || maxPages < 1)) {
      window.alert("최대 페이지는 1 이상의 숫자로 입력하세요.");
      return;
    }

    await runCapture({
      maxPages,
      outputPath: state.captureOutput,
    });
  });
}

function bindWeeklyMezzEvents() {
  $("#pickWeeklyMezzOutput").addEventListener("click", async () => {
    const selected = await runAction(() => window.maxawon.pickWeeklyMezzOutput(state.weeklyMezzOutput));
    if (!selected) return;
    state.weeklyMezzOutput = selected;
    $("#weeklyMezzOutput").value = selected;
    addLog(`주간 메자닌 발행현황 저장 파일을 변경했습니다: ${selected}`);
  });

  $("#runWeeklyMezz").addEventListener("click", async () => {
    await runWeeklyMezz();
  });
}

function bindPptEvents() {
  $("#pickPptTemplate").addEventListener("click", async () => {
    const selected = await runAction(() => window.maxawon.pickPptTemplate());
    if (!selected) return;
    state.pptTemplatePath = selected;
    $("#pptTemplate").value = selected;
    addLog(`PPT 템플릿을 선택했습니다: ${selected}`);
  });

  $("#pickPptTemplateDir").addEventListener("click", async () => {
    const selected = await runAction(() => window.maxawon.pptSelectTemplateDir());
    if (!selected) return;
    applyTemplateFiles(selected);
    addLog(`PPT Forger 템플릿 폴더를 선택했습니다: ${selected.templateDir}`);
    if (!selected.modelPath) addLog("선택한 폴더에서 Model.xlsx를 찾지 못했습니다.");
    if (!selected.templatePath) addLog("선택한 폴더에서 deal-summary.pptx를 찾지 못했습니다.");
  });

  $("#pickPptExcel").addEventListener("click", async () => {
    const selected = await runAction(() => window.maxawon.pickPptExcel());
    if (!selected) return;
    state.pptExcelPath = selected;
    state.pptExcelData = null;
    $("#pptExcel").value = selected;
    addLog(`PPT Forger 엑셀 파일을 선택했습니다: ${selected}`);
  });

  $("#pickPptOutput").addEventListener("click", async () => {
    const selected = await runAction(() => window.maxawon.pickPptOutput(state.pptOutputPath));
    if (!selected) return;
    state.pptOutputPath = selected;
    $("#pptOutput").value = selected;
    addLog(`PPT 저장 파일을 변경했습니다: ${selected}`);
  });

  $("#buildPptData").addEventListener("click", async () => {
    await buildPptData();
  });
  $("#generateGeminiText").addEventListener("click", async () => {
    await generateGeminiText();
  });
  $("#generatePpt").addEventListener("click", generatePptFromUi);
}

function bindPptSettingsEvents() {
  $("#openPptSettings").addEventListener("click", () => {
    setPptSettingsOpen(true);
  });
  $("#closePptSettings").addEventListener("click", () => {
    setPptSettingsOpen(false);
  });
  $("#pptSettingsOverlay").addEventListener("click", (event) => {
    if (event.target === $("#pptSettingsOverlay")) {
      setPptSettingsOpen(false);
    }
  });
  $("#saveGeminiSettings").addEventListener("click", async () => {
    const result = await runAction(() => window.maxawon.pptSaveGeminiSettings(buildGeminiSettings()));
    if (!result) return;
    applyTemplateFiles(result);
    addLog("Gemini 설정을 저장했습니다.");
    setPptSettingsOpen(false);
  });
}

async function generatePptFromUi() {
  if (state.pptRunning) return;
  if (!state.pptTemplatePath) {
    window.alert("PPT 템플릿을 선택하세요.");
    return;
  }
  if (!state.pptOutputPath) {
    window.alert("PPT 저장 파일을 선택하세요.");
    return;
  }

  const data = await buildPptData("review");
  if (!data) return;
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    window.alert("치환 데이터는 JSON 객체여야 합니다.");
    return;
  }

  state.pptRunning = true;
  $("#generatePpt").disabled = true;
  addLog("PPT 생성을 시작합니다.");
  try {
    const result = await window.maxawon.generatePpt({
      templatePath: state.pptTemplatePath,
      outputPath: state.pptOutputPath,
      data,
    });
    addLog(`PPT를 저장했습니다: ${result.outputPath}`);
  } catch (error) {
    addLog(error.message);
    window.alert(error.message);
  } finally {
    state.pptRunning = false;
    $("#generatePpt").disabled = false;
  }
}

function bindUpdateEvents() {
  window.maxawon.onUpdateStatus((payload) => {
    setUpdateStatus(payload);
    addLog(payload.message);
  });

  $("#checkUpdates").addEventListener("click", async () => {
    state.updateAvailable = false;
    state.updateDownloaded = false;
    $("#downloadUpdate").disabled = true;
    $("#installUpdate").disabled = true;

    const result = await runAction(() => window.maxawon.checkForUpdates());
    if (!result) return;
    setUpdateStatus(result);
    addLog(result.message);
  });

  $("#downloadUpdate").addEventListener("click", async () => {
    const result = await runAction(() => window.maxawon.downloadUpdate());
    if (!result) return;
    setUpdateStatus(result);
    addLog(result.message);
  });

  $("#installUpdate").addEventListener("click", async () => {
    const confirmed = window.confirm("앱을 재시작하고 다운로드된 업데이트를 설치할까요?");
    if (!confirmed) return;

    const result = await runAction(() => window.maxawon.installUpdate());
    if (!result) return;
    setUpdateStatus(result);
    addLog(result.message);
  });
}

function bindLogEvents() {
  $("#clearLog").addEventListener("click", () => {
    $("#logs").replaceChildren();
  });
}

function bindEvents() {
  bindNavigationEvents();
  bindSessionEvents();
  bindCaptureEvents();
  bindWeeklyMezzEvents();
  bindPptEvents();
  bindPptSettingsEvents();
  bindUpdateEvents();
  bindLogEvents();
}

async function init() {
  renderPageInfo();
  await loadInitialSettings();
  bindEvents();
  addLog("Chrome을 열고 직접 로그인한 뒤 '로그인 완료'를 누르세요.");
}

init();
