const state = {
  loginDone: false,
  captureOutput: "",
  pendingCapture: null,
  captureRunning: false,
  updateAvailable: false,
  updateDownloaded: false,
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

function setLogin(message, done = false) {
  state.loginDone = done;
  setText("#loginText", message);
  $("#loginPill").classList.toggle("connected", done);
  $("#loginPill").classList.toggle("disconnected", !done);
}

function showView(name) {
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === name));
  $$(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });
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

async function init() {
  const defaults = await window.maxawon.getDefaults();
  state.captureOutput = defaults.defaultCaptureOutput;
  $("#captureOutput").value = defaults.defaultCaptureOutput;
  if (defaults.appVersion) {
    setText("#appVersion", `v${defaults.appVersion}`);
    setText("#currentVersion", `v${defaults.appVersion}`);
  }
  setText("#updateFeed", defaults.updateFeed);
  if (!defaults.updatesSupported) {
    setUpdateStatus({ status: "unsupported", message: "앱 업데이트 확인은 패키징된 앱에서만 사용할 수 있습니다." });
  }

  window.maxawon.onUpdateStatus((payload) => {
    setUpdateStatus(payload);
    addLog(payload.message);
  });

  $$(".nav-button").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
  });

  $("#openChrome").addEventListener("click", async () => {
    const result = await runAction(() => window.maxawon.openChrome());
    if (!result) return;
    addLog(result.message);
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

  $("#clearLog").addEventListener("click", () => {
    $("#logs").replaceChildren();
  });

  addLog("Chrome을 열고 직접 로그인한 뒤 '로그인 완료'를 누르세요.");
}

init();
