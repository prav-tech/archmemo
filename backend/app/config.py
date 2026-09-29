"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Override via .env or environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Hindsight ──────────────────────────────────────────────────────────
    hindsight_base_url: str = "http://localhost:8888"
    hindsight_api_key: str = ""
    hindsight_bank_id: str = "architecture_decisions"

    # ── LLM ───────────────────────────────────────────────────────────────
    llm_provider: str = "groq"          # groq | openai
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen/qwen3-32b"   # or openai/gpt-oss-120b
    llm_temperature: float = 0.1        # low temp for grounded, factual answers
    llm_max_tokens: int = 4096
    llm_timeout_seconds: float = 60.0

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./archmemory.db"

    # ── Auth ──────────────────────────────────────────────────────────────
    # Every /api route except /api/auth/login, /api/auth/logout and /api/health
    # requires a session. Turn this off only for local experiments.
    auth_enabled: bool = True
    jwt_secret_key: str = ""            # required when auth is enabled; >= 32 chars
    jwt_algorithm: str = "HS256"        # HS256 | HS384 | HS512
    jwt_expire_minutes: int = 60 * 24   # 24 hours
    # The browser session is an httpOnly cookie holding the JWT. Set the cookie
    # to secure=true whenever the app is served over HTTPS.
    auth_cookie_name: str = "archmemory_session"
    auth_cookie_secure: bool = False
    # First-run bootstrap: if the users table is empty and ADMIN_PASSWORD is set,
    # this account is created at startup. Later changes to these values do nothing.
    admin_username: str = "admin"
    admin_password: str = ""
    # Login throttle (per username, per process).
    login_max_failures: int = 5
    login_lockout_seconds: int = 300

    # ── App ───────────────────────────────────────────────────────────────
    app_name: str = "ArchMemory"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]

    # ── Recall ────────────────────────────────────────────────────────────
    # Hindsight recall returns extracted *facts*, several per decision, so this
    # needs to be well above the number of decisions we expect to cite.
    recall_top_k: int = 15
    recall_query_max_chars: int = 2000  # proposals are truncated to this for the recall query


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton – call this everywhere."""
    return Settings()
