const state = {
  loginDone: false,
  excelPath: null,
  captureOutput: "",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function setText(selector, value) {
  $(selector).textContent = value;
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

function setProgress(message) {
  setText("#progressStatus", message);
  setText("#progressPill", message);
  setText("#excelProgress", message);
}

function setLogin(message, done = false) {
  state.loginDone = done;
  setText("#loginStatus", message);
  setText("#loginPill", message);
  $("#loginPill").classList.toggle("success", done);
  $("#loginPill").classList.toggle("neutral", !done);
  updateStartEnabled();
}

function updateStartEnabled() {
  $("#startProcessing").disabled = !(state.loginDone && state.excelPath);
}

function showView(name) {
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === name));
  $$(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });
}

function renderTable(targetSelector, headers, rows) {
  const target = $(targetSelector);
  if (!headers.length && !rows.length) {
    target.className = "table-empty";
    target.textContent = "표시할 데이터가 없습니다.";
    return;
  }

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");
  const headerRow = document.createElement("tr");
  const width = Math.max(headers.length, ...rows.map((row) => row.length));
  const normalizedHeaders = Array.from({ length: width }, (_, index) => headers[index] || `Column ${index + 1}`);

  normalizedHeaders.forEach((header) => {
    const th = document.createElement("th");
    th.textContent = header;
    headerRow.append(th);
  });
  thead.append(headerRow);

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    normalizedHeaders.forEach((_header, index) => {
      const td = document.createElement("td");
      td.textContent = row[index] || "";
      tr.append(td);
    });
    tbody.append(tr);
  });

  table.append(thead, tbody);
  target.className = "table-wrap";
  target.replaceChildren(table);
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

async function init() {
  const defaults = await window.cretop.getDefaults();
  state.captureOutput = defaults.defaultCaptureOutput;
  $("#captureOutput").value = defaults.defaultCaptureOutput;
  $("#cdpUrl").textContent = defaults.cdpUrl;

  $$(".nav-button").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
  });

  $("#openChrome").addEventListener("click", async () => {
    const result = await runAction(() => window.cretop.openChrome());
    if (!result) return;
    setProgress("Chrome 실행됨");
    addLog(result.message);
  });

  $("#loginDone").addEventListener("click", () => {
    setLogin("로그인 완료", true);
    setProgress("엑셀 파일 선택 대기");
    addLog("사용자가 로그인 완료를 확인했습니다.");
  });

  $("#checkScrapling").addEventListener("click", async () => {
    const result = await runAction(() => window.cretop.checkScrapling());
    if (!result) return;
    setText("#scraplingStatus", result.message);
    addLog(result.message);
  });

  $("#pickOutput").addEventListener("click", async () => {
    const selected = await runAction(() => window.cretop.pickCaptureOutput(state.captureOutput));
    if (!selected) return;
    state.captureOutput = selected;
    $("#captureOutput").value = selected;
    addLog(`조건검색 저장 파일을 변경했습니다: ${selected}`);
  });

  $("#captureTable").addEventListener("click", async () => {
    if (!state.loginDone) {
      window.alert("Cretop에 로그인한 뒤 '로그인 완료'를 누르세요.");
      return;
    }

    const maxPages = Number($("#maxPages").value);
    if (!Number.isInteger(maxPages) || maxPages < 1) {
      window.alert("최대 페이지는 1 이상의 숫자로 입력하세요.");
      return;
    }

    $("#captureTable").disabled = true;
    setText("#captureStatus", "복사 중");
    addLog("현재 Cretop 화면의 조건검색 결과 테이블 복사를 시작합니다.");
    const result = await runAction(() =>
      window.cretop.captureTable({
        maxPages,
        outputPath: state.captureOutput,
      }),
    );
    $("#captureTable").disabled = false;
    if (!result) {
      setText("#captureStatus", "복사 실패");
      return;
    }
    renderTable("#capturePreview", result.headers, result.rows);
    setText("#captureStatus", `${result.pages}페이지, ${result.rowCount}행 저장 완료`);
    setText("#captureCount", `${result.rowCount}행`);
    addLog(`조건검색 결과를 저장했습니다: ${result.outputPath}`);
  });

  $("#pickExcel").addEventListener("click", async () => {
    const result = await runAction(() => window.cretop.pickExcel());
    if (!result) return;
    state.excelPath = result.path;
    setText("#fileStatus", result.path);
    setProgress("엑셀 파일 로드됨");
    renderTable("#excelPreview", result.headers, result.rows);
    setText("#excelCount", `${result.rows.length}행 미리보기`);
    addLog(`검색 대상 파일을 불러왔습니다: ${result.path}`);
    updateStartEnabled();
  });

  $("#startProcessing").addEventListener("click", () => {
    setProgress("구현 대기");
    addLog("Scrapling 기반 검색 처리는 아직 구현되지 않았습니다. 중복 후보 처리 규칙을 먼저 확정해야 합니다.");
    window.alert("기업명/법인번호 컬럼, 출력 항목, 중복 후보 선택 기준을 확정한 뒤 구현하세요.");
  });

  $("#clearLog").addEventListener("click", () => {
    $("#logs").replaceChildren();
  });

  addLog("Chrome을 열고 직접 로그인한 뒤 '로그인 완료'를 누르세요.");
  const scrapling = await runAction(() => window.cretop.checkScrapling());
  if (scrapling) {
    setText("#scraplingStatus", scrapling.message);
    addLog(scrapling.message);
  }
}

init();
