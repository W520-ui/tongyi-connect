from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Configuration for the in-process agent runtime (AGENT_* variables)."""

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 60.0
    max_tool_rounds: int = Field(default=4, ge=1, le=10)
    session_ttl_hours: int = Field(default=24, ge=1)
    max_history_turns: int = Field(default=10, ge=1, le=50)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AGENT_",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.llm_api_key)


@lru_cache
def get_agent_settings() -> AgentSettings:
    return AgentSettings()
