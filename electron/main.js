const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(projectRoot, "src");
const profileDir = path.join(projectRoot, ".chrome-profile");
const defaultCaptureOutput = path.join(projectRoot, "output", "cretop_condition_search.csv");
const remoteDebuggingPort = "9222";
const cretopUrl = "https://www.cretop.com/";

let mainWindow;

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

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
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

  return { message: "Chrome을 열었습니다. Cretop에서 직접 로그인한 뒤 조건검색을 실행하세요." };
});

ipcMain.handle("app:check-scrapling", () =>
  runPython(`
import json
from cretop_data_reader.scrapling_adapter import check_scrapling
status = check_scrapling()
print(json.dumps({"installed": status.installed, "message": status.message}, ensure_ascii=False))
`),
);

ipcMain.handle("app:pick-excel", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "검색 대상 파일 선택",
    properties: ["openFile"],
    filters: [
      { name: "Excel or CSV", extensions: ["xlsx", "xlsm", "csv"] },
      { name: "Excel", extensions: ["xlsx", "xlsm"] },
      { name: "CSV", extensions: ["csv"] },
      { name: "All files", extensions: ["*"] },
    ],
  });

  if (result.canceled || result.filePaths.length === 0) return null;
  const filePath = result.filePaths[0];
  const preview = await runPython(
    `
import json
import sys
from pathlib import Path
from cretop_data_reader.app import read_excel_preview
headers, rows = read_excel_preview(Path(sys.argv[1]))
print(json.dumps({"headers": headers, "rows": rows}, ensure_ascii=False))
`,
    [filePath],
  );
  return { path: filePath, ...preview };
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
