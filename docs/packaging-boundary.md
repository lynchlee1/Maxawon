# Packaging Boundary

This project keeps the distributable app small by packaging only the files needed
at runtime.

## Included in the Electron build

- `electron/**/*`: Electron main, preload, renderer HTML, CSS, and JavaScript.
- `package.json`: Electron app metadata used by the packaged app.
- `dist-python/maxawon-worker`: bundled Python worker copied to `bin/`.
- Python runtime modules under `src/**`, copied through `extraResources` so
  development runs can import them as normal files.

## Runtime prerequisite

Development runs use the developer's installed Python 3 and checks required
Python packages before starting Cretop capture, 주간 메자닌 발행현황 collection, or
network logging. If a package is missing, the app reports the missing module and
asks the developer to run:

```bash
python3 -m pip install -e .
```

Packaged apps include a PyInstaller-built `maxawon-worker` executable under the
Electron resources directory and do not require users to install Python. Build it
before packaging:

```bash
python3 -m pip install -e ".[build]"
npm run build:python
```

`npm run dist`, `npm run dist:mac`, and `npm run dist:dir` run
`build:python` automatically for the current OS.

## Not included in the Electron build

- `AGENTS.md`, `README.md`, and `docs/**`.
- `tests/**` and Python test/tool caches.
- Local browser profiles such as `.chrome-profile/**`.
- Opt-in runtime network logs such as `network-logs/**` and `logs/**`.
- Runtime capture output such as `output/**`.
- User-provided or exported business data such as `data/**`, `input/**`,
  `exports/**`, `downloads/**`, `*.xlsx`, `*.xlsm`, `*.xls`, and `*.csv`.
- Playwright browser downloads such as `ms-playwright/**`,
  `.local-browsers/**`, `chromium*/**`, and `chrome-*/**`.

## Runtime-generated directories

The packaged app writes runtime files under Electron's `userData` directory, not
inside the installed application directory.

- Chrome profile: `<userData>/chrome-profile`
- Network logs: `<userData>/network-logs` when `MAXAWON_NETWORK_LOGS=1`
- Default table capture output: `<userData>/output/maxawon_condition_search.csv`

## Browser policy

The app uses the user's installed Chrome. Do not package Chromium, Playwright
browser downloads, or browser-stealth tooling with the app.
