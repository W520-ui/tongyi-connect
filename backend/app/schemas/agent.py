from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enable_inline_genui: bool | None = None
    enable_default_system_prompt: bool | None = None
    enable_streaming: bool = False
    enable_reasoning: bool | None = None


class AgentChatRequest(BaseModel):
    """项目对外的统一 Agent 请求模型。"""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=20_000)
    session_id: str | None = None
    username: str | None = None
    locale: str = "zh-CN"
    config_id: str | None = None
    config_name: str | None = None
    selected_provider: str | None = None
    selected_model: str | None = None
    flags: AgentFlags = Field(default_factory=AgentFlags)


class AgentChatResponse(BaseModel):
    """透传 AstrBot 的标准成功信封，保留其 data 结构。"""

    status: str
    data: Any = None
    message: str | None = None
