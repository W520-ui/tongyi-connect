# 重构任务说明：通译智联（后端）

> **给负责人：** 先逐条确认或修改第 2 节的决策，再把整份文件交给执行模型。执行模型需要能读写本仓库、运行命令。
>
> **给执行模型：** 本文件就是你的任务说明。**你只负责后端（`backend/` 目录）**；前端由另一位开发者（Claude）按 [`frontend-plan.md`](frontend-plan.md) 并行开发，双方只通过接口契约对接，协作规则见第 3 节"前后端协作"。问题清单、证据和目标架构的理由见 [`architecture-review.md`](architecture-review.md)。

## 1. 角色与目标

你是一名资深的 Python 后端工程师，要对仓库 `tongyi-connect`（通译智联：面向中小跨境商家的 AI 客服智能体）的后端做**分阶段的渐进式重构**。目标：

1. 理顺模块边界，依赖方向单一，并且能被自动检查；
2. 工具调用健壮，副作用真实、有类型；
3. 会话状态和记忆只有一个事实来源，并发安全；
4. 去掉单进程假设，为多实例部署留好路；
5. **每个阶段结束时，演示闭环都必须还能跑通。**

动手之前，完整阅读：`docs/architecture-review.md`、`README.md`、`backend/README.md`，以及 `backend/app/`、`backend/tests/` 下的全部代码；再看一遍 `src/services/`，了解前端现在怎么调用接口。

## 2. 决策（以本节为准）

本节没有覆盖、但会影响业务行为的问题（物流范围、价格、退款政策、对客户的承诺等），**不要自己发明**：停下来提问，或者留下 `TODO(owner)`，并在阶段汇报里列出来。

- **D1 多商家：** 所有业务表加 `merchant_id`；只种一个默认商家 `demo`；不做商家管理界面。
- **D2 物流与报价：** `catalog_shipping` 改为按 `shipping_rules` 查询，参数用 ISO 3166-1 alpha-2 国家代码（由模型负责把"西班牙""España"之类转换成 `ES`）。演示种子数据只把西班牙（`ES`）标为三个商品都可送达，时效沿用现有的 `shipping_days`（`TODO(owner)`：确认真实范围）；其他目的地返回 `"availability": "unconfirmed"`，模型必须告诉客户"需商家确认"，不得声称能送达。报价保持单一美元价，不做阶梯价。
- **D3 事后分析：** 启用一次结构化的"事后分析"调用，产出意图、语言、涉及的商品、是否需要人工、中文商家摘要（含外文咨询的中文译文）。配置项：`AGENT_ANALYSIS_ENABLED`（默认 `true`）、`AGENT_ANALYSIS_MODEL`（默认与主模型相同）。关闭或失败时退回关键词规则，并在结果里标明来源。事后分析只做标注，不创建工单。
- **D4 人工接管：** 会话状态机为 `bot_active → pending_human → human_active → resolved`，客户在 `resolved` 之后再发消息时回到 `bot_active`。
  - `pending_human`：机器人继续回答，但不重复创建工单；
  - `human_active`（商家确认接管之后）：机器人停止自动回复，只保存客户消息，返回固定提示"已转人工，商家会尽快回复您"（接口仍按 `AgentWorkflowData` 的结构返回）；
  - `resolved`：商家标记解决。
- **D5 旧数据：** 丢弃 `backend/data/workflow.db` 里的旧数据，不做迁移；提供 `python -m app.scripts.seed`，一键重建种子数据。
- **D6 依赖：** 允许新增后端依赖 `sqlalchemy>=2`、`alembic`、`aiosqlite`，开发依赖 `pytest`、`pytest-asyncio`、`import-linter`（前端依赖由前端负责人另行确认）。**不允许**引入任何模型 SDK（包括 OpenAI SDK）、LangChain 或其他 Agent 框架：Agent 运行时保持自研，用 httpx 直连 OpenAI 兼容的 `/chat/completions`。其他新依赖先提问。
- **D7 部署：** 本次只按单机演示（SQLite）实现。鉴权、限流、Postgres 不在本次范围内，但要留好接口（见第 5 节最后一部分）。
- **D8 时间线：** 没有固定截止日期。如果负责人另有说明，先完成并交付第 0–1 阶段。

## 3. 硬性约束

1. 技术栈不变：后端 FastAPI + Python ≥ 3.11；前端 Vue 3 + TypeScript + Vite + Pinia + Vue Router。
2. **每个阶段结束时**必须满足：
   - `ruff check` 和 `ruff format --check` 通过；
   - 后端全部测试通过；
   - 前端 `npm run build` 仍然通过（你不改前端代码，这一条用来确认没有误伤）；
   - README 里的 4 步演示流程能跑通：用脚本化的假模型写一个自动化的演示冒烟测试，再附上用真实模型手动验证的步骤（用 curl 调接口，或者用现有的前端页面）。
3. 第 0–1 阶段**不改对外契约**：`POST /api/v1/agent/chat` 的请求字段、`AgentWorkflowData` 现有字段的名字和类型都不变，只允许新增字段。新接口从第 3 阶段才引入。
4. 密钥只存在后端环境变量里，不得写进日志，也不得返回给浏览器。
5. 在新分支上工作，命名为 `backend/phase-N`；起点由负责人指定，并且必须包含 `docs/` 下的这几份文档。不要直接提交或推送到 `main`。每个阶段单独一个 PR；提交信息写清楚改了什么、为什么改、怎么验证的。不要改写已有的提交历史。
6. 代码和注释用英文；界面文案和文档用简体中文。
7. 测试不得写入真实的 `backend/data/` 目录，每个测试用自己的临时数据库。
8. 开发环境：这台机器是 Windows，默认的 `python` 是 3.10，不满足要求。请用 uv：在 `backend/` 下执行 `uv venv --python 3.12 --managed-python .venv`，再执行 `uv pip install -e ".[dev]"`。注意 `backend/data/` 在 `.gitignore` 里，种子数据文件不能放在那里。

### 前后端协作

前端由另一位开发者（Claude）在独立的 git worktree 和 `frontend/*` 分支上并行开发。

9. **文件归属：** 你只修改 `backend/**`、`.github/workflows/**` 和根目录的 `.gitignore`。不要修改 `src/**`、`public/**`、`index.html`、`package.json`、`package-lock.json`、`vite.config.ts`、`tsconfig*.json`、`scripts/dev-all.mjs`、根目录的 `README.md` 和 `docs/` 下的文件。确实需要改时，写进阶段汇报，由负责人协调。
10. **接口契约：** 第 3 阶段的接口以 `docs/api-contract.md` 为准（前端起草、负责人确认）。契约确认之前不要开始第 3 阶段；实现中发现契约有问题，先在汇报里提出，不要自行改动接口的形状。
11. **提前交付（第 1 阶段）：** `GET /api/v1/status`，返回 `{llm_configured, model, db_ok, version}`；以及 `python -m app.scripts.export_openapi`，不启动服务就能导出 `openapi.json`。前端会提前用上这两样。
12. **兼容层：** 现有接口（`/api/v1/agent/chat`、`/api/v1/dashboard/*`、`/api/v1/catalog/products`）的路径和响应形状保持不变、只增字段，一直保留到负责人通知"前端已迁移"，再单独删除或调整。
13. **虚拟环境位置：** 保持在 `backend/.venv`，因为 `scripts/dev-all.mjs` 按这个路径启动后端。
14. **别人的分支：** 不要切换、合并或删除 `frontend/*` 分支和前端的 worktree。
15. **CI：** `.github/workflows/ci.yml` 由你维护，里面保留前端构建任务（`npm ci` + `npm run build`）。前端构建失败时不要改前端代码，在汇报里说明。

## 4. 目标架构（必须遵守）

### 4.1 目录与依赖方向

```text
backend/app/
├── main.py              create_app() + lifespan：创建和关闭所有资源，挂到 app.state
├── core/                config（单一 Settings，env 文件路径锚定到 backend/）、db、errors（错误码）、logging（request_id）
├── domain/              纯数据类型与枚举，不做 I/O
├── repositories/        SQLAlchemy 2.0 模型 + 仓储；Alembic 迁移放在 backend/migrations/
├── services/            conversation_service（处理入站消息的唯一入口）、handoff_service、catalog_service、analytics_service
├── agent/
│   ├── runtime.py       AgentRunner：工具循环，产出事件流
│   ├── context.py       ContextBuilder：系统提示词 + 会话状态 + 摘要 + 按 token 预算裁剪的历史
│   ├── effects.py       有类型的副作用
│   ├── analysis.py      结构化事后分析（D3）
│   ├── guardrails.py    关键词护栏（按词边界匹配），只做兜底和强制转人工
│   ├── commands.py      斜杠指令 → 调用 services 里对应的方法
│   ├── llm/             LLMClient 协议 + OpenAI 兼容实现
│   ├── tools/           每个工具：Pydantic 参数模型 + run(args, deps) -> ToolOutput；deps.py 定义工具依赖的 Protocol
│   └── prompts/         带版本号的提示词模板
├── api/                 deps（数据库会话、服务、鉴权占位）、v1 路由、v1/schemas（所有 HTTP 结构只放这里）、v1/presenters.py
├── scripts/             seed.py、export_openapi.py
└── seed/                catalog.json、shipping_rules.json（D2：只放已知规则）
```

依赖规则：`api → services → agent 或 repositories → domain`，`core` 各层都可以用。

- `agent` 不得 import `api` 或 `repositories`：工具需要的数据通过 `agent/tools/deps.py` 里定义的 Protocol 注入，由 `services` 实现；
- `domain` 不得 import `app` 里的其他包；
- 所有 HTTP 请求/响应结构只放在 `api/v1/schemas/`。

把这些规则写成 `import-linter` 合约（或者一个扫描 import 语句的测试），放进 CI。

### 4.2 数据模型（第 2 阶段落地）

- `conversations`：`id`（UUID 字符串）、`merchant_id`、`channel`（目前只有 `web_demo`）、`customer_ref`（可空）、`status`（见 D4）、`reply_language`（可空，只允许 `zh-CN`、`en-US`、`es-ES`）、`state`（JSON：`focused_product_ids`、`destination_country`、`quantity`）、`summary`（可空）、`version`（乐观锁）、`created_at`、`updated_at`、`last_message_at`。
- `messages`：`id`、`conversation_id`、`seq`、`role`（`user`、`assistant`、`tool`、`human_agent`）、`content`、`tool_calls`（JSON，可空）、`tool_call_id`、`name`、`run_id`、`client_message_id`（可空，用于幂等）、`created_at`；`(conversation_id, seq)` 唯一。**只追加，不更新。** 斜杠指令不写入这张表。
- `agent_runs`：`id`、`conversation_id`、`trigger_message_id`、`model`、`status`（`ok`、`error`）、`error_code`、`rounds`、`tool_trace`（JSON：每次调用的 `name`、`args`、`ok`、`latency_ms`、`error`）、`prompt_tokens`、`completion_tokens`、`latency_ms`、`outcome`（JSON：`intents`、`language`、`product_ids`、`needs_human`、`handoff_reason`、`merchant_summary_zh`）、`analysis_source`（`llm`、`heuristic`）、`created_at`。
- `handoff_tickets`：`id`、`conversation_id`、`merchant_id`、`reason_code`（`after_sales`、`user_request`、`guardrail`）、`reason_text`、`issue_summary`、`status`（`open`、`acknowledged`、`resolved`）、`created_at`、`acknowledged_at`、`resolved_at`。同一会话同一时间最多一张未关闭的工单。
- `products`：`id`、`merchant_id`、`name`、`english_name`、`category`、`price_usd`、`stock`、`shipping_days`、`aliases`（JSON）、`specs`（JSON）。
- `shipping_rules`：`merchant_id`、`product_id`（可空，表示所有商品）、`destination_country`、`available`、`days_text`、`note`。
- 看板统计全部基于上面这些表做 SQL 聚合，并加上必要的索引。

### 4.3 Agent 运行时契约

```python
# agent/llm/base.py
@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int

@dataclass(frozen=True)
class ModelResponse:
    content: str | None
    tool_calls: tuple[ToolCall, ...]
    finish_reason: str | None
    usage: Usage | None

class LLMClient(Protocol):
    @property
    def is_configured(self) -> bool: ...

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[dict[str, Any]] = (),
        tool_choice: Literal["auto", "none"] = "auto",
        response_format: dict[str, Any] | None = None,
    ) -> ModelResponse: ...

    def stream(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[dict[str, Any]] = (),
        tool_choice: Literal["auto", "none"] = "auto",
    ) -> AsyncIterator[StreamChunk]: ...


# agent/effects.py
@dataclass(frozen=True)
class RequestHandoff:
    reason_code: Literal["after_sales", "user_request", "guardrail"]
    reason_text: str
    issue_summary: str | None = None

@dataclass(frozen=True)
class FocusProducts:
    product_ids: tuple[str, ...]

@dataclass(frozen=True)
class UpdateSlots:
    destination_country: str | None = None  # ISO 3166-1 alpha-2
    quantity: int | None = None

Effect = RequestHandoff | FocusProducts | UpdateSlots


# agent/tools/base.py
@dataclass(frozen=True)
class ToolOutput:
    content: str  # 给模型看的结果（JSON 字符串）
    ok: bool = True
    effects: tuple[Effect, ...] = ()

class Tool(Protocol):
    name: str                    # 只用字母、数字、下划线
    description: str
    args_model: type[BaseModel]  # 工具的 JSON Schema 由它生成
    timeout_seconds: float
    async def run(self, args: BaseModel, deps: ToolDeps) -> ToolOutput: ...


# agent/runtime.py
class AgentRunner:
    async def run(self, ctx: RunContext) -> AsyncIterator[AgentEvent]: ...  # 异步生成器

# AgentEvent = ToolStarted(name, args) | ToolFinished(name, ok, latency_ms, error)
#            | TextDelta(text) | RunCompleted(reply, effects, trace, usage)
#            | RunFailed(error_code, message)
```

工具循环必须满足：

1. 每轮把全部工具的 schema 发给模型；**最后一轮**用 `tool_choice="none"`，强制给出文本回复。
2. 未知工具名、参数不是合法 JSON、参数没通过 Pydantic 校验：都生成一条 `role="tool"` 的错误结果（写明原因）回传给模型，请求不中断；同时记入轨迹。
3. 同一轮里的多个工具调用用 `asyncio.gather` 并发执行；每个工具有超时（默认 10 秒），超时也作为工具错误回传。
4. 工具抛出异常时，用 `logger.exception` 记录，回传给模型的是不含内部细节的通用错误。
5. `finish_reason == "length"` 时记录警告，并在轨迹里标记 `truncated`。
6. 整次运行有总时限 `AGENT_RUN_TIMEOUT_SECONDS`（默认 60 秒，必须小于前端的 70 秒超时），超时返回错误码 `AGENT_RUN_TIMEOUT`。
7. 运行器本身不写数据库，只产出回复、effects 和轨迹，由 `ConversationService` 落库。
8. 流式模式下，按 `index` 累积 `delta.tool_calls` 的片段，等这一轮的流结束再执行工具。

### 4.4 处理一条入站消息：`ConversationService.handle_inbound`

1. 带了 `client_message_id`，并且这个会话里已经处理过同一个 ID：直接返回已保存的结果，不再调用模型（第 3 阶段）。
2. 取得会话锁：单进程用按会话 ID 的 `asyncio.Lock`；锁的接口要能换成数据库锁，为多实例预留。
3. 加载会话。`status == human_active` 时（D4）：只追加用户消息，返回固定提示，不调用模型。
4. 斜杠指令：调用对应的服务方法。`/reset` 关闭当前会话并新建一个；`/handoff` 创建工单（`reason_code="user_request"`）；`/lang` 校验取值后写入 `reply_language`；`/help`、`/product` 只返回信息。指令不写入消息表，不计入统计。
5. 用 `ContextBuilder`（4.5）构建消息，交给 `AgentRunner` 运行；流式模式下把事件转发给 HTTP 层。
6. 护栏兜底：关键词护栏判断为退款或投诉、而模型没有登记时，补一个 `RequestHandoff(reason_code="guardrail")`。
7. 在一个事务里：追加用户消息、工具消息、助手消息；应用 effects（创建工单、更新槽位和关注的商品）；写入一条 `agent_runs`。
8. 事后分析（D3）：产出 outcome，写回 `agent_runs.outcome`。流式模式下先推送回复，再推送分析结果事件，不让客户等分析。
9. 组装 `AgentWorkflowData`：`matched_product(s)`、`product_id` 来自 `FocusProducts` 和工具轨迹；`needs_human`、`handoff_reason` 来自工单；`steps` 来自真实轨迹（字段名和类型不变，内容变成真实记录）。

### 4.5 记忆：`ContextBuilder`

- **系统提示词：** 稳定的角色与规则，放在 `agent/prompts/`，带版本号。**删除**现在注入关键词分析结果的"本轮业务分析"段落（`agent/prompts.py:19-41`）。
- **会话状态块：** 关注的商品（从商品服务实时读取关键字段）、目的国、数量、`reply_language`、接管状态。
- **摘要：** `conversations.summary`（有就带上）。
- **最近消息：** 包含工具调用和结果，单条工具结果超过 `AGENT_TOOL_RESULT_MAX_CHARS` 时截断；按 `AGENT_CONTEXT_TOKEN_BUDGET` 从新到旧保留。token 用简单的字符估算即可，不引入新依赖。**带 `tool_calls` 的助手消息和对应的工具消息必须整组保留或整组丢弃**，否则 OpenAI 兼容接口会报错。
- **长对话摘要：** 做成可选功能（`AGENT_SUMMARY_ENABLED`，默认关闭）；打开后，在历史超出预算时，于回复之后异步生成。
- **语言：** `reply_language` 有值时，在系统提示词里明确要求用这种语言回复；否则要求按客户最新一条消息的语言回复。

### 4.6 API（第 3 阶段）

下面是接口清单；字段级的定义以 `docs/api-contract.md` 为准。

- `POST /api/v1/conversations` → `{id}`（服务端生成）
- `GET /api/v1/conversations/{id}` → 会话状态
- `GET /api/v1/conversations/{id}/messages` → 历史（用户消息、助手消息、接管标记）
- `POST /api/v1/conversations/{id}/messages` → `AgentWorkflowData` + `conversation_id` + `run_id`；请求可以带 `client_message_id`
- `POST /api/v1/conversations/{id}/messages/stream` → `text/event-stream`，事件：`tool_started`、`tool_finished`、`delta`、`completed`、`analysis`、`error`
- `POST /api/v1/conversations/{id}/reset`、`POST /api/v1/conversations/{id}/handoff`、`PATCH /api/v1/conversations/{id}`（修改 `reply_language`）
- `GET /api/v1/handoffs?status=open`、`POST /api/v1/handoffs/{id}/acknowledge`、`POST /api/v1/handoffs/{id}/resolve`
- `GET /api/v1/dashboard/overview`、`GET /api/v1/dashboard/recent`：带类型的响应模型
- `GET /api/v1/status` → `{llm_configured, model, db_ok, version}`
- 统一错误信封：`{"status": "error", "error": {"code": "...", "message": "..."}}`。错误码至少包括 `LLM_NOT_CONFIGURED`、`LLM_TIMEOUT`、`LLM_UPSTREAM_ERROR`、`LLM_BAD_RESPONSE`、`AGENT_RUN_TIMEOUT`、`CONVERSATION_NOT_FOUND`、`VALIDATION_ERROR`，以及预留的 `RATE_LIMITED`。前端会按这个信封解析（由前端负责修改）。
- SSE 用 Starlette 的 `StreamingResponse(media_type="text/event-stream")`。Agent 运行放在独立的任务里，响应只是订阅事件队列：客户端中途断开时，运行仍要完成并落库。
- 鉴权占位：商家接口（看板、工单）加一个 `require_merchant` 依赖，检查请求头 `X-Merchant-Key`。配置了 `MERCHANT_API_KEY` 才强制校验；没配置时放行，并在启动日志里给出警告。
- 旧接口 `POST /api/v1/agent/chat` 和 `/api/v1/dashboard/handoffs*` 在迁移期间保留为兼容层（`/agent/chat` 缺少 `session_id` 时自动建会话，并在响应里返回 `session_id`）；收到负责人通知后再删除（见第 3 节第 12 条），并更新 `backend/README.md`。

### 4.7 前端（不在你的范围内）

前端由 Claude 按 [`frontend-plan.md`](frontend-plan.md) 开发（见第 3 节"前后端协作"）。你只需要保证接口符合契约，并按时交付第 3 节第 11 条的两样东西。

## 5. 分阶段计划与验收标准

### 第 0 阶段：安全网（不改行为）

1. 用 uv 管理后端依赖并提交锁文件（`uv lock`）；更新 `backend/README.md`：写明 Python ≥ 3.11，以及用 uv 安装、运行、测试的命令。
2. 在 `pyproject.toml` 里加入开发依赖；运行 `ruff check --fix`，手动处理剩下的问题（基线是 26 处）；`ruff format` 的格式化改动单独一个提交。
3. 新增 `.github/workflows/ci.yml`：后端跑 ruff 和测试；前端跑 `npm ci` 和 `npm run build`。
4. 让数据库路径可配置（最小改动即可），保证测试只用临时数据库。
5. 新增接口级测试（`fastapi.testclient.TestClient` 或 `httpx.ASGITransport`），用脚本化的假模型覆盖 `/agent/chat`、看板接口和接管确认；把 `AgentWorkflowData` 的字段集合写成契约测试；写一个演示冒烟测试，按 README 的 4 步走一遍。
6. 把第 6 节的缺陷全部写成测试，并标记为预期失败（`unittest.expectedFailure` 或 `pytest.mark.xfail(strict=True)`），测试名里带缺陷编号。

**验收：** ruff 0 问题；测试全绿（缺陷测试为预期失败）；构建通过。

### 第 1 阶段：边界与工具调用（对外契约不变）

1. 拆分 `services/workflow.py`：
   - 商品数据 → `app/seed/catalog.json` + `CatalogService`（本阶段可以先用内存实现，第 2 阶段换成数据库）；
   - 关键词规则 → `agent/guardrails.py`：只保留一张规则表（现在同一组关键词在 `_detect_intent` 和 `_detect_all_intents` 里重复了两遍）；英文按词边界匹配，并为每个关键词列出允许的词形；中文用词表精确匹配；"用英文回复""in English"这类指令按短语匹配，而不是只要出现"英语"就判为英文；
   - 统计 → `AnalyticsService`：SQL 实时聚合，删除进程内计数器；`failed_requests` 也落库；
   - 卡片组装 → `api/v1/presenters.py`。
2. 所有资源在 lifespan 里创建，挂在 `app.state` 上，通过依赖注入使用；删除模块级的 `metrics` 单例和用 `lru_cache` 做的引擎单例。导入任何模块都不能产生 I/O。
3. Agent 核心不再 import `app.schemas`：新增领域类型 `InboundMessage`。
4. 工具改为 Pydantic 参数模型加 `ToolOutput(effects)`，删除 `data` 里的魔法键；`knowledge_search` 在没有配置数据源时不注册，不暴露给模型。
5. 按 4.3 实现循环规则。
6. 模型客户端：共享 `httpx.AsyncClient`（由 lifespan 管理）；对 429、5xx 和连接错误做指数退避重试（最多 2 次，遵守 `Retry-After`）；温度和 `max_tokens` 可配置；记录 token 用量；上游错误详情只写日志，返回给浏览器的是通用信息和错误码。
7. 修复第 6 节的缺陷 1–11，其中：
   - 缺陷 5、9：本阶段先在现有归档表上加 `handoff_reason`、`issue_summary` 两列；
   - 缺陷 3：把显式语言偏好和检测出的语言分开存；
   - 缺陷 6：缺少 `session_id` 时由服务端生成，并在响应里新增 `session_id` 字段；
   - 缺陷 7：先用按会话的 `asyncio.Lock` 解决，第 2 阶段再根治；
   - 缺陷 11：按 D2 实现，本阶段的规则可以先放在种子 JSON 里。
8. 卡片里的 `matched_product(s)`、`product_id`、`needs_human`、`handoff_reason`、`steps` 改为来自真实轨迹和 effects；轨迹里没有相关信息时，才用关键词结果兜底。
9. 删除 `.gitignore` 里 AstrBot 的残留条目。
10. 提前交付 `GET /api/v1/status` 和 `python -m app.scripts.export_openapi`（见第 3 节第 11 条）。

**验收：** 缺陷 1–11 的测试去掉预期失败标记，并全部通过；新增循环健壮性测试（未知工具、坏参数、工具超时、轮次耗尽后强制作答、总时限）；演示冒烟测试通过；`AgentWorkflowData` 现有字段不变；`/status` 和 OpenAPI 导出可用。

### 第 2 阶段：统一的状态与记忆

1. 引入 SQLAlchemy 2.0（async）+ Alembic + aiosqlite；SQLite 开启 WAL；新增配置 `DATABASE_URL`，默认指向 `backend/data/app.db`（路径锚定到 `backend/` 目录，而不是当前工作目录）。
2. 按 4.2 建表，写第一版 Alembic 迁移；按 D5 处理旧数据；实现种子脚本。
3. 按 4.4 实现 `ConversationService.handle_inbound`：消息只追加；会话锁；用 `version` 做乐观锁，为多实例预留。
4. 实现 D4 的接管状态机和工单生命周期，以及商家确认、解决的服务方法。
5. 按 4.5 实现 `ContextBuilder`。
6. 实现 D3 的事后分析：优先用 `response_format`（JSON Schema）；网关不支持时，退回"只输出 JSON"的提示词，再解析和校验；失败时兜底。中文商家摘要必须包含外文咨询的中文译文。
7. 看板统计改为基于新表的 SQL 聚合；删除旧的 `agent_sessions`、`workflow_conversations` 代码路径。
8. 新增离线评测 `backend/evals/`：20–50 条典型咨询（多语言、追问、售后、诱导编造价格或承诺），写明期望的工具调用和关键事实；提供一个用真实模型运行、输出通过率的脚本（不进 CI）。
9. 在 `backend/README.md` 里说明 D4 的接管流程：确认接管后机器人暂停，标记解决后恢复（根目录 README 的演示步骤由前端负责更新）。

**验收：** 并发测试通过（同一会话并发 2 条消息，4 条消息全部保存，顺序正确）；接管状态机测试通过；上下文裁剪测试通过（不拆散工具消息组）；西语咨询的中文摘要测试通过（用脚本化的分析结果）；缺陷 7、12 的测试通过；演示冒烟测试通过。

### 第 3 阶段：API

按 4.6 和 `docs/api-contract.md` 实现后端接口，包括 SSE 和幂等。

**验收：** 接口级测试覆盖契约里的每个接口和每种 SSE 事件；用 curl 能演示流式输出；历史接口返回完整的会话；重复提交同一个 `client_message_id` 不会被处理两次；导出的 `openapi.json` 与契约一致；兼容层仍然保留（等负责人通知再删）。

### 本次不做，但不能挡路

- 鉴权（商家 API Key / JWT）、限流与配额、Postgres、观测（request_id、token 成本）、输出检查、数据保留策略、Docker、后台任务队列；
- 政策/FAQ 知识库检索、物流与阶梯价规则、渠道接入（网站挂件、WhatsApp 等）、商家在控制台直接回复、接管通知。

## 6. 已知缺陷（每条都要有回归测试）

下面的输入都已经在当前代码上复现过。测试统一用脚本化的假模型，不需要真实密钥。

1. **子串误判**（`analyze_message`，重构后是 `agent/guardrails.py`）：
   - "Can I cancel my order?"、"Do you ship to France?" → 不应命中 `headset-pro`；
   - "I'm a returning customer, what's the price?" → 意图不应是售后，也不应转人工；
   - "Is it lightweight enough for a flight?" → 不应命中 `lamp-mini`；
   - "Is this especially good for kids?" → 不应判为参数咨询；
   - "你们客服会说英语吗？" → 语言应为 `zh-CN`；
   - 同时保留真阳性："I want a refund"、"我要退货" → 售后；"Nebula ANC Headphones Pro"、"降噪耳机" → `headset-pro`；"请用英文回复：……" → `en-US`。
2. **`/reset` 不清商品：** 依次发送 "Please quote the headphones"、`/reset`、`/product`、"How long is the delivery?" → 期望重置后没有商品上下文，不再回退去读归档。
3. **`/lang` 只管一条：** `/lang es-ES` 之后发一条英文消息 → 显式偏好仍是 `es-ES`，模型收到的提示要求用西班牙语回复；`/lang foo` → 被拒绝，并列出可选值。
4. **指令污染统计和历史：** 3 条真实消息加上 `/help`、`/product`、`/lang es-ES` → 看板累计为 3；发给模型的历史里没有任何指令及其回复。
5. **接管原因写死：** `/handoff` → 商家队列显示的原因是"用户主动请求人工接管"。
6. **匿名请求共用会话：** 两个不带 `session_id` 的请求 → 各自是独立会话；第二个请求发给模型的上下文里没有第一个请求的消息；响应里带服务端生成的 `session_id`。
7. **并发丢消息：** 同一 `session_id` 用 `asyncio.gather` 并发发送两条消息（假模型返回前先 `await asyncio.sleep(0.05)`）→ 保存了 4 条记录（两问两答），顺序与处理顺序一致。
8. **多实例数字不一致：** 两个统计服务实例共用同一个数据库，A 写入一条接管记录 → B 读到的累计、人工接管、待处理都是 1。
9. **问题摘要丢失：** 假模型调用 `after_sales_record`，参数 `issue="ISSUE-MARKER screen cracked on arrival"` → 这段文字存进了工单（第 1 阶段是归档记录），并显示在商家队列里。
10. **卡片与实际行为不一致：** 消息 "How much is the Nebula?"，假模型依次调用 `catalog_search(query="nebula")`、`catalog_quote(product_id="headset-pro")`，然后回复报价 → 卡片的 `matched_product` 是"星云降噪耳机 Pro"，`steps` 里能看到这两次工具调用，会话记住了 `headset-pro`。
11. **物流编造事实：** `catalog_shipping` 的目的地分别为 `ES`、`AQ`（南极洲）和 "Mars" → `ES` 返回可送达和时效；`AQ` 返回 `unconfirmed`；"Mars" 参数校验失败，作为工具错误回传，由模型请客户确认目的地。
12. **商家摘要不翻译**（第 2 阶段）：西语咨询 "Hola, ¿cuánto tarda el envío de los auriculares a México?" → 中文商家摘要是中文，并包含译文；意图为物流。自动化测试用脚本化的分析结果验证流程，再用真实模型手动验证效果。

## 7. 阶段汇报格式

每个阶段结束时输出：

1. 按模块列出的改动摘要，以及提交列表；
2. 测试与构建结果（贴出命令和关键输出）；
3. 与本说明不一致的地方，以及原因；
4. 新增的 `TODO(owner)`，以及需要负责人决定的问题；
5. 演示验证记录：自动化结果和手动验证步骤。

遇到本说明没有覆盖、又会影响业务行为的选择时，先停下来提问，不要猜。

## 8. 不要做的事

- 不要一次性推倒重写，也不要跳过任何阶段的验收；
- 不要修改前端文件（见第 3 节"前后端协作"）；
- 不要引入模型 SDK、Agent 框架或向量数据库（知识库到第 5 阶段再议）；
- 不要改写 git 历史；不要提交 `.env`、数据库文件或任何密钥；
- 不要为了让测试通过而删除或放宽测试；
- 不要改产品名称和界面文案的风格（修复写死的错误状态除外）。
