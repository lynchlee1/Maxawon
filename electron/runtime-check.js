const { spawnSync } = require("child_process");

const REQUIRED_PYTHON_MODULES = [
  { module: "playwright", packageName: "playwright", feature: "Cretop 화면 연결과 테이블 저장" },
  { module: "bs4", packageName: "beautifulsoup4", feature: "Weekly Mezz HTML 파싱" },
  { module: "lxml", packageName: "lxml", feature: "Weekly Mezz HTML/XML 파싱" },
  { module: "openpyxl", packageName: "openpyxl", feature: "Weekly Mezz 엑셀 생성" },
  { module: "requests", packageName: "requests", feature: "KIND/DART 데이터 수집" },
];

function buildPythonEnv(processEnv, srcRoot) {
  return {
    ...processEnv,
    PYTHONPATH: processEnv.PYTHONPATH ? `${srcRoot}${process.platform === "win32" ? ";" : ":"}${processEnv.PYTHONPATH}` : srcRoot,
    PYTHONUTF8: "1",
    PYTHONWARNINGS: "ignore",
  };
}

function dependencyProbeCode() {
  return `
import importlib.util
import json
modules = json.loads(${JSON.stringify(JSON.stringify(REQUIRED_PYTHON_MODULES.map((item) => item.module)))})
missing = [name for name in modules if importlib.util.find_spec(name) is None]
print(json.dumps({"missing": missing}, ensure_ascii=False))
`;
}

function checkPythonRuntime({ command, cwd, env, spawnSyncImpl = spawnSync } = {}) {
  const result = spawnSyncImpl(command, ["-c", dependencyProbeCode()], {
    cwd,
    env,
    encoding: "utf8",
  });

  if (result.error) {
    return {
      ok: false,
      command,
      missing: REQUIRED_PYTHON_MODULES,
      message: `${command} 실행 파일을 찾지 못했습니다.`,
    };
  }

  if (result.status !== 0) {
    return {
      ok: false,
      command,
      missing: REQUIRED_PYTHON_MODULES,
      message: result.stderr.trim() || `${command} 실행에 실패했습니다.`,
    };
  }

  try {
    const parsed = JSON.parse(result.stdout);
    const missing = REQUIRED_PYTHON_MODULES.filter((item) => parsed.missing.includes(item.module));
    return {
      ok: missing.length === 0,
      command,
      missing,
      message: missing.length === 0 ? "Python 런타임 준비 완료" : "Python 패키지가 설치되어 있지 않습니다.",
    };
  } catch (_error) {
    return {
      ok: false,
      command,
      missing: REQUIRED_PYTHON_MODULES,
      message: `Python 점검 결과를 읽지 못했습니다: ${result.stdout.trim()}`,
    };
  }
}

function formatPythonRuntimeError(status) {
  const missing = status.missing.map((item) => `${item.packageName}(${item.feature})`).join(", ");
  const installCommand = `${status.command} -m pip install -e .`;
  return [
    status.message,
    missing ? `누락: ${missing}` : "",
    `프로젝트 폴더에서 \`${installCommand}\`를 실행한 뒤 다시 시도하세요.`,
  ].filter(Boolean).join("\n");
}

function assertPythonRuntime(status) {
  if (!status.ok) {
    throw new Error(formatPythonRuntimeError(status));
  }
}

module.exports = {
  REQUIRED_PYTHON_MODULES,
  assertPythonRuntime,
  buildPythonEnv,
  checkPythonRuntime,
  formatPythonRuntimeError,
};
