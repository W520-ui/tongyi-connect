# 通译智联后端

基于 FastAPI 的后端服务，提供版本化 API、自研进程内 Agent 运行时、跨境服务工作流、商品知识库和演示看板统计。Agent 与 API 同进程，不依赖任何外部 Agent 服务。

## 环境要求

- Python ≥ 3.11；本项目的 Windows 开发环境和 CI 使用 uv 管理的 Python 3.12。
- uv（当前锁文件和 CI 使用 0.8.0）。Windows 默认 `python` 可能仍是 3.10，不要直接用它创建环境。

## 本地运行

在 `backend/` 目录下执行：

```powershell
uv venv --python 3.12 --managed-python .venv
uv pip install -e ".[dev]"
uv lock --check
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run --extra dev uvicorn app.main:app --reload
```

`.venv` 必须放在 `backend/.venv`，根目录的 `scripts/dev-all.mjs` 会使用这个路径。无需激活虚拟环境，后续命令通过 `uv run` 执行。

需要严格按提交的锁文件安装时（CI 使用此方式）：

```bash
uv sync --frozen --extra dev
```

只有有意修改依赖时才执行 `uv lock`，并将 `pyproject.toml` 与 `uv.lock` 一起提交。

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

第 0 阶段新增 `WORKFLOW_DB_PATH` 环境变量，用于同时配置咨询归档和会话数据库。默认仍是 `backend/data/workflow.db`；相对路径以 `backend/` 为基准，绝对路径按原样使用。后续统一数据模型时再引入 `DATABASE_URL`。

```dotenv
WORKFLOW_DB_PATH=data/workflow.db
```

测试在导入应用之前就把数据库路径指向临时目录，每个测试运行时另用自己的临时数据库，不读取或写入真实的 `backend/data/`。测试模型是脚本化假模型，不调用真实上游。

## 测试

```bash
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev pytest
```

原有 unittest 用例也由 pytest 一并执行；仍可单独运行：

```bash
uv run --extra dev python -m unittest discover -s tests -v
```

接口测试冻结 `AgentWorkflowData` 的 18 个现有字段及类型，允许后续增加字段。`tests/test_known_defects.py` 覆盖说明中的缺陷 1–12，使用 `xfail(strict=True, raises=AssertionError)`：预期失败表示缺陷已复现，意外通过或非断言异常都必须处理。第 1 阶段修复 1–11，第 2 阶段修复 12；不能通过删掉断言或放宽标记来通过验收。

演示流程的 API 冒烟测试：

```bash
uv run --extra dev pytest tests/test_demo_smoke.py -v
```

CI 分为后端和前端两个独立任务；前端在仓库根目录执行 `npm ci`、`npm run build`。

## 真实模型手动验证

自动化测试只验证脚本化模型下的接口和数据流程，不代表真实模型效果已经验证。手动验证前在后端 `.env` 填好可用的 `AGENT_LLM_BASE_URL`、`AGENT_LLM_MODEL`、`AGENT_LLM_API_KEY`，密钥只留在后端。按上面的命令安装后端依赖，再在主 worktree 根目录执行 `npm ci`、`npm run dev`，打开 `http://127.0.0.1:5173/`。

1. 工作台发送“请用英文回复：星云降噪耳机 Pro 支持发往西班牙吗？”，确认商品为星云耳机、物流意图被识别、对客回复为英文，时效与商品资料的 5–8 个工作日一致。
2. 在同一会话发送“那它的物流要多久？”，确认沿用耳机商品上下文，回复没有改成其他商品的时效。
3. 发送“客户说耳机收到后无法开机，帮我登记售后”，确认出现人工接管记录；点击“确认接管”，确认待处理队列减少、归档标记已接管。
4. 检查看板咨询累计增加 3、人工接管累计增加 1、待处理回到发送前的数量；意图分布、语言分布和最近归档应体现这三条消息，再在设置页检查后端健康状态。

第 0 阶段只建立安全网，已知缺陷仍保留。真实模型验证时不要把尚未修复的中文摘要翻译、语言偏好持久化或接管后暂停行为当作已完成能力。阶段验收及提交记录见 `PHASE_0.md`。

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
