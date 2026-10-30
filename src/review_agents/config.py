from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service settings, read once from `REVIEW_AGENTS_*` environment variables."""

    model_config = SettingsConfigDict(env_prefix="REVIEW_AGENTS_", frozen=True)

    data_dir: Path = Path("data")
    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)
    worker_poll_seconds: float = Field(default=2.0, gt=0)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "review-agents.sqlite3"
