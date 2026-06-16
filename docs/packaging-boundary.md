# Packaging Boundary

This project keeps the distributable app small by packaging only the files needed
at runtime.

## Included in the Electron build

- `electron/**/*`: Electron main, preload, renderer HTML, CSS, and JavaScript.
- `package.json`: Electron app metadata used by the packaged app.
- Python runtime modules under `src/**`, copied through `extraResources` so
  Python can import them as normal files.

## Runtime prerequisite

The app uses the user's installed Python 3 and checks required Python packages
before starting Cretop capture or Weekly Mezz collection. If a package is
missing, the app reports the missing module and asks the user to run:

```bash
python3 -m pip install -e .
```

## Not included in the Electron build

- `AGENTS.md`, `README.md`, and `docs/**`.
- `tests/**` and Python test/tool caches.
- Local browser profiles such as `.chrome-profile/**`.
- Runtime network logs such as `network-logs/**` and `logs/**`.
- Runtime capture output such as `output/**`.
- User-provided or exported business data such as `data/**`, `input/**`,
  `exports/**`, `downloads/**`, `*.xlsx`, `*.xlsm`, `*.xls`, and `*.csv`.
- Playwright browser downloads such as `ms-playwright/**`,
  `.local-browsers/**`, `chromium*/**`, and `chrome-*/**`.

## Runtime-generated directories

The packaged app writes runtime files under Electron's `userData` directory, not
inside the installed application directory.

- Chrome profile: `<userData>/chrome-profile`
- Network logs: `<userData>/network-logs`
- Default table capture output: `<userData>/output/maxawon_condition_search.csv`

## Browser policy

The app uses the user's installed Chrome. Do not package Chromium, Playwright
browser downloads, or browser-stealth tooling with the app.
