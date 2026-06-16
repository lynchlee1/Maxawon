const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { autoUpdater } = require("electron-updater");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const runtimeRoot = app.getPath("userData");
const pythonRoot = app.isPackaged ? process.resourcesPath : projectRoot;
const srcRoot = path.join(pythonRoot, "src");
const profileDir = path.join(runtimeRoot, "chrome-profile");
const defaultCaptureOutput = path.join(runtimeRoot, "output", "maxawon_condition_search.csv");
const networkLogDir = path.join(runtimeRoot, "network-logs");
const remoteDebuggingPort = "9222";
const maxawonUrl = "https://www.maxawon.com/";
const updateFeed = "https://github.com/lynchlee1/Maxawon/releases";

let mainWindow;
let networkLoggerProcess = null;
let downloadedUpdate = false;

autoUpdater.autoDownload = false;

function sendUpdateStatus(payload) {
  if (!mainWindow) return;
  mainWindow.webContents.send("update:status", {
    ...payload,
    downloaded: downloadedUpdate,
  });
}

autoUpdater.on("checking-for-update", () => {
  sendUpdateStatus({ status: "checking", message: "업데이트를 확인하는 중입니다." });
});

autoUpdater.on("update-available", (info) => {
  sendUpdateStatus({
    status: "available",
    message: `새 버전 ${info.version}을 사용할 수 있습니다.`,
    version: info.version,
  });
});

autoUpdater.on("update-not-available", (info) => {
  sendUpdateStatus({
    status: "not-available",
    message: "현재 최신 버전을 사용 중입니다.",
    version: info.version,
  });
});

autoUpdater.on("download-progress", (progress) => {
  sendUpdateStatus({
    status: "downloading",
    message: `업데이트 다운로드 중입니다. ${Math.round(progress.percent)}%`,
    progress: progress.percent,
  });
});

autoUpdater.on("update-downloaded", (info) => {
  downloadedUpdate = true;
  sendUpdateStatus({
    status: "downloaded",
    message: "업데이트 다운로드가 완료되었습니다. 재시작하면 설치됩니다.",
    version: info.version,
  });
});

autoUpdater.on("error", (error) => {
  sendUpdateStatus({
    status: "error",
    message: error.message || "업데이트 확인 중 오류가 발생했습니다.",
  });
});

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1220,
    height: 780,
    minWidth: 980,
    minHeight: 680,
    title: "Maxawon",
    backgroundColor: "#eef2f7",
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));

  if (process.argv.includes("--dev")) {
    mainWindow.webContents.openDevTools({ mode: "detach" });
  }
}

app.whenReady().then(() => {
  purgeOldNetworkLogs();
  startNetworkLogger();
  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  stopNetworkLogger();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

function pythonCommand() {
  return process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
}

function runPython(code, args = []) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonCommand(), ["-c", code, ...args], {
      cwd: pythonRoot,
      env: {
        ...process.env,
        PYTHONPATH: process.env.PYTHONPATH ? `${srcRoot}${path.delimiter}${process.env.PYTHONPATH}` : srcRoot,
        PYTHONUTF8: "1",
        PYTHONWARNINGS: "ignore",
      },
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (codeNumber) => {
      if (codeNumber !== 0) {
        reject(new Error(stderr.trim() || `Python exited with code ${codeNumber}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (error) {
        reject(new Error(`Python returned invalid JSON: ${stdout.trim()}`));
      }
    });
  });
}

function pythonEnv() {
  return {
    ...process.env,
    PYTHONPATH: process.env.PYTHONPATH ? `${srcRoot}${path.delimiter}${process.env.PYTHONPATH}` : srcRoot,
    PYTHONUTF8: "1",
    PYTHONWARNINGS: "ignore",
  };
}

function purgeOldNetworkLogs() {
  if (!fs.existsSync(networkLogDir)) return;

  const cutoff = Date.now() - 24 * 60 * 60 * 1000;
  const removeOldFiles = (directory) => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const entryPath = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        removeOldFiles(entryPath);
        try {
          fs.rmdirSync(entryPath);
        } catch (_error) {
          // Keep non-empty directories.
        }
        continue;
      }

      if (entry.isFile() && fs.statSync(entryPath).mtimeMs < cutoff) {
        fs.unlinkSync(entryPath);
      }
    }
  };

  removeOldFiles(networkLogDir);
}

function startNetworkLogger() {
  if (networkLoggerProcess && !networkLoggerProcess.killed) return;

  fs.mkdirSync(networkLogDir, { recursive: true });
  const stdout = fs.openSync(path.join(networkLogDir, "network-logger.stdout.log"), "a");
  const stderr = fs.openSync(path.join(networkLogDir, "network-logger.stderr.log"), "a");
  networkLoggerProcess = spawn(
    pythonCommand(),
    [
      "-m",
      "maxawon.network_logger",
      "--log-dir",
      networkLogDir,
      "--cdp-url",
      `http://127.0.0.1:${remoteDebuggingPort}`,
    ],
    {
      cwd: pythonRoot,
      env: pythonEnv(),
      stdio: ["ignore", stdout, stderr],
    },
  );
  networkLoggerProcess.on("error", () => {
    networkLoggerProcess = null;
  });
  networkLoggerProcess.on("exit", () => {
    networkLoggerProcess = null;
  });
}

function stopNetworkLogger() {
  if (!networkLoggerProcess || networkLoggerProcess.killed) return;
  networkLoggerProcess.kill();
  networkLoggerProcess = null;
}

function runSync(command, args) {
  return spawnSync(command, args, { encoding: "utf8" });
}

function collectMatchingPids(patterns) {
  const pids = new Set();
  for (const pattern of patterns) {
    const result = runSync("pgrep", ["-f", pattern]);
    if (result.status !== 0 && result.status !== 1) continue;
    for (const line of result.stdout.split(/\r?\n/)) {
      const pid = Number(line.trim());
      if (Number.isInteger(pid) && pid > 0 && pid !== process.pid) {
        pids.add(pid);
      }
    }
  }
  return [...pids];
}

function terminatePids(pids, signal) {
  let count = 0;
  for (const pid of pids) {
    try {
      process.kill(pid, signal);
      count += 1;
    } catch (_error) {
      // Process may have exited between discovery and termination.
    }
  }
  return count;
}

function closeAppChromeProcesses() {
  stopNetworkLogger();

  const patterns = [profileDir, `--remote-debugging-port=${remoteDebuggingPort}`];
  if (process.platform === "win32") {
    const profile = profileDir.replace(/'/g, "''");
    const port = `--remote-debugging-port=${remoteDebuggingPort}`;
    const script = `
$matches = Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq 'chrome.exe' -and $_.CommandLine -and (
    $_.CommandLine -like '*${profile}*' -or $_.CommandLine -like '*${port}*'
  )
}
$matches | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force
  $_.ProcessId
}
`;
    const result = runSync("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]);
    if (result.status !== 0) {
      throw new Error(result.stderr.trim() || "앱이 연 Chrome 프로세스 종료에 실패했습니다.");
    }
    return result.stdout.split(/\r?\n/).filter((line) => line.trim()).length;
  }

  const pids = collectMatchingPids(patterns);
  const count = terminatePids(pids, "SIGTERM");
  return count || terminatePids(pids, "SIGKILL");
}

function closeAllChromeProcesses() {
  stopNetworkLogger();

  if (process.platform === "darwin") {
    const result = runSync("pkill", ["-f", "Google Chrome"]);
    if (result.status !== 0 && result.status !== 1) {
      throw new Error(result.stderr.trim() || "Chrome 전체 종료에 실패했습니다.");
    }
    return result.status === 0 ? 1 : 0;
  }

  if (process.platform === "win32") {
    const script = `
$matches = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' }
$matches | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force
  $_.ProcessId
}
`;
    const result = runSync("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]);
    if (result.status !== 0) {
      throw new Error(result.stderr.trim() || "Chrome 전체 종료에 실패했습니다.");
    }
    return result.stdout.split(/\r?\n/).filter((line) => line.trim()).length;
  }

  const result = runSync("pkill", ["-f", "chrome|chromium"]);
  if (result.status !== 0 && result.status !== 1) {
    throw new Error(result.stderr.trim() || "Chrome/Chromium 전체 종료에 실패했습니다.");
  }
  return result.status === 0 ? 1 : 0;
}

function findChrome() {
  if (process.platform === "darwin") {
    const candidates = [
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      path.join(os.homedir(), "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    ];
    return candidates.find((candidate) => fs.existsSync(candidate)) || null;
  }

  if (process.platform === "win32") {
    const candidates = [
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      path.join(os.homedir(), "AppData", "Local", "Google", "Chrome", "Application", "chrome.exe"),
    ];
    return candidates.find((candidate) => fs.existsSync(candidate)) || null;
  }

  const commands = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"];
  for (const command of commands) {
    const lookup = spawnSync("which", [command]);
    if (lookup.status === 0) return command;
  }
  return null;
}

ipcMain.handle("app:get-defaults", () => ({
  defaultCaptureOutput,
  cdpUrl: `http://127.0.0.1:${remoteDebuggingPort}`,
  networkLogDir,
  appVersion: app.getVersion(),
  updateFeed,
  updatesSupported: app.isPackaged,
}));

ipcMain.handle("app:check-for-updates", async () => {
  if (!app.isPackaged) {
    return {
      status: "unsupported",
      message: "업데이트 확인은 패키징된 앱에서만 사용할 수 있습니다.",
    };
  }

  downloadedUpdate = false;
  const result = await autoUpdater.checkForUpdates();
  return {
    status: "checked",
    message: "업데이트 확인 요청을 보냈습니다.",
    version: result?.updateInfo?.version || null,
  };
});

ipcMain.handle("app:download-update", async () => {
  if (!app.isPackaged) {
    return {
      status: "unsupported",
      message: "업데이트 다운로드는 패키징된 앱에서만 사용할 수 있습니다.",
    };
  }

  await autoUpdater.downloadUpdate();
  return {
    status: "downloading",
    message: "업데이트 다운로드를 시작했습니다.",
  };
});

ipcMain.handle("app:install-update", () => {
  if (!downloadedUpdate) {
    return {
      status: "not-ready",
      message: "아직 설치할 업데이트가 없습니다.",
    };
  }

  autoUpdater.quitAndInstall(false, true);
  return {
    status: "installing",
    message: "앱을 재시작해 업데이트를 설치합니다.",
  };
});

ipcMain.handle("app:open-chrome", async () => {
  const chrome = findChrome();
  if (!chrome) {
    throw new Error("이 PC에서 Chrome 실행 파일을 찾지 못했습니다.");
  }

  fs.mkdirSync(profileDir, { recursive: true });
  const child = spawn(
    chrome,
    [
      `--user-data-dir=${profileDir}`,
      `--remote-debugging-port=${remoteDebuggingPort}`,
      "--new-window",
      maxawonUrl,
    ],
    { detached: true, stdio: "ignore" },
  );
  child.unref();
  startNetworkLogger();

  return {
    message: `Chrome을 열었습니다. Network 로그는 ${networkLogDir}에 1일치만 저장합니다.`,
  };
});

ipcMain.handle("app:close-app-chrome", () => {
  const count = closeAppChromeProcesses();
  return {
    message: count > 0 ? "앱이 연 Chrome 프로세스를 종료했습니다." : "종료할 앱 Chrome 프로세스를 찾지 못했습니다.",
  };
});

ipcMain.handle("app:close-all-chrome", () => {
  const count = closeAllChromeProcesses();
  return {
    message: count > 0 ? "모든 Chrome 프로세스 종료 명령을 실행했습니다." : "실행 중인 Chrome 프로세스를 찾지 못했습니다.",
  };
});

ipcMain.handle("app:pick-capture-output", async (_event, currentPath) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    title: "조건검색 복사 결과 저장",
    defaultPath: currentPath || defaultCaptureOutput,
    filters: [
      { name: "CSV", extensions: ["csv"] },
      { name: "All files", extensions: ["*"] },
    ],
  });

  if (result.canceled || !result.filePath) return null;
  return result.filePath;
});

ipcMain.handle("app:capture-table", (_event, payload) =>
  runPython(
    `
import json
import sys
from pathlib import Path
from maxawon.table_capture import CapturedTable, capture_current_maxawon_table_sync, write_table_csv
max_pages = int(sys.argv[1]) if sys.argv[1] else None
output_path = Path(sys.argv[2])
result = capture_current_maxawon_table_sync(max_pages=max_pages)
if not result.rows:
    raise RuntimeError("현재 화면에서 복사할 테이블 데이터를 찾지 못했습니다.")
output_path.parent.mkdir(parents=True, exist_ok=True)
write_table_csv(output_path, CapturedTable(result.headers, result.rows))
print(json.dumps({
    "headers": result.headers,
    "rows": result.rows[:100],
    "pages": result.pages,
    "rowCount": len(result.rows),
    "outputPath": str(output_path),
}, ensure_ascii=False))
`,
    [payload.maxPages == null ? "" : String(payload.maxPages), payload.outputPath],
  ),
);
