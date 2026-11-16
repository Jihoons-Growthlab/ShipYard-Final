"""설정값. 환경 변수는 호출 시점에 읽는다(테스트에서 임시 경로로 바꿀 수 있게)."""
import os
import secrets
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TODAY = "2026-10-19"  # 기준일(모든 "오늘")

_PROCESS_SECRET = secrets.token_urlsafe(48)


def _path(env: str, default: str) -> Path:
    p = Path(os.environ.get(env) or default)
    return p if p.is_absolute() else REPO_ROOT / p


def db_path() -> Path:
    return _path("SHIPYARD_DB_PATH", "database/shipyard.db")


def file_dir() -> Path:
    return _path("SHIPYARD_FILE_DIR", "storage/drawings")


def report_dir() -> Path:
    """보고서 파일: <SHIPYARD_FILE_DIR의 부모>/reports (F14)."""
    return file_dir().parent / "reports"


def migrations_dir() -> Path:
    return REPO_ROOT / "database" / "migrations"


def seed_path() -> Path:
    return REPO_ROOT / "reference" / "seed" / "seed.json"


def app_secret() -> str:
    return os.environ.get("APP_SECRET") or _PROCESS_SECRET


def token_ttl() -> int:
    return int(os.environ.get("TOKEN_TTL") or 28800)


def otp_token_ttl() -> int:
    return int(os.environ.get("OTP_TOKEN_TTL") or 300)


def weather_provider() -> str:
    return (os.environ.get("WEATHER_PROVIDER") or "").strip()


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"


def ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL") or "qwen2.5:1.5b-instruct"


def ollama_timeout() -> float:
    return float(os.environ.get("OLLAMA_TIMEOUT") or 90)


def report_font() -> str:
    return os.environ.get("SHIPYARD_REPORT_FONT") or ""


def demo_enabled() -> bool:
    return os.environ.get("SHIPYARD_DEMO") == "1" and db_path().resolve() == (REPO_ROOT / "state/run/demo.db").resolve()
