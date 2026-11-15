ERRORS = {
    "LLM_NOT_CONFIGURED": (503, "后端尚未配置模型密钥，无法生成回复"),
    "LLM_TIMEOUT": (504, "模型请求超时，请稍后重试"),
    "AGENT_RUN_TIMEOUT": (504, "智能体处理超时，请稍后重试"),
    "LLM_UPSTREAM_ERROR": (502, "模型服务暂时不可用，请稍后重试"),
    "LLM_BAD_RESPONSE": (502, "模型服务返回的响应无法解析，请稍后重试"),
    "CONVERSATION_BUSY": (409, "当前会话正在处理其他消息，请稍后重试"),
    "INTERNAL_ERROR": (500, "处理请求时发生错误，请稍后重试"),
}


class AppError(Exception):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.status_code, default_message = ERRORS[code]
        self.message = message or default_message
        super().__init__(self.message)
