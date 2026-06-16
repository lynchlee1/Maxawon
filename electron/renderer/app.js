const state = {
  loginDone: false,
  captureOutput: "",
  pendingCapture: null,
  captureRunning: false,
  weeklyMezzOutput: "",
  weeklyMezzRunning: false,
  pptTemplateDir: "",
  pptTemplatePath: "",
  pptExcelPath: "",
  pptOutputPath: "",
  pptRunning: false,
  pptCompanyInfo: null,
  pptExcelData: null,
  pptData: null,
  geminiRunning: false,
  updateAvailable: false,
  updateDownloaded: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const PPT_STEPS = ["source", "shareholders", "copy", "review"];
const PROMPT_PANELS = ["investment", "price", "risk"];

const PAGE_INFO = {
  session: [],
  capture: [],
  weeklyMezz: [
    {
      type: "boundary",
      title: "수집 기준",
      items: [
        ["대상", "KIND의 주권 관련 사채권 발행 공시 중 전환사채, 교환사채, 신주인수권부사채 발행 건만 저장합니다."],
        ["옵션/리픽싱", "KIND HTML 수집을 사용하되, 옵션 일정과 리픽싱 한도는 기존 안정 파서의 컬럼 계약을 함께 보존합니다."],
      ],
    },
  ],
  ppt: [],
  updates: [
    {
      type: "steps",
      title: "사용 방법",
      items: ["새 버전을 확인합니다.", "있으면 다운로드합니다.", "재시작 후 설치합니다."],
    },
  ],
};

function setText(selector, value) {
  $(selector).textContent = value;
}

function appendText(parent, text) {
  const parts = text.split(/(\{\{[^}]+\}\})/g).filter(Boolean);
  parts.forEach((part) => {
    const node = part.startsWith("{{") && part.endsWith("}}") ? document.createElement("code") : document.createTextNode(part);
    node.textContent = part;
    parent.append(node);
  });
}

function createInfoSection(section) {
  const element = document.createElement(section.collapsed ? "details" : "section");
  element.className = `page-section ${section.type === "steps" ? "guide-section" : "boundary-section"}`;
  if (section.collapsed) {
    const summary = document.createElement("summary");
    summary.textContent = section.title;
    element.append(summary);
  } else {
    const heading = document.createElement("h3");
    heading.textContent = section.title;
    element.append(heading);
  }

  if (section.type === "steps") {
    const list = document.createElement("ol");
    section.items.forEach((text) => {
      const item = document.createElement("li");
      appendText(item, text);
      list.append(item);
    });
    element.append(list);
    return element;
  }

  const list = document.createElement("dl");
  list.className = "boundary-list";
  section.items.forEach(([term, description]) => {
    const item = document.createElement("div");
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = term;
    appendText(dd, description);
    item.append(dt, dd);
    list.append(item);
  });
  element.append(list);
  return element;
}

function renderPageInfo() {
  $$("[data-info]").forEach((slot) => {
    const fragment = document.createDocumentFragment();
    PAGE_INFO[slot.dataset.info].forEach((section) => {
      fragment.append(createInfoSection(section));
    });
    slot.replaceWith(fragment);
  });
}

function addLog(message) {
  const logs = $("#logs");
  const item = document.createElement("li");
  const time = document.createElement("time");
  const body = document.createElement("span");
  time.textContent = new Date().toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  body.textContent = message;
  item.append(time, body);
  logs.append(item);
  logs.scrollTop = logs.scrollHeight;
}

function setLogin(_message, done = false) {
  state.loginDone = done;
}

function showView(name) {
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === name));
  $$(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });
}

function setPptSettingsOpen(open) {
  $("#pptSettingsOverlay").classList.toggle("hidden", !open);
  $("#pptSettingsOverlay").setAttribute("aria-hidden", String(!open));
}

function showPptTab(name) {
  const activeIndex = PPT_STEPS.indexOf(name);
  $$(".ppt-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.pptTab === name);
    button.setAttribute("aria-selected", String(button.dataset.pptTab === name));
  });
  $$(".ppt-tab-panel").forEach((panel) => {
    const isActive = panel.dataset.pptPanel === name;
    panel.classList.toggle("active", isActive);
    panel.hidden = !isActive;
  });
  $$("#ppt-forger .workflow-overview-item").forEach((button) => {
    const stepIndex = PPT_STEPS.indexOf(button.dataset.pptStep);
    const isActive = button.dataset.pptStep === name;
    button.classList.toggle("active", isActive);
    button.classList.toggle("complete", activeIndex > stepIndex);
    button.setAttribute("aria-current", isActive ? "step" : "false");
  });
}

function showPromptPanel(name) {
  if (!PROMPT_PANELS.includes(name)) return;

  $$(".prompt-tab").forEach((button) => {
    const isActive = button.dataset.promptTab === name;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  $$(".prompt-panel").forEach((panel) => {
    const isActive = panel.dataset.promptPanel === name;
    panel.classList.toggle("active", isActive);
    panel.hidden = !isActive;
  });
}

function movePromptPanel(direction) {
  const current = $(".prompt-tab.active")?.dataset.promptTab || PROMPT_PANELS[0];
  const currentIndex = PROMPT_PANELS.indexOf(current);
  const nextIndex = (currentIndex + direction + PROMPT_PANELS.length) % PROMPT_PANELS.length;
  showPromptPanel(PROMPT_PANELS[nextIndex]);
}

function setUpdateStatus(payload) {
  const message = payload?.message || "대기 중";
  setText("#updateStatus", message);

  state.updateAvailable = payload?.status === "available" || state.updateAvailable;
  state.updateDownloaded = payload?.status === "downloaded" || payload?.downloaded || false;

  if (payload?.status === "not-available" || payload?.status === "error") {
    state.updateAvailable = false;
    state.updateDownloaded = false;
  }

  $("#downloadUpdate").disabled = !state.updateAvailable || state.updateDownloaded;
  $("#installUpdate").disabled = !state.updateDownloaded;
}

async function runAction(action) {
  try {
    return await action();
  } catch (error) {
    addLog(error.message);
    window.alert(error.message);
    return null;
  }
}

function isExpiredError(error) {
  return /만료|8004|-8002|expired/i.test(error?.message || "");
}

function inputValue(selector) {
  return $(selector).value.trim();
}

function pythonRuntimeMessage(status) {
  if (!status || status.ok) return "";
  const missing = (status.missing || [])
    .map((item) => item.packageName)
    .join(", ");
  const installCommand = `${status.command || "python3"} -m pip install -e .`;
  return `${status.message}${missing ? ` 누락: ${missing}.` : ""} 프로젝트 폴더에서 ${installCommand} 실행 후 다시 시작하세요.`;
}

function formatDateInput(value) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function compactDate(value) {
  return value.replaceAll("-", "");
}

function defaultWeeklyMezzDates(today = new Date()) {
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const daysSinceMonday = end.getDay() === 1 ? 7 : (end.getDay() + 6) % 7;
  const start = new Date(end);
  start.setDate(end.getDate() - daysSinceMonday);
  return {
    from: formatDateInput(start),
    to: formatDateInput(end),
  };
}

function buildPptInputs() {
  return {
    stock_code: inputValue("#pptStockCode"),
    mezz_type_full: inputValue("#pptMezzType"),
    investment_amt: inputValue("#pptInvestmentAmt"),
    issue_amt: inputValue("#pptIssueAmt"),
  };
}

function buildPptOwnership() {
  return {
    callPercent: inputValue("#pptCallPercent"),
    refixingPercent: inputValue("#pptRefixingPercent"),
    priorMezzanineShares: inputValue("#pptPriorMezzanineShares"),
    maxShareholders: inputValue("#pptMaxShareholders"),
    isTreasuryEb: $("#pptTreasuryEb").value === "Y",
  };
}

function buildPptAiText() {
  return {
    investment_text_title1: inputValue("#investmentTextTitle1"),
    investment_text_contents1_1: inputValue("#investmentTextContents11"),
    investment_text_contents1_2: inputValue("#investmentTextContents12"),
    investment_text_title2: inputValue("#investmentTextTitle2"),
    investment_text_contents2_1: inputValue("#investmentTextContents21"),
    investment_text_contents2_2: inputValue("#investmentTextContents22"),
    investment_text_title3: inputValue("#investmentTextTitle3"),
    investment_text_contents3_1: inputValue("#investmentTextContents31"),
    investment_text_contents3_2: inputValue("#investmentTextContents32"),
    price_text_title1: inputValue("#priceTextTitle1"),
    price_text_title2: inputValue("#priceTextTitle2"),
    risk_text_title1: inputValue("#riskTextTitle1"),
    risk_text_contents1_1: inputValue("#riskTextContents11"),
    risk_text_title2: inputValue("#riskTextTitle2"),
    risk_text_contents2_1: inputValue("#riskTextContents21"),
  };
}

function applyTemplateFiles(settings) {
  if (settings.templateDir) {
    state.pptTemplateDir = settings.templateDir;
    $("#pptTemplateDir").value = settings.templateDir;
  }
  if (settings.modelPath) {
    state.pptExcelPath = settings.modelPath;
    state.pptExcelData = null;
    $("#pptExcel").value = settings.modelPath;
  }
  if (settings.templatePath) {
    state.pptTemplatePath = settings.templatePath;
    $("#pptTemplate").value = settings.templatePath;
  }
}

function applySavedFilePaths(savedFilePaths = {}, defaults = {}) {
  state.captureOutput = savedFilePaths.captureOutput || defaults.defaultCaptureOutput || "";
  state.weeklyMezzOutput = savedFilePaths.weeklyMezzOutput || defaults.defaultWeeklyMezzOutput || "";
  state.pptOutputPath = savedFilePaths.pptOutput || defaults.defaultPptOutput || "";
  state.pptTemplatePath = savedFilePaths.pptTemplate || state.pptTemplatePath;
  state.pptExcelPath = savedFilePaths.pptExcel || state.pptExcelPath;

  $("#captureOutput").value = state.captureOutput;
  $("#weeklyMezzOutput").value = state.weeklyMezzOutput;
  $("#pptOutput").value = state.pptOutputPath;
  $("#pptTemplate").value = state.pptTemplatePath;
  $("#pptExcel").value = state.pptExcelPath;
}

function buildGeminiSettings() {
  return {
    apiKeys: inputValue("#geminiApiKey") ? [inputValue("#geminiApiKey")] : [],
    investmentModel: inputValue("#geminiInvestmentModel") || "gemini-1.5-pro",
    formattingModel: inputValue("#geminiFormattingModel") || "gemini-2.5-flash",
    useSearchGrounding: $("#geminiUseSearch").checked,
    templateDir: state.pptTemplateDir,
    prompts: {
      investmentSystem: inputValue("#investmentSystemPrompt"),
      investmentCustom: inputValue("#investmentCustomPrompt"),
      priceSystem: inputValue("#priceSystemPrompt"),
      priceCustom: inputValue("#priceCustomPrompt"),
      riskSystem: inputValue("#riskSystemPrompt"),
      riskCustom: inputValue("#riskCustomPrompt"),
    },
  };
}

function applyGeminiSettings(settings) {
  $("#geminiApiKey").value = settings.apiKeys?.[0] || "";
  $("#geminiInvestmentModel").value = settings.investmentModel || "gemini-1.5-pro";
  $("#geminiFormattingModel").value = settings.formattingModel || "gemini-2.5-flash";
  $("#geminiUseSearch").checked = settings.useSearchGrounding !== false;
  $("#investmentSystemPrompt").value = settings.prompts?.investmentSystem || "";
  $("#investmentCustomPrompt").value = settings.prompts?.investmentCustom || "";
  $("#priceSystemPrompt").value = settings.prompts?.priceSystem || "";
  $("#priceCustomPrompt").value = settings.prompts?.priceCustom || "";
  $("#riskSystemPrompt").value = settings.prompts?.riskSystem || "";
  $("#riskCustomPrompt").value = settings.prompts?.riskCustom || "";
}

function applyAiText(aiText) {
  $("#investmentTextTitle1").value = aiText.investment_text_title1 || "";
  $("#investmentTextContents11").value = aiText.investment_text_contents1_1 || "";
  $("#investmentTextContents12").value = aiText.investment_text_contents1_2 || "";
  $("#investmentTextTitle2").value = aiText.investment_text_title2 || "";
  $("#investmentTextContents21").value = aiText.investment_text_contents2_1 || "";
  $("#investmentTextContents22").value = aiText.investment_text_contents2_2 || "";
  $("#investmentTextTitle3").value = aiText.investment_text_title3 || "";
  $("#investmentTextContents31").value = aiText.investment_text_contents3_1 || "";
  $("#investmentTextContents32").value = aiText.investment_text_contents3_2 || "";
  $("#priceTextTitle1").value = aiText.price_text_title1 || "";
  $("#priceTextTitle2").value = aiText.price_text_title2 || "";
  $("#riskTextTitle1").value = aiText.risk_text_title1 || "";
  $("#riskTextContents11").value = aiText.risk_text_contents1_1 || "";
  $("#riskTextTitle2").value = aiText.risk_text_title2 || "";
  $("#riskTextContents21").value = aiText.risk_text_contents2_1 || "";
}

function renderShareholderRows(shareholders = []) {
  const body = $("#shareholderRows");
  body.replaceChildren();
  if (shareholders.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.textContent = "조회된 주주가 없습니다.";
    row.append(cell);
    body.append(row);
    return;
  }

  shareholders.forEach((shareholder, index) => {
    const row = document.createElement("tr");
    row.dataset.index = String(index);

    const enabledCell = document.createElement("td");
    const enabledInput = document.createElement("input");
    enabledInput.type = "checkbox";
    enabledInput.className = "ui-checkbox shareholder-enabled";
    enabledInput.checked = shareholder.enabled !== false;
    enabledCell.append(enabledInput);
    row.append(enabledCell);

    [
      ["name", shareholder.name || ""],
      ["relation", shareholder.relation || ""],
      ["shares", shareholder.shares || ""],
      ["ratio", shareholder.ratio || ""],
    ].forEach(([key, value]) => {
      const cell = document.createElement("td");
      const input = document.createElement("input");
      input.className = `ui-input shareholder-${key}`;
      input.value = value;
      cell.append(input);
      row.append(cell);
    });

    const callCell = document.createElement("td");
    const callInput = document.createElement("input");
    callInput.type = "checkbox";
    callInput.className = "ui-checkbox shareholder-call";
    callInput.checked = shareholder.callEnabled !== false;
    callCell.append(callInput);
    row.append(callCell);

    const orderCell = document.createElement("td");
    const upButton = document.createElement("button");
    const downButton = document.createElement("button");
    upButton.type = "button";
    downButton.type = "button";
    upButton.className = "ui-button ui-button--compact secondary table-button";
    downButton.className = "ui-button ui-button--compact secondary table-button";
    upButton.textContent = "위";
    downButton.textContent = "아래";
    upButton.disabled = index === 0;
    downButton.disabled = index === shareholders.length - 1;
    upButton.addEventListener("click", () => moveShareholder(index, -1));
    downButton.addEventListener("click", () => moveShareholder(index, 1));
    orderCell.append(upButton, downButton);
    row.append(orderCell);

    body.append(row);
  });
}

function collectShareholdersFromEditor() {
  return $$("#shareholderRows tr")
    .map((row) => {
      const enabled = row.querySelector(".shareholder-enabled");
      const name = row.querySelector(".shareholder-name")?.value.trim();
      if (!enabled || !enabled.checked || !name) return null;
      return {
        name,
        relation: row.querySelector(".shareholder-relation")?.value.trim() || "",
        shares: row.querySelector(".shareholder-shares")?.value.trim() || "0",
        ratio: row.querySelector(".shareholder-ratio")?.value.trim() || "0",
        callEnabled: row.querySelector(".shareholder-call")?.checked !== false,
      };
    })
    .filter(Boolean);
}

function moveShareholder(index, direction) {
  if (!state.pptCompanyInfo?.shareholders) return;
  const current = collectShareholdersFromEditor();
  const target = index + direction;
  if (target < 0 || target >= current.length) return;
  const next = [...current];
  const item = next[index];
  next[index] = next[target];
  next[target] = item;
  state.pptCompanyInfo = { ...state.pptCompanyInfo, shareholders: next };
  renderShareholderRows(next);
}

function renderPptPreview(result) {
  const summary = $("#pptSummaryPreview");
  summary.replaceChildren();
  [
    ["회사", `${result.data.corp_name || ""} ${result.data.stock_code ? `(${result.data.stock_code})` : ""}`.trim()],
    ["시장", result.data.stock_market || "-"],
    ["메자닌", result.data.mezz_type || "-"],
    ["투자금액", result.data.invest_amt || "-"],
    ["발행금액", result.data.issue_amt || "-"],
    ["전환가", result.data.ex_prc || "-"],
    ["기준일", result.data.base_date || "-"],
    ["보고일", result.data.report_date || "-"],
  ].forEach(([term, description]) => {
    const item = document.createElement("div");
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = term;
    dd.textContent = description;
    item.append(dt, dd);
    summary.append(item);
  });

  const detail = $("#companyDetailPreview");
  detail.replaceChildren();
  const companyData = result.companyInfo?.companyData || {};
  [
    ["정식명", result.companyInfo?.corp_name_full || "-"],
    ["영문명", companyData.corp_name_en || "-"],
    ["대표이사", companyData.representative || "-"],
    ["설립일", companyData.establishment_date || "-"],
    ["상장일", companyData.listing_date || "-"],
    ["업종", companyData.industry || "-"],
    ["주요제품", companyData.main_products || "-"],
    ["자본금", companyData.capital || "-"],
    ["종업원수", companyData.employees || "-"],
    ["전화번호", companyData.phone || "-"],
    ["주소", companyData.address || "-"],
    ["홈페이지", companyData.homepage || "-"],
  ].forEach(([term, description]) => {
    const item = document.createElement("div");
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = term;
    dd.textContent = description;
    item.append(dt, dd);
    detail.append(item);
  });

  const classificationRows = $("#classificationPreviewRows");
  classificationRows.replaceChildren();
  const classifications = result.companyInfo?.shareholderClassification || [];
  if (classifications.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 2;
    cell.textContent = "조회된 주주구분 데이터가 없습니다.";
    row.append(cell);
    classificationRows.append(row);
  } else {
    classifications.forEach((classification) => {
      const row = document.createElement("tr");
      const categoryCell = document.createElement("td");
      const sharesCell = document.createElement("td");
      categoryCell.textContent = classification.category || "";
      sharesCell.textContent = classification.shares || "";
      row.append(categoryCell, sharesCell);
      classificationRows.append(row);
    });
  }

  const head = $("#ownershipPreviewHead");
  const body = $("#ownershipPreviewRows");
  head.replaceChildren();
  body.replaceChildren();

  const headerRow = document.createElement("tr");
  ["구분", ...(result.ownershipCases || []).flatMap((ownershipCase) => [`${ownershipCase.label} 주식수`, `${ownershipCase.label} 지분율`])].forEach((label) => {
    const cell = document.createElement("th");
    cell.textContent = label;
    headerRow.append(cell);
  });
  head.append(headerRow);

  const names = [];
  (result.ownershipCases || []).forEach((ownershipCase) => {
    ownershipCase.rows.forEach((row) => {
      if (!names.includes(row.name)) names.push(row.name);
    });
  });
  names.push("합계");

  names.forEach((name) => {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    nameCell.textContent = name;
    row.append(nameCell);

    (result.ownershipCases || []).forEach((ownershipCase) => {
      const ownershipRow = ownershipCase.rows.find((item) => item.name === name);
      const shares = name === "합계" ? ownershipCase.totalShares : ownershipRow?.shares || 0;
      const ratio = ownershipCase.denominatorShares > 0 ? (shares / ownershipCase.denominatorShares) * 100 : 0;
      const sharesCell = document.createElement("td");
      const ratioCell = document.createElement("td");
      sharesCell.textContent = shares > 0 || name === "합계" ? shares.toLocaleString() : "-";
      ratioCell.textContent = shares > 0 || name === "합계" ? `${ratio.toFixed(1)}%` : "-";
      row.append(sharesCell, ratioCell);
    });

    body.append(row);
  });
}

async function loadPptSourceData() {
  const inputs = buildPptInputs();
  if (!/^\d{6}$/.test(inputs.stock_code)) {
    window.alert("종목코드는 6자리 숫자로 입력하세요.");
    return null;
  }
  if (!state.pptExcelPath) {
    window.alert("Model.xlsx 파일을 선택하세요.");
    return null;
  }

  addLog("PPT Forger 회사 정보와 엑셀 데이터를 읽습니다.");
  try {
    const useCachedCompany = state.pptCompanyInfo?.stock_code === inputs.stock_code;
    const useCachedExcel = state.pptExcelData?.path === state.pptExcelPath;
    const [companyInfo, excelData] = await Promise.all([
      useCachedCompany ? Promise.resolve(state.pptCompanyInfo) : window.maxawon.pptFetchCompany(inputs.stock_code),
      useCachedExcel ? Promise.resolve(state.pptExcelData) : window.maxawon.pptReadExcel(state.pptExcelPath),
    ]);
    state.pptCompanyInfo = { ...companyInfo, stock_code: inputs.stock_code };
    state.pptExcelData = { ...excelData, path: state.pptExcelPath };
    if (!useCachedCompany) renderShareholderRows(state.pptCompanyInfo.shareholders || []);
    return { inputs, companyInfo: state.pptCompanyInfo, excelData };
  } catch (error) {
    addLog(error.message);
    window.alert(error.message);
    return null;
  }
}

async function buildPptData(nextTab = "shareholders") {
  $("#buildPptData").disabled = true;
  try {
    const sourceData = await loadPptSourceData();
    if (!sourceData) return null;
    const { inputs, excelData } = sourceData;
    const companyInfo = {
      ...sourceData.companyInfo,
      shareholders: collectShareholdersFromEditor(),
    };
    state.pptCompanyInfo = companyInfo;

    const result = await window.maxawon.pptBuildData({
      inputs,
      companyInfo,
      excelData,
      aiText: buildPptAiText(),
      ownership: buildPptOwnership(),
    });
    state.pptData = result.data;
    $("#pptData").value = JSON.stringify(result.data, null, 2);
    renderPptPreview(result);
    showPptTab(nextTab);
    addLog(`PPT 치환 데이터를 만들었습니다: ${result.data.corp_name || inputs.stock_code}`);
    if (excelData.missingFinancials?.length) {
      addLog(`Model.xlsx에서 찾지 못한 재무 항목: ${excelData.missingFinancials.join(", ")}`);
    }
    return result.data;
  } catch (error) {
    addLog(error.message);
    window.alert(error.message);
    return null;
  } finally {
    $("#buildPptData").disabled = false;
  }
}

async function generateGeminiText() {
  if (state.geminiRunning) return null;

  const sourceData = await loadPptSourceData();
  if (!sourceData) return null;

  state.geminiRunning = true;
  $("#generateGeminiText").disabled = true;
  addLog("Gemini 문구 생성을 시작합니다.");
  try {
    const savedSettings = await window.maxawon.pptSaveGeminiSettings(buildGeminiSettings());
    const result = await window.maxawon.pptGenerateGemini({
      settings: savedSettings,
      companyInfo: `${sourceData.companyInfo.corp_name}(${sourceData.inputs.stock_code})`,
      financialData: sourceData.excelData.financialData,
      options: {
        investment: $("#generateInvestmentText").checked,
        price: $("#generatePriceText").checked,
        risk: $("#generateRiskText").checked,
      },
    });
    applyAiText(result.aiText);
    showPptTab("copy");
    addLog("Gemini 문구를 생성하고 입력칸에 반영했습니다.");
    await buildPptData("copy");
    return result.aiText;
  } catch (error) {
    addLog(error.message);
    window.alert(error.message);
    return null;
  } finally {
    state.geminiRunning = false;
    $("#generateGeminiText").disabled = false;
  }
}

async function runCapture(payload, resumed = false) {
  if (!state.loginDone) {
    window.alert("Maxawon에 로그인한 뒤 '로그인 완료'를 누르세요.");
    return;
  }

  state.captureRunning = true;
  $("#captureTable").disabled = true;
  addLog(resumed ? "보류된 조건검색 테이블 CSV 저장을 재개합니다." : "현재 조건검색 테이블 CSV 저장을 시작합니다.");

  try {
    const result = await window.maxawon.captureTable(payload);
    state.pendingCapture = null;
    addLog(`조건검색 결과 ${result.rowCount}행을 저장했습니다: ${result.outputPath}`);
  } catch (error) {
    if (isExpiredError(error)) {
      state.pendingCapture = payload;
      setLogin("재확인 필요", false);
      addLog("Maxawon 페이지가 만료되어 작업을 일시 중단했습니다. Chrome에서 새로고침한 뒤 앱의 '로그인 완료'를 누르면 다시 실행합니다.");
      window.alert("Maxawon 페이지가 만료되었습니다. Chrome에서 새로고침한 뒤 앱으로 돌아와 '로그인 완료'를 누르세요.");
    } else {
      addLog(error.message);
      window.alert(error.message);
    }
  } finally {
    state.captureRunning = false;
    $("#captureTable").disabled = false;
  }
}

async function runWeeklyMezz() {
  if (state.weeklyMezzRunning) return;

  const fromDate = inputValue("#weeklyMezzFrom");
  const toDate = inputValue("#weeklyMezzTo");
  if (!fromDate || !toDate) {
    window.alert("조회 시작일과 종료일을 입력하세요.");
    return;
  }
  if (fromDate > toDate) {
    window.alert("시작일은 종료일보다 늦을 수 없습니다.");
    return;
  }
  if (!state.weeklyMezzOutput) {
    window.alert("저장 파일을 선택하세요.");
    return;
  }
  const lastReportValue = inputValue("#weeklyMezzLastOnly").toUpperCase() || "Y";
  if (!["Y", "N"].includes(lastReportValue)) {
    window.alert("최종보고서만 값은 Y 또는 N이어야 합니다.");
    return;
  }

  state.weeklyMezzRunning = true;
  $("#runWeeklyMezz").disabled = true;
  addLog(`Weekly Mezz 수집을 시작합니다: ${fromDate} ~ ${toDate}`);
  try {
    const result = await window.maxawon.weeklyMezzCollect({
      fromDate: compactDate(fromDate),
      toDate: compactDate(toDate),
      outputPath: state.weeklyMezzOutput,
      lastReportValue,
    });
    const summary = result.summary || {};
    addLog(`Weekly Mezz 엑셀을 저장했습니다: ${result.outputPath}`);
    addLog(`검색 ${summary.total_count || 0}건, 필터 ${summary.filtered_count || 0}건, 저장 ${summary.exported_count || 0}건`);
    if (result.rawPath) addLog(`원본 JSON을 저장했습니다: ${result.rawPath}`);
  } catch (error) {
    addLog(error.message);
    window.alert(error.message);
  } finally {
    state.weeklyMezzRunning = false;
    $("#runWeeklyMezz").disabled = false;
  }
}
