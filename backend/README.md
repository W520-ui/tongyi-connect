# 通译智联后端

FastAPI 服务内运行自研 Agent，通过共享的 httpx 客户端直连 OpenAI 兼容的 `/chat/completions`。第 2 阶段已统一会话、消息、运行与工单的数据库状态，保留现有前端接口。

## 环境与启动

需要 Python ≥ 3.11。Windows 默认 Python 可能为 3.10；本项目用 uv 0.8.0 管理 Python 3.12，虚拟环境保持在 `backend/.venv`，根目录启动脚本依赖这个路径。

在 `D:\10178\Projects\tongyi-connect\backend` 执行：

```powershell
uv venv --python 3.12 --managed-python .venv
uv pip install -e ".[dev]"
uv sync --frozen --extra dev
uv lock --check
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run --frozen --extra dev uvicorn app.main:app --reload
```

有意调整依赖时才运行 `uv lock`，并提交锁文件。默认地址为 `http://127.0.0.1:8000`；`DEBUG=true` 时可访问 `/docs`、`/openapi.json`。主 worktree 根目录安装前端依赖后执行 `npm run dev`，可以同时启动现有前后端。

`app.main:app` 保留旧启动入口，首次 ASGI 调用创建应用。导入模块不读取环境文件、不连接数据库或构造 HTTP 客户端。lifespan 创建数据库、客户端、服务及后台任务管理器，挂到 `app.state`；退出或启动失败时关闭资源。

## 模块与依赖

| 模块 | 职责 |
|---|---|
| `core/config.py`、`db.py` | 唯一 Settings、异步数据库资源、SQLite 连接设置、执行迁移 |
| `core/errors.py`、`locks.py`、`logging.py`、`background.py` | 错误码、可替换锁协议、密钥遮蔽、后台任务生命周期 |
| `domain/` | 纯领域类型、枚举、消息与工具轨迹 |
| `repositories/models.py`、`conversations.py` | SQLAlchemy 模型、消息追加、版本校验、会话别名 |
| `repositories/analytics.py`、`seed.py` | SQL 看板读取、初始化种子 |
| `services/conversation.py` | 唯一入站入口，命令、锁、运行、统一保存及分析 |
| `services/catalog.py`、`analytics.py`、`handoff.py` | 商品规则、统计、接管与重置 |
| `agent/runtime.py`、`events.py`、`effects.py` | 异步事件、工具循环与类型化副作用；运行器不写数据库 |
| `agent/context.py`、`analysis.py`、`guardrails.py`、`commands.py` | 记忆、结构化分析、关键词兜底、本地指令 |
| `agent/llm/`、`agent/tools/` | httpx 模型协议、Pydantic 工具参数及依赖 Protocol |
| `agent/prompts/system_v2.txt` | 当前版本化提示词，不注入关键词“本轮业务分析” |
| `api/v1/schemas/`、`presenters.py` | HTTP 结构和卡片组装 |
| `seed/`、`migrations/`、`scripts/` | 源码种子、Alembic 迁移、种子/OpenAPI/评测入口 |
| `evals/` | 30 条典型咨询及真实模型评测说明 |

依赖方向为 `api → services → agent 或 repositories → domain`，各层可以使用 core。Agent 通过 Protocol 获取商品数据，不依赖 API、服务或仓储；domain 不依赖其他应用层。HTTP 模型只放在 `api/v1/schemas/`，工具参数模型放在 `agent/tools/`。AST 导入扫描测试检查这些约束，随全部测试进入 CI。

## 配置与数据库

后端环境文件锚定为 `backend/.env`，不随当前目录变化。密钥仅放后端环境变量或该文件；Settings 用 SecretStr，HTTP 错误隐藏原始上游内容，日志格式化遮蔽当前模型密钥。

| 配置 | 默认值 | 含义 |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///data/app.db` | 相对路径锚定 backend；本次只支持文件型 SQLite |
| `AGENT_LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容地址 |
| `AGENT_LLM_API_KEY` | 未配置 | 未配置时普通聊天返回 503；本地指令仍可执行 |
| `AGENT_LLM_MODEL` | `gpt-4o-mini` | 主模型 |
| `AGENT_LLM_TIMEOUT_SECONDS` | 60 | 单次调用超时；连接建立最多等待 5 秒 |
| `AGENT_LLM_TEMPERATURE` | 0.3 | 温度，0–2 |
| `AGENT_LLM_MAX_TOKENS` | 不发送 | 可选正整数输出上限 |
| `AGENT_RUN_TIMEOUT_SECONDS` | 60 | 主运行总时限，大于 0、小于前端的 70 秒；分析使用剩余预算 |
| `AGENT_TOOL_TIMEOUT_SECONDS` | 10 | 单工具超时 |
| `AGENT_MAX_TOOL_ROUNDS` | 4 | 最后一轮禁用工具、强制文本回复 |
| `AGENT_CONTEXT_TOKEN_BUDGET` | 8192 | 系统、当前消息及历史的估算 token 预算 |
| `AGENT_TOOL_RESULT_MAX_CHARS` | 2000 | 单条历史工具结果的字符上限 |
| `AGENT_SUMMARY_ENABLED` | false | 历史超预算时，回复后异步生成摘要 |
| `AGENT_ANALYSIS_ENABLED` | true | 启用结构化事后分析 |
| `AGENT_ANALYSIS_MODEL` | 主模型 | 可选分析模型，共用 HTTP 客户端 |
| `AGENT_ANALYSIS_TIMEOUT_SECONDS` | 10 | 分析与可选摘要的超时上限 |

旧 `WORKFLOW_DB_PATH`、按条数裁剪和 TTL 配置已退役。新库包含 merchants、conversations、messages、agent_runs、handoff_tickets、products、shipping_rules，以及支持旧会话标识、持久化失败计数和启动时间的辅助表。所有业务表带 merchant_id，只种默认商家 demo。

应用启动执行 Alembic 到 head，在空商品目录中初始化种子；SQLite 启用 WAL、外键和 busy_timeout。消息有会话内唯一 seq，数据库触发器禁止更新，正常处理只追加。同一会话最多一张 open/acknowledged 工单。看板在同一读事务中聚合实际客户消息、运行与工单；服务重启不会清零失败数。普通模型失败会保存客户消息和 error 运行，不保存助手回复或成功归档，该客户消息按 A.2 计入咨询数。

D5：旧 `backend/data/workflow.db` 不读取、不迁移，旧表代码路径已删除；本阶段从新库开始。重建会清空所配置新库的演示会话、消息、运行及工单，恢复原始三个商品和 ES 规则。请先停止使用该库的服务，再执行：

```powershell
uv run --frozen --extra dev python -m app.scripts.seed
uv run --frozen --extra dev alembic current
uv run --frozen --extra dev alembic upgrade head
```

指定临时库可先设置 `$env:DATABASE_URL = "sqlite+aiosqlite:///$env:TEMP/tongyi-demo.db"`。源码种子在 `app/seed/`，不能放在被忽略的 data 目录。

## 工具、记忆与分析

工具仍为 `catalog_search`、`catalog_quote`、`catalog_shipping`、`catalog_specs`、`after_sales_record`；没有知识库数据源时不注册 knowledge_search。同轮并发执行，坏 JSON、未知工具、参数校验、异常及超时均转成工具错误供模型纠正，保留真实轨迹。最后一轮强制文本；总时限、流式工具片段和截断均记录。

商品仍为单一美元价；报价工具可以记住 quantity，不生成阶梯折扣。配送只确认 ES 的三条种子规则，其他有效国家返回 unconfirmed、要求商家确认；Mars 必须参数校验失败，不能当成未知国家正常返回。商品卡片与关注状态来自成功工具的 FocusProducts 或已有状态，关键词及事后分析不会替模型确定商品。

ContextBuilder 实时读取关注商品，注入目的国、数量、reply_language、接管状态和已有摘要。显式 reply_language 优先，否则要求按客户最新消息的语言回复，不把关键词检测结果写成语言指令。历史从新到旧按字符估算 token 预算，带 tool_calls 的助手消息与全部结果整组保留或丢弃，超长工具结果截断。系统规则和最新客户消息始终保留；它们本身超出预算时，历史全部省略。可选摘要在回复后运行，带版本条件保存，失败不影响已经落库的回复。

事后分析优先请求 JSON Schema，网关拒绝 response_format 时改用只输出 JSON 的提示，再校验意图、语言、商品、人工标注及中文摘要。外文咨询要求中文译文；关闭、超时或校验失败时返回 heuristic 来源，不能声称该兜底已完成翻译。分析只标注，不创建/取消工单，也不修改商品状态。主运行事务先保存消息、effects、状态与运行，分析随后在独立事务更新 outcome 和归档卡片。token 用量保存主运行及成功解析分析返回的用量。

连接错误、429 和 5xx 最多重试两次，指数退避并遵守 Retry-After；已输出的流不重试，读取超时不重试。所有上游错误返回通用中文消息和错误码。

## 人工接管与指令（D4）

状态顺序为 `bot_active → pending_human → human_active → resolved`：

1. 售后工具、强制护栏或 /handoff 创建一张工单，进入 pending_human。机器人继续回答，已有未解决工单时复用它。
2. 商家确认 open 工单后，它变为 acknowledged，会话进入 human_active。普通客户消息只保存 user 记录，不调用主模型或分析，不生成助手历史；返回固定暂停提示。
3. 服务方法 `HandoffService.resolve(ticket_id)` 可解决 open/acknowledged 工单，会话进入 resolved；下一条普通客户消息恢复 bot_active。
4. /reset 关闭旧会话及未解决工单，新建 UUID 会话，清空偏好与状态，保留旧消息。旧 session_id 别名跟随新会话，保持现有前端可用。

暂停提示优先采用 reply_language，否则检测最近客户消息；无法判断时为中文：

- zh-CN：已转人工，商家会尽快回复您。
- en-US：You've been connected to our team. A staff member will reply shortly.
- es-ES：Le hemos transferido a nuestro equipo. Un agente le responderá en breve.

按负责人明确的澄清，human_active 期间仍执行所有本地斜杠指令，只暂停普通消息。/help、/product、/lang、/handoff、/reset 及未知斜杠指令均不进入消息历史或咨询统计。/lang 仅接受 zh-CN、en-US、es-ES。旧确认接口已支持真实暂停；解决方法在服务层验证，新解决 HTTP 接口在第 3 阶段交付。

同会话锁采用可替换 Protocol，串行处理；version 条件更新阻止过期快照覆盖。不同进程竞争时过期写入返回 CONVERSATION_BUSY，尚未提供数据库级队列或多实例透明串行。内部已有普通/暂停消息的 client_message_id 重放支持；旧聊天请求字段保持不变，新 HTTP 幂等入口留到第 3 阶段。

## 兼容接口与 OpenAPI

旧 /agent/chat、/dashboard/overview、/dashboard/recent、/dashboard/handoffs、确认接管、/catalog/products、/health 路径和原请求字段保留，工作流原 18 字段的名称、类型不变，仅增加状态/消息/运行/分析字段。最近归档实际返回 conversation_id，等于 session_id，id 为运行 ID；接管队列的 id 改为工单 ID，确认接管也按工单 ID 处理。待接管队列保留触发运行的回复、中文摘要和原始 issue_summary。

/status 返回 version、llm_configured、model、db_ok；未配置模型时 model 为 null。不启动服务导出 OpenAPI：

```powershell
uv run --frozen --extra dev python -m app.scripts.export_openapi
uv run --frozen --extra dev python -m app.scripts.export_openapi --output "$env:TEMP/tongyi-openapi.json"
```

默认 backend/openapi.json 被忽略。导出不创建数据库或连接模型，当前仅包含已交付接口；新会话/工单 API、SSE、统一校验错误信封和商家鉴权占位留到第 3 阶段。

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
uv run --frozen --extra dev python -m app.scripts.eval_agent --list
```

缺陷 1–12 均为必须通过的回归，没有 xfail。Mars 验证工具失败标记、参数校验错误码、非空错误信息和 HTTP 失败轨迹；西语摘要用脚本化的分析结果验证。另覆盖统一事务回滚、并发顺序、版本冲突、状态机、只追加消息、迁移/种子、完整工具组、背景摘要及分析回退。所有测试使用临时数据库和假模型，不访问真实 data 或上游。

CI 后端检查锁文件、ruff 和全部测试；主 worktree 根目录前端任务执行 npm ci、npm run build、npm run test --if-present。现有前端没有 test 脚本，会正常跳过；这不能作为新前端 Vitest 通过的证据。

## 演示验证

自动化四步：`uv run --frozen --extra dev pytest tests/test_demo_smoke.py -v`。通过 API 检索耳机与 ES 配送、同会话追问、售后登记并确认、检查看板与健康。咨询量 3、接管量 1、待处理和失败 0、解决率 66.7%；断言真实工具消息、完整历史、最近归档 conversation_id 和确认状态。该冒烟用例关闭额外分析，以固定原演示统计；结构化分析另有专门回归。

真实模型手动步骤（需可用密钥；自动化结果不代表真实效果已经验证）：

1. 配置 backend/.env 的模型地址、名称与密钥，保持分析启用。主 worktree 根目录运行 npm ci、npm run dev，打开 http://127.0.0.1:5173/，记录看板基线。发送“请用英文回复：星云降噪耳机 Pro 支持发往西班牙吗？”，核对英文回复、耳机卡片、成功的 catalog_search/catalog_shipping 及 5–8 个工作日。
2. 同会话发送“那它的物流要多久？”，核对沿用 headset-pro 与 ES，没有换商品或编造时效；在网络响应检查 analysis_source 和中文摘要。
3. 发送“客户说耳机收到后无法开机，帮我登记售后”，核对真实问题与原因、中文摘要及队列中的回复；点击确认接管，队列减少，状态为 human_active。
4. 看板比基线新增 3 条咨询、1 张工单，最近咨询的 conversation_id 与聊天相同；核对语言和意图标注，并检查设置页健康和 /api/v1/status。

确认后再发“¿Envían a España?”，应返回西语暂停提示，不调用模型，仅增加一条客户消息；执行 /lang en-US、/help 不增加咨询数，再发中文消息应返回英文暂停提示。服务层的解决和恢复验证命令为 `uv run --frozen --extra dev pytest tests/test_phase2_state.py -v`，目前没有解决工单 HTTP 路由。

独立会话再检查 AQ、Mars、三句西语与 /reset：未知国家需商家确认；Mars 若调用工具则必须校验失败；无偏好西语跟随客户，有 /lang 偏好则持续采用偏好；reset 返回新 UUID 且旧消息仍保存。缺陷 12 的西语输入为“Hola, ¿cuánto tarda el envío de los auriculares a México?”，核对物流意图和包含“你好，耳机寄往墨西哥需要多长时间？”含义的中文译文。

30 条真实模型评测、按 case 运行及报告通过率的命令见 evals/README.md。评测使用临时数据库，实际会调用上游，不进入 CI；结果目录被忽略。正则评分只作可复核基线，译文准确性、否定句及承诺仍需人工检查。

阶段证据和恢复入口见 PHASE_0.md、PHASE_1.md、PHASE_2.md。TODO(owner) 仍为确认真实物流范围；根目录 README 由 Claude 在前端分支统一维护。
