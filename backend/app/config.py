"""
config.py - Application configuration loaded from .env via pydantic-settings.
Import `settings` anywhere in the app rather than reading os.environ directly.
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "app/.env", "backend/app/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    SLACK_WEBHOOK_URL: str = Field(
    default="",
    description=(
        "Slack Incoming Webhook URL. "
        "Get one free at https://api.slack.com/apps → Incoming Webhooks"
    ),
)

    # Groq API
    GROQ_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("GROQ_API_KEY", "Groq_API_KEY", "GROK_API_KEY", "Grok_API_KEY"),
        description="API key from https://console.groq.com",
    )
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        validation_alias=AliasChoices("GROQ_MODEL", "Groq_MODEL", "GROK_MODEL", "Grok_MODEL"),
        description="Groq model used for narration",
    )

    # NVD API
    NVD_API_KEY: str = Field(
        default="",
        description="Optional API key for NIST NVD (increases rate limit)",
    )

    # App
    APP_NAME: str = Field(default="Attack Path Analyzer")
    APP_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=False)

    # Mock mode
    MOCK_MODE: bool = Field(
        default=True,
        description=(
            "True  -> load nokia_telecom.json scenario (safe for demo day)\n"
            "False -> fetch live data from kubectl"
        ),
    )
    MOCK_SCENARIO: str = Field(
        default="data/scenarios/nokia_telecom.json",
        description="Path to the mock scenario file",
    )

    # Cluster
    CLUSTER_NAME: str = Field(
        default="nokia-telecom-cluster",
        description="Display name shown in reports and the UI header",
    )
    KUBECTL_TIMEOUT: int = Field(
        default=30,
        description="Seconds before a kubectl command is considered failed",
    )

    # Algorithm defaults
    BFS_MAX_HOPS: int = Field(default=3)
    CENTRALITY_TOP_N: int = Field(default=10)
    MAX_ATTACK_PATHS: int = Field(default=5)
    RISK_HIGH_THRESHOLD: float = Field(default=7.0)

    # ── Real-time monitoring ──────────────────────────────────────────────────
    ENABLE_WATCH_API: bool = Field(
        default=True,
        description="Enable K8s Watch API for real-time monitoring (ignored in MOCK_MODE)",
    )
    WATCH_DEBOUNCE_MS: int = Field(
        default=2000,
        description="Debounce window for K8s events (ms). Prevents analysis thrashing on burst changes.",
    )
    ALERT_RISK_DELTA_THRESHOLD: float = Field(
        default=1.0,
        description="Minimum risk score delta to trigger a watch alert (e.g. 6.2→7.5 = 1.3 > 1.0 → alert)",
    )
    ALERT_ON_NEW_PATHS: bool = Field(
        default=True,
        description="Send alert when new attack paths are detected by Watch API",
    )
    ALERT_ON_NEW_CYCLES: bool = Field(
        default=True,
        description="Send alert when new privilege escalation cycles are detected",
    )
    WATCH_RECONNECT_DELAY_SEC: int = Field(
        default=5,
        description="Seconds to wait before reconnecting Watch API after a failure",
    )
    FALLBACK_POLL_INTERVAL_SEC: int = Field(
        default=300,
        description="Fallback polling interval (seconds) when Watch API is unavailable",
    )

    # CORS
    CORS_ORIGINS: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        description="Allowed frontend origins",
    )


settings = Settings()
