from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    app_name: str = "通译智联 API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///data/app.db"
    merchant_id: str = "demo"
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
    context_token_budget: int = Field(
        default=8192, ge=128, validation_alias="AGENT_CONTEXT_TOKEN_BUDGET"
    )
    tool_result_max_chars: int = Field(
        default=2000, ge=100, validation_alias="AGENT_TOOL_RESULT_MAX_CHARS"
    )
    summary_enabled: bool = Field(default=False, validation_alias="AGENT_SUMMARY_ENABLED")
    analysis_enabled: bool = Field(default=True, validation_alias="AGENT_ANALYSIS_ENABLED")
    analysis_model: str | None = Field(default=None, validation_alias="AGENT_ANALYSIS_MODEL")
    analysis_timeout_seconds: float = Field(
        default=10, gt=0, validation_alias="AGENT_ANALYSIS_TIMEOUT_SECONDS"
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
        validate_default=True,
    )

    @field_validator("database_url")
    @classmethod
    def anchor_database_path(cls, value: str) -> str:
        url = make_url(value)
        if url.drivername != "sqlite+aiosqlite" or not url.database or url.database == ":memory:":
            raise ValueError("Use a file-backed sqlite+aiosqlite DATABASE_URL for this demo")
        path = Path(url.database)
        if not path.is_absolute():
            path = Path(__file__).absolute().parents[2] / path
        return url.set(database=str(path.resolve())).render_as_string(hide_password=False)

    @property
    def is_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_api_key.get_secret_value().strip())
