"""
config.py — Application Configuration
All environment variables loaded from .env via pydantic-settings.
Import `settings` anywhere in the app — never read os.environ directly.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):

    # ─── Gemini API ───────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = Field(
    default="",
    description="Free API key from https://aistudio.google.com",
)
    GEMINI_MODEL: str = Field(
    default="gemini-2.0-flash",
    description="Gemini model — gemini-2.0-flash is free tier",
)

    # ─── App ──────────────────────────────────────────────────────────────────
    APP_NAME:    str = Field(default="Attack Path Analyzer")
    APP_VERSION: str = Field(default="1.0.0")
    DEBUG:       bool = Field(default=False)

    # ─── Mock Mode ────────────────────────────────────────────────────────────
    MOCK_MODE: bool = Field(
        default=True,
        description=(
            "True  → load nokia_telecom.json scenario (safe for demo day)\n"
            "False → fetch live data from kubectl"
        ),
    )
    MOCK_SCENARIO: str = Field(
        default="data/scenarios/nokia_telecom.json",
        description="Path to the mock scenario file",
    )

    # ─── Cluster ──────────────────────────────────────────────────────────────
    CLUSTER_NAME: str = Field(
        default="nokia-telecom-cluster",
        description="Display name shown in reports and the UI header",
    )
    KUBECTL_TIMEOUT: int = Field(
        default=30,
        description="Seconds before a kubectl command is considered failed",
    )

    # ─── Algorithm defaults ───────────────────────────────────────────────────
    BFS_MAX_HOPS:       int   = Field(default=3)
    CENTRALITY_TOP_N:   int   = Field(default=10)
    MAX_ATTACK_PATHS:   int   = Field(default=5)
    RISK_HIGH_THRESHOLD: float = Field(default=7.0)

    # ─── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed frontend origins",
    )

    class Config:
        env_file         = (".env", "app/.env")
        env_file_encoding = "utf-8"
        case_sensitive   = False


# Single shared instance — import this everywhere
settings = Settings()
