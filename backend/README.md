# 通译智联后端

FastAPI 服务内运行自研 Agent，通过共享的 httpx 客户端直连 OpenAI 兼容的 `/chat/completions`。第 1 阶段已拆分模块边界、修复缺陷 1–11，并保留旧前端使用的全部接口。

## 环境与启动

需要 Python ≥ 3.11。Windows 默认 Python 可能是 3.10；本项目使用 uv 0.8.0 管理 Python 3.12，虚拟环境必须位于 `backend/.venv`，根目录的 `scripts/dev-all.mjs` 依赖这个路径。

在 `D:\10178\Projects\tongyi-connect\backend` 执行：

```powershell
uv venv --python 3.12 --managed-python .venv
uv pip install -e ".[dev]"
uv sync --frozen --extra dev
uv lock --check
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run --frozen --extra dev uvicorn app.main:app --reload
```

只有有意调整依赖时才执行 `uv lock`，并提交对应锁文件。服务默认地址为 `http://127.0.0.1:8000`；`DEBUG=true` 时可以访问 `/docs`、`/openapi.json`。也可在主 worktree 根目录安装前端依赖后执行 `npm run dev`，同时启动现有前后端。

`app.main:app` 保留现有启动入口，首次 ASGI 调用时创建应用。模块导入不读取环境配置文件、不打开数据库、不创建 HTTP 客户端。数据库、模型客户端和服务由 lifespan 创建、挂到 `app.state`，退出或启动中途失败时关闭已创建资源；API 通过依赖注入获取服务。

## 模块与依赖

| 目录或模块 | 职责 |
|---|---|
| `core/config.py` | 唯一 Settings；环境文件与数据库路径锚定到 backend |
| `core/errors.py`、`core/locks.py`、`core/logging.py` | 错误码、可替换的会话锁协议、日志密钥遮蔽 |
| `domain/` | 纯领域类型、枚举、消息和工具轨迹 |
| `repositories/session.py`、`archive.py` | 第 1 阶段旧 SQLite 表访问、持久化失败计数、SQL 聚合 |
| `services/conversation.py` | `handle_inbound` 入站唯一入口；指令、会话锁、effects 应用与保存 |
| `services/catalog.py`、`analytics.py`、`handoff.py` | 商品、看板统计、人工接管业务 |
| `agent/runtime.py`、`events.py`、`effects.py` | 异步事件运行器、真实工具轨迹、类型化副作用；运行器不写数据库 |
| `agent/context.py`、`guardrails.py`、`commands.py` | 上下文、单表关键词兜底、斜杠指令协议 |
| `agent/llm/` | complete/stream 协议与 OpenAI 兼容实现；不安装模型 SDK |
| `agent/tools/`、`registry.py` | Pydantic 参数校验、工具依赖 Protocol、超时和工具错误结果 |
| `agent/prompts/system_v1.txt` | 版本化系统提示词，不注入“本轮业务分析” |
| `api/v1/schemas/`、`presenters.py` | HTTP 请求与响应结构、旧卡片组装 |
| `seed/catalog.json`、`shipping_rules.json` | 三个演示商品与已知 ES 配送规则 |
| `scripts/export_openapi.py` | 不启动服务导出 OpenAPI |

依赖方向为 `api → services → agent 或 repositories → domain`，各层可以使用 core。Agent 不依赖 API、业务服务或仓储，工具数据通过 Protocol 注入。领域层不依赖其他应用层；HTTP 模型只放在 `api/v1/schemas/`，工具参数模型放在 `agent/tools/`。这些边界由 AST 导入扫描测试检查，并随全套测试进入 CI。

## 模型与数据配置

后端 `.env` 的路径始终是 `backend/.env`，不随启动目录变化。密钥只写在后端环境变量或该文件中；Settings 使用 SecretStr，HTTP 错误不返回原始上游内容，日志格式化时遮蔽当前模型密钥。

| 配置项 | 默认值 | 用途 |
|---|---|---|
| `AGENT_LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容服务地址 |
| `AGENT_LLM_API_KEY` | 未配置 | 模型密钥；未配置时聊天返回 503 |
| `AGENT_LLM_MODEL` | `gpt-4o-mini` | 主模型 |
| `AGENT_LLM_TIMEOUT_SECONDS` | 60 | 单次模型调用超时；连接建立最多等待 5 秒 |
| `AGENT_LLM_TEMPERATURE` | 0.3 | 温度，范围 0–2 |
| `AGENT_LLM_MAX_TOKENS` | 未设置 | 可选的正整数输出上限；不设置时不发送 max_tokens |
| `AGENT_RUN_TIMEOUT_SECONDS` | 60 | 整次 Agent 运行总时限，必须大于 0 且小于前端的 70 秒 |
| `AGENT_TOOL_TIMEOUT_SECONDS` | 10 | 单个工具超时 |
| `AGENT_MAX_TOOL_ROUNDS` | 4 | 模型调用最多 4 轮，最后一轮禁用工具并强制文本回复 |
| `AGENT_SESSION_TTL_HOURS` | 24 | 旧会话过期时间 |
| `AGENT_MAX_HISTORY_TURNS` | 10 | 当前按消息条数保留的上下文上限；工具调用与结果整组保留 |
| `WORKFLOW_DB_PATH` | `data/workflow.db` | 当前会话与归档共用的 SQLite 文件 |

`WORKFLOW_DB_PATH` 的相对路径锚定到 backend，绝对路径按原样使用。第 1 阶段继续使用 `agent_sessions` 和 `workflow_conversations`，增加显式回复语言、槽位、接管原因、问题摘要、工具轨迹、指令标记和工单创建标记；失败请求与首次启动时间也持久化。看板每次执行 SQL 聚合，多个 SELECT 在同一读事务中形成一致快照，服务重启不会清零失败数。

连接错误、429 和 5xx 最多重试 2 次（共 3 次请求），使用指数退避并遵守 Retry-After；已经开始输出的流不重试。读取超时不重试；连接超时重试耗尽后返回 `LLM_TIMEOUT`。重试和工具调用都受整次运行总时限约束，token 用量按轮累计。

## 工具与会话行为

只注册 5 个工具：`catalog_search`、`catalog_quote`、`catalog_shipping`、`catalog_specs`、`after_sales_record`。没有知识库数据源时不注册 `knowledge_search`。参数由 Pydantic 校验，结果为 `ToolOutput(content, ok, effects)`，关注商品、目的国与人工接管通过类型化 effects 交给业务服务处理。

每轮发送全部工具 schema，最后一轮使用 `tool_choice="none"`。未知工具、非法 JSON、参数校验失败、单工具超时和工具异常都作为 `role="tool"` 的失败结果回传模型并记入轨迹，请求可以继续。同轮工具使用 `asyncio.gather` 并发执行，事件及卡片 steps 保留实际完成顺序；流式工具参数按 index 拼接，在当轮流结束后执行。模型被长度截断时记录警告，并在持久化运行轨迹中标记 `truncated`。

配送参数 `destination` 必须是已分配的 ISO 3166-1 alpha-2 国家代码：

- 三个演示商品仅有 ES 可送达规则，时效分别为 5–8、6–10、7–12 个工作日，美元报价和商品资料保持原值。
- AQ 等其他有效国家代码查询成功，但返回 `availability="unconfirmed"`，要求商家确认，不承诺配送与时效。
- Mars、ZZ 等无效代码返回 `ok=false`、`TOOL_VALIDATION_ERROR` 和错误说明，由模型请客户确认目的地。
- `TODO(owner)`：确认真实配送范围；当前仅把 ES 当作已知演示事实。

匿名请求由服务端生成独立 session_id，并随响应返回。同会话使用可替换的 asyncio 锁按到达顺序处理；这是第 1 阶段的单进程保护，数据库乐观锁留到第 2 阶段。

`/help`、`/product`、`/lang`、`/reset`、`/handoff` 不进入模型消息历史，也不计入咨询量。`/lang` 只接受 zh-CN、en-US、es-ES，显式偏好独立于检测出的客户语言，持续用于后续回复。`/reset` 清空当前 session 的历史、商品和槽位，不从归档恢复商品；新建会话的完整 reset 语义留到第 2 阶段。`/handoff` 保存“用户主动请求人工接管”原因；模型登记售后会保存 issue_summary，未确认的接管记录不重复创建。

## 对外接口

现有请求字段和 AgentWorkflowData 原有 18 个字段的名字与类型保持不变。第 1 阶段只在工作流中新增 `session_id` 和 `trace`，最近归档新增 `conversation_id`（等于 session_id）。

| 方法与路径 | 用途 |
|---|---|
| `POST /api/v1/agent/chat` | 旧聊天接口，响应仍为 `{status, data, message}` |
| `GET /api/v1/catalog/products` | 演示商品 |
| `GET /api/v1/dashboard/overview` | SQL 看板统计 |
| `GET /api/v1/dashboard/recent` | 最近咨询 |
| `GET /api/v1/dashboard/handoffs` | 待确认的人工接管归档 |
| `POST /api/v1/dashboard/handoffs/{record_id}/acknowledge` | 确认旧接管记录 |
| `GET /api/v1/health` | 保留健康检查形状 |
| `GET /api/v1/status` | 提前交付模型配置状态与数据库健康状态 |

聊天请求示例：

```json
{
  "message": "请用英文回复：星云降噪耳机 Pro 支持发往西班牙吗？",
  "session_id": "demo-session-001",
  "username": "demo-user"
}
```

status 返回 `{status: "ok", data: {version, llm_configured, model, db_ok}}`；未配置密钥时 model 为 null，不暴露密钥。

模型与运行错误提供中文通用消息及错误码：`LLM_NOT_CONFIGURED`（503）、`LLM_UPSTREAM_ERROR`/`LLM_BAD_RESPONSE`（502）、`LLM_TIMEOUT`/`AGENT_RUN_TIMEOUT`（504）、`CONVERSATION_BUSY`（409）、`INTERNAL_ERROR`（500）。保留旧前端读取的顶层 detail，并增加结构化 error。请求校验仍使用旧接口的默认行为；第 3 阶段统一完整错误信封。

不启动服务导出 OpenAPI：

```powershell
uv run --frozen --extra dev python -m app.scripts.export_openapi
uv run --frozen --extra dev python -m app.scripts.export_openapi --output "$env:TEMP\tongyi-openapi.json"
```

默认生成 `backend/openapi.json`，由 .gitignore 忽略；导出不会创建数据库或连接模型。当前文档只包含已经交付的旧接口与 status；附录 A 的新会话、工单、幂等和 SSE 接口在第 3 阶段交付。

## 验证与 CI

在 backend 执行：

```powershell
uv sync --frozen --extra dev
uv lock --check
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
$env:PYTHONIOENCODING = "utf-8"
uv run --frozen --extra dev pytest
uv run --frozen --extra dev pytest tests/test_demo_smoke.py -v
```

原有测试已迁移到 pytest，保留原验证意图；统一通过 pytest 执行。缺陷 1–11 均为必须通过的回归，Mars 用例同时检查模型收到的失败标记、参数校验错误码和非空消息，并验证 HTTP 轨迹失败状态。只有第 2 阶段的缺陷 12 保留 `xfail(strict=True, raises=AssertionError)`。

新增验证覆盖未知工具、坏 JSON/参数、工具异常/超时、同轮并发、强制最后一轮文本、总时限与取消、流式片段、截断和 token 累计、模型重试/错误遮蔽、资源关闭、无资源构造的模块导入、架构边界及离线 OpenAPI。所有测试使用临时数据库和脚本化模型，不读取或写入真实 `backend/data/`，不调用真实上游。

CI 的后端任务执行锁文件检查、ruff 和全部测试；前端任务在主 worktree 根目录依次执行 `npm ci`、`npm run build`、`npm run test --if-present`。现有前端没有 test 脚本，会正常跳过；新前端合入后会执行其 Vitest 测试。不能以本分支的跳过结果声称新前端 Vitest 已通过。

## 演示验证

自动化命令 `uv run --frozen --extra dev pytest tests/test_demo_smoke.py -v` 使用 API 级四步冒烟测试：商品检索与 ES 配送、同会话追问、售后登记及确认、看板与健康检查。预期咨询量 3、接管量 1、待处理 0、失败 0、解决率 66.7%，英文 1 条、中文 2 条；真实工具消息和两问两答以上的完整历史保存到临时数据库。

真实模型手动步骤（自动化通过不代表真实模型效果已验证）：

1. 在后端 .env 配置可用的模型地址、名称和密钥；主 worktree 根目录执行 `npm ci`、`npm run dev`，打开 `http://127.0.0.1:5173/`。记录看板基线，发送“请用英文回复：星云降噪耳机 Pro 支持发往西班牙吗？”，确认英文回复、耳机商品，以及成功的 catalog_search/catalog_shipping 轨迹；时效应为 5–8 个工作日。
2. 同一会话发送“那它的物流要多久？”，确认沿用 headset-pro 与 ES，没有换成其他商品或编造时效。
3. 发送“客户说耳机收到后无法开机，帮我登记售后”，确认问题摘要和真实接管原因出现在商家队列；点击“确认接管”，确认待处理队列减少、归档标记已确认。
4. 看板咨询累计应比基线增加 3、人工接管增加 1；核对语言/意图分布、最近三条咨询，在设置页检查健康状态，并访问 `http://127.0.0.1:8000/api/v1/status` 检查模型与数据库状态。

另用独立会话验证“耳机能送往南极洲吗？”与“耳机能送往 Mars 吗？”：前者工具参数应为 AQ，结果为 unconfirmed，回复需商家确认；后者工具必须显示参数校验失败，请客户确认真实目的地。用 `/lang es-ES` 再发两条英文消息，确认回复持续采用西语；重置后确认不再携带商品。现有 UI 未显示结构化 trace 时，在浏览器网络面板查看聊天响应。

## 当前阶段边界

第 1 阶段仍使用旧表，会话保存与归档写入分开提交，尚未实现跨进程写入锁或统一事务。历史当前按条数裁剪，尚无完整 token 预算、长对话摘要。商家确认接管后暂停机器人、解决后的恢复、新 reset ID、统一 SQLAlchemy 表、结构化事后分析与外文中文译文都留到第 2 阶段；新的会话/工单 API、幂等、鉴权占位与 SSE 留到第 3 阶段。当前商家摘要仍是关键词结果与原始咨询组合，不应当作已完成翻译。

阶段交付记录与恢复入口见 `PHASE_0.md`、`PHASE_1.md`。根目录 README 仍有旧模块描述，按文件归属由负责人协调更新：`TODO(owner)` 更新自研 Agent 和工作流职责说明。
