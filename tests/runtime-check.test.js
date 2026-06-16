const assert = require("assert");
const test = require("node:test");

const {
  REQUIRED_PYTHON_MODULES,
  checkPythonRuntime,
  formatPythonRuntimeError,
} = require("../electron/runtime-check");

test("checkPythonRuntime reports ready runtime", () => {
  const result = checkPythonRuntime({
    command: "python3",
    cwd: "/tmp",
    env: {},
    spawnSyncImpl: () => ({
      status: 0,
      stdout: JSON.stringify({ missing: [] }),
      stderr: "",
    }),
  });

  assert.equal(result.ok, true);
  assert.deepEqual(result.missing, []);
});

test("checkPythonRuntime maps missing modules to install packages", () => {
  const result = checkPythonRuntime({
    command: "python3",
    cwd: "/tmp",
    env: {},
    spawnSyncImpl: () => ({
      status: 0,
      stdout: JSON.stringify({ missing: ["playwright", "bs4"] }),
      stderr: "",
    }),
  });

  assert.equal(result.ok, false);
  assert.deepEqual(
    result.missing.map((item) => item.packageName),
    ["playwright", "beautifulsoup4"],
  );
});

test("formatPythonRuntimeError includes install command", () => {
  const message = formatPythonRuntimeError({
    ok: false,
    command: "python3",
    message: "Python 패키지가 설치되어 있지 않습니다.",
    missing: [REQUIRED_PYTHON_MODULES[0]],
  });

  assert.match(message, /playwright/);
  assert.match(message, /python3 -m pip install -e \./);
});
