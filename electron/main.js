const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(projectRoot, "src");
const profileDir = path.join(projectRoot, ".chrome-profile");
const defaultCaptureOutput = path.join(projectRoot, "output", "cretop_condition_search.csv");
const networkLogDir = path.join(projectRoot, "network-logs");
const remoteDebuggingPort = "9222";
const cretopUrl = "https://www.cretop.com/";

let mainWindow;
let networkLoggerProcess = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1220,
    height: 780,
    minWidth: 980,
    minHeight: 680,
    title: "Cretop Data Reader",
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
      cwd: projectRoot,
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
  networkLoggerProcess = spawn(
    pythonCommand(),
    [
      "-m",
      "cretop_data_reader.network_logger",
      "--log-dir",
      networkLogDir,
      "--cdp-url",
      `http://127.0.0.1:${remoteDebuggingPort}`,
    ],
    {
      cwd: projectRoot,
      env: pythonEnv(),
      stdio: "ignore",
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
}));

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
      cretopUrl,
    ],
    { detached: true, stdio: "ignore" },
  );
  child.unref();
  startNetworkLogger();

  return {
    message: `Chrome을 열었습니다. Network 로그는 ${networkLogDir}에 1일치만 저장합니다.`,
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
from cretop_data_reader.table_capture import CapturedTable, capture_current_cretop_table_sync, write_table_csv
max_pages = int(sys.argv[1])
output_path = Path(sys.argv[2])
result = capture_current_cretop_table_sync(max_pages=max_pages)
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
    [String(payload.maxPages), payload.outputPath],
  ),
);
