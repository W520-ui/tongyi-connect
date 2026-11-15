from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "通译智联 API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"
    workflow_db_path: Path = Path(__file__).resolve().parents[2] / "data" / "workflow.db"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("workflow_db_path")
    @classmethod
    def anchor_database_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            value = Path(__file__).resolve().parents[2] / value
        return value.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
