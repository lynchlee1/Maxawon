import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv, set_key
except ImportError:  # pragma: no cover - dependency is optional at import time
    load_dotenv = None
    set_key = None

APP_DIR = Path.home() / ".weekly_mezz"
CONFIG_PATH = APP_DIR / "config.json"
ENV_PATH = APP_DIR / ".env"


def ensure_app_dir() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DIR


def load_environment() -> None:
    if load_dotenv is None:
        return
    local_env = Path.cwd() / ".env"
    if local_env.exists():
        load_dotenv(local_env)
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)


def get_api_key(default: str = "") -> str:
    load_environment()
    return os.getenv("OPENDART_API_KEY", default).strip()


def save_api_key(api_key: str) -> None:
    ensure_app_dir()
    if set_key is not None:
        if not ENV_PATH.exists():
            ENV_PATH.write_text("", encoding="utf-8")
        set_key(str(ENV_PATH), "OPENDART_API_KEY", api_key.strip())
    else:
        data = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
        lines = [line for line in data.splitlines() if not line.startswith("OPENDART_API_KEY=")]
        lines.append(f"OPENDART_API_KEY={api_key.strip()}")
        ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["OPENDART_API_KEY"] = api_key.strip()


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config: dict) -> None:
    ensure_app_dir()
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def get_config_value(name: str, default=None):
    return load_config().get(name, default)


def set_config_value(name: str, value) -> None:
    config = load_config()
    config[name] = value
    save_config(config)

