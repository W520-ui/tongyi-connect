from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "通译智联 API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"
    workflow_db_path: Path = Path(__file__).resolve().parents[2] / "data" / "workflow.db"
    llm_base_url: str = Field(
        default="https://api.openai.com/v1", validation_alias="AGENT_LLM_BASE_URL"
    )
    llm_api_key: SecretStr | None = Field(default=None, validation_alias="AGENT_LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", validation_alias="AGENT_LLM_MODEL")
    llm_timeout_seconds: float = Field(
        default=60, gt=0, validation_alias="AGENT_LLM_TIMEOUT_SECONDS"
    )
    llm_temperature: float = Field(
        default=0.3, ge=0, le=2, validation_alias="AGENT_LLM_TEMPERATURE"
    )
    llm_max_tokens: int | None = Field(default=None, ge=1, validation_alias="AGENT_LLM_MAX_TOKENS")
    max_tool_rounds: int = Field(default=4, ge=1, le=10, validation_alias="AGENT_MAX_TOOL_ROUNDS")
    run_timeout_seconds: float = Field(
        default=60, gt=0, lt=70, validation_alias="AGENT_RUN_TIMEOUT_SECONDS"
    )
    tool_timeout_seconds: float = Field(
        default=10, gt=0, validation_alias="AGENT_TOOL_TIMEOUT_SECONDS"
    )
    session_ttl_hours: int = Field(default=24, ge=1, validation_alias="AGENT_SESSION_TTL_HOURS")
    max_history_turns: int = Field(
        default=10, ge=1, le=50, validation_alias="AGENT_MAX_HISTORY_TURNS"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    model_config = SettingsConfigDict(
        env_file=Path(__file__).absolute().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("workflow_db_path")
    @classmethod
    def anchor_database_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            value = Path(__file__).resolve().parents[2] / value
        return value.resolve()

    @property
    def is_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_api_key.get_secret_value().strip())
