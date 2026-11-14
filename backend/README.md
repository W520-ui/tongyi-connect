# 通译智联后端

基于 FastAPI 的后端服务，提供版本化 API、自研进程内 Agent 运行时、跨境服务工作流、商品知识库和演示看板统计。Agent 与 API 同进程，不依赖任何外部 Agent 服务。

## 环境要求

- Python 3.11 或更新版本

## 本地运行

在 `backend/` 目录下执行：

```bash
python -m venv .venv
```

Windows PowerShell 激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

安装项目依赖并启动开发服务：

```bash
python -m pip install -e .
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

服务默认运行在 `http://127.0.0.1:8000`。开发模式下可在 `/docs` 查看 API 文档，健康检查地址为 `/api/v1/health`。

## 自研 Agent 运行时

`app/agent/` 是运行时主体，与 FastAPI 同进程、零新增端口、无额外依赖：

| 模块 | 职责 |
|---|---|
| `engine.py` | `AgentEngine`：指令优先、会话加载、业务分析、受控 function calling 循环、归档 |
| `config.py` | `AGENT_*` 配置（pydantic-settings） |
| `models.py` | Message / ToolCall / Decision / Session / AgentContext / AgentError |
| `session.py` | `SessionStore`：SQLite 多轮会话、商品上下文、语言偏好、TTL |
| `registry.py` | `ToolRegistry`：工具注册、JSON Schema 导出、受控调用 |
| `commands.py` | `/help /reset /lang /product /handoff` |
| `prompts.py` | 系统提示词与业务上下文注入 |
| `providers/` | `LLMProvider` 协议 + OpenAI 兼容实现（httpx 直连，不安装 SDK） |
| `tools/` | catalog / handoff / knowledge 内置工具 |
| `hooks.py` | `on_tool_call` / `on_handoff` / `on_reply` 事件订阅 |

内置 6 个工具：`catalog_search`、`catalog_quote`、`catalog_shipping`、`catalog_specs`、`after_sales_record`、`knowledge_search`。工具名统一使用下划线，因为部分 OpenAI 兼容网关会拒绝带点号的 function name。

### 模型配置

复制 `.env.example` 为 `.env`，按需填写：

```dotenv
AGENT_LLM_BASE_URL=https://api.openai.com/v1
AGENT_LLM_API_KEY=你的模型_API_Key
AGENT_LLM_MODEL=gpt-4o-mini
AGENT_LLM_TIMEOUT_SECONDS=60
AGENT_MAX_TOOL_ROUNDS=4
AGENT_SESSION_TTL_HOURS=24
AGENT_MAX_HISTORY_TURNS=10
```

任何 OpenAI 兼容的 `/chat/completions` 端点（含本地 Ollama）都可直接接入。密钥只保存在后端环境变量中，浏览器不会接触。未配置密钥、模型不可用或工具循环超限时，`/api/v1/agent/chat` 返回 502/503 错误，不生成兜底回复。

### 对外接口

`POST /api/v1/agent/chat`，请求示例：

```json
{
  "message": "请用英文回复：这款产品支持发往西班牙吗？",
  "session_id": "demo-session-001",
  "username": "demo-user"
}
```

响应仍是 `{status, data, message}` 信封，`data` 为 `AgentWorkflowData`，`source` 为 `native` 或 `native+human-handoff`。前端契约未改变。

工作流接口：

- `GET /api/v1/catalog/products`：商品知识库
- `GET /api/v1/dashboard/overview`：咨询量、意图和人工接管统计
- `GET /api/v1/dashboard/recent`：最近咨询归档
- `GET /api/v1/dashboard/handoffs`：待人工接管队列
- `POST /api/v1/dashboard/handoffs/{record_id}/acknowledge`：商家确认接管

演示会话按 `session_id` 记忆最近命中的商品，方便客户用“它的物流呢？”等追问继续咨询。咨询摘要、商品上下文、接管状态与会话历史存储于 `backend/data/workflow.db`，服务重启后保留。

## 配置

复制 `.env.example` 为 `.env`，按需调整应用名称、调试模式、日志级别、API 前缀和前端跨域来源。敏感配置不要提交到版本库。

模型连接建立超时为 5 秒，避免服务未启动时等待过久；模型生成仍使用完整的超时时间。

## 测试

```bash
python -m unittest discover -s tests -v
```

## 目录结构

```text
backend/
├── app/
│   ├── agent/        自研 Agent 运行时
│   ├── api/          API 路由及版本入口
│   ├── core/         配置与应用基础设施
│   ├── models/       持久化模型预留
│   ├── repositories/ 数据访问层预留
│   ├── schemas/      请求和响应模型
│   ├── services/     业务服务（workflow / agent 适配）
│   └── main.py       FastAPI 应用入口
├── tests/
├── .env.example
└── pyproject.toml
```
