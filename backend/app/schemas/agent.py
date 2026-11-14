from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enable_streaming: bool = False


class AgentChatRequest(BaseModel):
    """项目对外的统一 Agent 请求模型。"""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=20_000)
    session_id: str | None = None
    username: str | None = None
    locale: str = "zh-CN"
    flags: AgentFlags = Field(default_factory=AgentFlags)


class AgentChatResponse(BaseModel):
    """项目统一的 Agent 响应信封，data 为 AgentWorkflowData。"""

    status: str
    data: Any = None
    message: str | None = None
