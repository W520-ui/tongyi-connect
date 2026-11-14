# 通译智联架构评审

- 评审日期：2026-11-14
- 评审对象：提交 `4b5c78d` 上的全部后端（`backend/app/`）和前端（`src/`）代码
- 代码位置写法：后端路径相对于 `backend/app/`，前端路径相对于 `src/`，例如 `agent/engine.py:65`
- 标注"已复现"的结论，都在临时副本上用脚本实际跑过；评审过程没有改动任何项目代码

## 0. 结论速览

基线是健康的：后端 22 个测试全部通过，前端 `vue-tsc -b && vite build` 通过，演示闭环能跑通。但这套代码是围绕演示脚本拼出来的，有 5 个结构性问题。不先解决它们，后面每加一个功能都会更难：

1. **两套"大脑"各说各话。** 关键词规则（`analyze_message`）和大模型各自判断商品、意图和语言。真正回复客户的是大模型，可界面卡片、商家摘要、会话记忆和看板统计用的全是关键词那一套，两边经常对不上。
2. **会话状态散落在 5 个地方，没有唯一的事实来源。** 已复现的大部分 bug，都是这几处状态互相打架造成的。
3. **工具调用没有真实的副作用，也没有明确的契约。** 工具靠 `data` 里的"魔法键"给引擎传信号；售后登记工具其实什么也没登记；物流工具对任何目的地都说能送；模型调用一个不存在的工具，整个请求就失败。
4. **单进程假设写死在代码里。** 一导入模块就打开数据库，计数器缓存在进程内存里，每次写归档都要全表重扫，而且这些都在事件循环线程上同步执行。多开一个 worker，数据就不一致。
5. **分层只有目录名，没有真正的边界。** Agent 核心依赖 HTTP 层的请求模型；`services/workflow.py` 一个文件管着 5 种职责；预留的 `models/`、`repositories/` 目录是空的。

**建议走渐进式重构，不要推倒重写。** 第 1 阶段在不改对外接口的前提下理顺边界、修好工具循环；第 2 阶段用一套"会话 + 消息 + 运行轨迹"的数据模型替换现在的存储；第 3 阶段再改 API 和前端体验。每个阶段结束时，演示都必须还能跑通。路线图见第 5 节；可以直接交给执行模型的提示词见 [`refactor-prompt.md`](refactor-prompt.md)。

## 1. 现状架构

### 1.1 一条消息的处理路径

```text
浏览器 AgentChatPanel
  │  POST /api/v1/agent/chat {message, session_id}
  ▼
api/v1/endpoints/agent.py → services/agent.py（只做转发）→ agent/engine.py: AgentEngine.chat()
  │
  ├─ 1. SessionStore.load(session_id)     读 agent_sessions（turns 是一整段 JSON）
  ├─ 2. 商品提示 = session.last_product_id，
  │     没有就回退去读 workflow_conversations 归档（metrics.last_product_id）
  ├─ 3. analyze_message()                  关键词猜语言、意图、商品
  ├─ 4. 是斜杠指令？→ 直接跳到第 6 步
  ├─ 5. 模型循环（最多 4 轮）               decide() → 串行执行工具 → 回填工具结果
  └─ 6. _finalize()
        ├─ 用第 3 步的关键词结果拼界面卡片（build_workflow_answer）
        ├─ 覆盖 last_product_id 和 language，整段重写 turns JSON
        └─ metrics.archive()：写一条归档，再全表重扫，刷新内存计数器
  ▼
返回 {status, data: AgentWorkflowData}
```

### 1.2 实际的模块依赖

```text
api ─────────► services/agent ──► agent/engine ──► schemas/agent      （核心依赖 HTTP 请求模型）
 │                                     │
 │ 直接 import 全局 metrics             │ analyze_message / build_workflow_answer / metrics
 ▼                                     ▼
services/workflow ◄──────────────── agent/tools/catalog              （直接读全局常量 PRODUCTS）
```

`services/workflow.py`（518 行）一个文件承担了 5 种职责：商品数据（`PRODUCTS` 常量）、语言/意图/商品识别、商家摘要、界面视图模型（`steps`、`task_plan`）、SQLite 建表/迁移/统计。

## 2. 主要问题

严重度：**高** = 影响正确性，或者会挡住后续扩展；**中** = 明显的技术债；**低** = 顺手就能改。

### 2.1 模块边界

- **B1【高】两套大脑。** 界面卡片、商家摘要、会话商品和看板统计都来自关键词规则，而不是 Agent 实际做了什么（`agent/engine.py:183-210`）。
  - 已复现：模型通过 `catalog_search` 和 `catalog_quote` 查到耳机并报了价，卡片却显示"未匹配具体商品"，步骤写着"等待商家补充商品信息"，会话也没有记住这个商品。
- **B2【高】`services/workflow.py` 是"上帝模块"。** 见 1.2。改动其中任何一种职责，都会波及另外四种。
- **B3【高】依赖方向是反的。**
  - Agent 核心 import 了 HTTP 请求模型 `AgentChatRequest`（`agent/engine.py:19`）；
  - 工具直接 import 业务模块里的全局常量 `PRODUCTS`（`agent/tools/catalog.py:8`）；
  - 接口层直接 import 全局单例 `metrics`，既不能替换，也不能注入。
- **B4【中】`AgentEngine` 管得太多。** 它同时负责编排、持久化、归档和拼界面数据（`_finalize`，`agent/engine.py:173-219`），而 `services/agent.py` 只是一层空转发。
- **B5【中】契约没有类型。** `AgentContext.analysis` 是 `Any`（`agent/models.py:94`），`AgentChatResponse.data` 也是 `Any`（`schemas/agent.py:28`）；看板接口返回裸 `dict`；前端类型全靠手写，`Product` 还定义了两遍。
- **B6【中】"处理步骤"和"置信度"都是装出来的。** `steps`、`task_plan` 由关键词结果拼成固定文案（`services/workflow.py:405-413`、`483-498`），不是真实的执行轨迹；界面上的"置信度 93%"是按规则写死的常数（0.93、0.96、0.72 等）；前端的"LIVE"流程图也是静态的（`views/WorkspaceView.vue:195-201`）。
- **B7【中】前端没有角色边界。** 商家控制台和"客户聊天"挤在同一个页面里（`WorkspaceView.vue` 548 行），没有为将来接入真实渠道（网站挂件、WhatsApp 等）留出边界。
- **B8【低】空壳和死代码。** `models/`、`repositories/` 是空的；`ToolSpec.scopes` 从没用过；`on_reply`、`on_handoff` 事件没有任何订阅者；现有 hooks 是同步回调，将来也做不了异步通知。

### 2.2 工具调用

- **T1【高】工具没有真实的副作用，只有"魔法键"。** 工具通过 `ToolResult.data` 里的 `needs_human`、`handoff_reason` 给引擎发信号（`agent/engine.py:141-143`）。
  - 已复现：`after_sales_record` 返回 `"registered": true`，但模型写的问题摘要 `issue` 在两个数据库里都查不到（0 行），商家队列显示的是写死的原因。
- **T2【高】工具会编造事实。**
  - `catalog_shipping` 完全忽略目的地，对任何地方都返回 `international_shipping: true` 和同一个时效。已复现：南极、火星都是"5–8 个工作日"，模型会把它当成事实告诉客户。
  - `catalog_quote` 只有一个美元单价，没有数量或批发价，可系统提示词又让模型"主动询问采购数量"。
  - `knowledge_search` 是永远返回"未配置"的空壳，却照样暴露给模型，白白浪费调用轮次。
- **T3【高】工具循环不健壮。**
  - 模型调用了不存在的工具 → 抛出 `AgentError` → 整个请求返回 503（`agent/registry.py:56`），而不是把错误回传给模型，让它自己改正；
  - 参数 JSON 解析失败时静默变成 `{}`（`agent/providers/openai.py:91-94`），参数也从不按 JSON Schema 校验；
  - 4 轮用完直接报错，前面查到的结果全部丢弃（`agent/engine.py:153-154`），没有"最后一轮禁止调工具、强制作答"；
  - 不检查 `finish_reason`，回复被截断（`length`）也当作正常结果；
  - 工具内部的异常被吞掉，只把异常文字交给模型，没有写日志（`agent/registry.py:61-62`）；
  - 没有单个工具的超时；同一轮里的多个工具调用串行执行；
  - 没有端到端的总时限：单次模型调用最长 60 秒、最多 4 轮，最坏要 4 分钟左右；前端 70 秒就放弃了，后端却仍会跑完，把这一轮写进历史和归档。用户看到报错后重发，同一个问题就会被处理两次。
- **T4【中】模型接口抽象太窄。** `LLMProvider` 只有一个 `decide()`，结果是"回复"和"工具调用"二选一，表达不了流式输出、token 用量、`finish_reason` 和结构化输出。每次调用都新建一个 `httpx.AsyncClient`（`agent/providers/openai.py:48`），没有连接复用；遇到 429/5xx 不重试；`temperature` 写死为 0.3。
- **T5【中】提示词自相矛盾。** 规则 2 要求"价格、库存、时效必须调工具查询"，可 `build_context_message` 又把关键词命中商品的价格、库存、时效直接写进系统提示词（`agent/prompts.py:28-33`）。关键词一旦误判（比如 "France" 命中耳机），错误信息就以"服务端分析"的权威口吻误导模型。

### 2.3 记忆与状态管理

- **S1【高】没有唯一的事实来源。** 一个会话的状态分散在 5 个地方：
  1. `agent_sessions` 表：`turns` 整段 JSON、`last_product_id`、`language`；
  2. `workflow_conversations` 归档表：截断过的消息，还被当作商品上下文的回退来源（`agent/engine.py:67-69`）；
  3. `WorkflowMetrics` 的进程内计数器；
  4. 请求级的 `AgentContext.language_override`；
  5. 前端组件里的 `sessionId` 和消息列表（一刷新就丢）。

  之前复现的"`/reset` 清不掉商品""`/lang` 只管一条消息""指令混进历史和统计"，都是这几处互相打架的结果。
- **S2【高】读-改-写没有并发控制。** 两个请求同时进入同一个会话时，各自加载、各自整段覆盖，后写的会把先写的覆盖掉（`agent/session.py:60-91`）。
  - 已复现：同一会话并发发送 2 条消息，最后只保存了 2 条记录（应该是 4 条），归档表里却记了 2 次——两个存储对不上。
- **S3【高】会话 ID 不可信（上线前必须解决）。** 没有 `session_id` 的请求全部落进同一个"未命名会话"（`agent/engine.py:65`）；服务端接受客户端传来的任意会话 ID，而 `/dashboard/recent` 又公开返回所有 `session_id`，任何人都能接着别人的会话聊下去。
- **S4【中】记忆只有"最近 N 条原文 + 一个商品 ID + 一个语言"。**
  - 工具调用和结果不入库，追问时模型看不到上一轮查到的事实，只能重新查；
  - 历史窗口按条数截取，而不是按 token 预算（`max_history_turns=10` 实际是 10 条消息，也就是 5 轮对话）；
  - 没有结构化的会话槽位（目的国、数量、关注的商品），也没有长对话摘要；
  - 提示词里的"会话语言偏好"其实是上一条消息检测出的语言（`agent/engine.py:194`）。客户换了语言时，提示词里会同时出现两条互相矛盾的语言信息。
- **S5【中】人工接管不是会话状态，只是归档记录上的一个布尔值。** 没有"待接管 → 人工处理中 → 已解决"的生命周期；商家点了"确认接管"，机器人仍会继续自动回复；接管原因和问题摘要都没存下来。
- **S6【低】过期只在读取时检查。** 会话的 TTL 只在加载时判断；归档表里的商品不受 TTL 约束，这正是 `/reset` 问题的根源之一。

### 2.4 可扩展性

- **P1【高】单进程假设。** 导入 `services/workflow.py` 时就创建全局 `metrics` 并打开数据库（`services/workflow.py:349`）；`get_agent_engine()` 用 `lru_cache` 当全局单例；统计计数器缓存在进程内存里。
  - 已复现：两个 worker 共用一个库，A 写入一条接管记录后，B 的看板显示"累计 0、人工接管 0、待处理 1"，同一个页面上的数字自相矛盾。
  - `failed_requests` 只存在内存里，重启就清零，多 worker 时各算各的。
- **P2【高】写放大，而且阻塞事件循环。** 每次归档之后，`_load_existing_metrics()` 都会全表扫描并逐行解析 JSON（`services/workflow.py:229`）。
  - 实测单次 `archive()` 的耗时：1 千条 6 ms，1 万条 24 ms，5 万条 110 ms，随数据量线性增长。它在事件循环线程上同步执行，这段时间里所有请求都被卡住。
  - 会话历史每追加一条，也要把整段 JSON 重写一遍。
- **P3【中】存储层很原始。** 同步 SQLite 直接跑在 `async` 接口里；两个模块各开一个连接指向同一个文件；没开 WAL；迁移靠手写的 `_ensure_column`；数据库路径写死在源码目录下的 `data/`，无法配置。
- **P4【中】没有限流、配额和观测。** `/agent/chat` 一次请求最多触发 4 次模型调用，却没有按 IP、会话或商家限流，成本和稳定性都不可控；也没有请求 ID、耗时、token 用量这类数据，出了问题很难查。
- **P5【中】没有"商家"（租户）概念。** 商品、会话、看板全是全局的。如果产品要服务许多中小商家，这是越晚补越贵的一笔债。
- **P6【低】`.env` 按当前工作目录查找**（`core/config.py:17`、`agent/config.py:19`）。不在 `backend/` 目录下启动时，会静默读不到模型密钥。

### 2.5 其他：API、安全、前端、工程化

- **API：** 没有流式接口（`flags.enable_streaming` 收到了但没用上）；没有会话历史接口；错误只有一段文字，没有错误码；`/health` 不报告模型是否已配置；没有幂等机制，重发的消息会被再处理一次。
- **安全：** 商家接口没有任何鉴权；会话可以被别人接着聊（见 S3）；上游模型服务的错误详情会原样透传给浏览器。客户消息里会有个人信息，如果服务欧盟客户（比如演示里的西班牙），上线前还要考虑数据保留和删除（GDPR）。
- **前端：** 刷新页面就丢会话；回复不是流式的；设置页的"Agent 执行 · 可用"和顶栏的"系统框架已就绪"是写死的；回车发送不判断输入法是否还在选字；看板只在本页发完消息后才刷新，看不到其他客户新产生的接管；Markdown 原样显示；缺少 `favicon.svg`。
- **工程化：** ruff 有 26 处问题，而且没有强制执行；没有 CI；没有接口级测试、并发测试和模型效果评测；Python 依赖没有锁文件；这台机器默认的 Python 是 3.10，而项目要求 3.11+，README 的安装步骤在这里跑不通。

## 3. 目标架构

### 3.1 分层与依赖规则

```text
backend/app/
├── api/           只管 HTTP：路由、请求/响应结构、鉴权、SSE 适配、界面视图模型的组装
├── services/      用例编排：ConversationService、HandoffService、CatalogService、AnalyticsService
├── agent/         Agent 运行时：runtime（工具循环）、context（上下文构建）、tools、llm、prompts、guardrails
├── repositories/  持久化：SQLAlchemy 模型与仓储
├── domain/        纯领域类型：Conversation、Message、Product、HandoffTicket、各种枚举（不做 I/O）
└── core/          配置、数据库会话工厂、日志、错误码
```

依赖只允许自上而下：`api → services → agent / repositories → domain`，`core` 各层都能用。

- `domain` 不依赖任何其他包；
- `agent` 不知道 HTTP 的存在，也不直接访问数据库：工具通过注入的接口拿数据，接口由 `services` 实现；
- 所有 HTTP 的请求/响应结构只出现在 `api` 里。

这条规则要写进 CI（用 `import-linter`，或者写一个扫描 import 语句的测试），否则很快又会被打破。

### 3.2 统一的数据模型

用下面这几张表取代现在的 `agent_sessions` + `workflow_conversations` + 进程内计数器：

| 表 | 主要字段 | 说明 |
|---|---|---|
| `conversations` | `id`、`merchant_id`、`channel`、`status`、`reply_language`、`state`（JSON 槽位）、`summary`、`version`、时间戳 | 一个会话一行。`status` 取值：`bot_active` / `pending_human` / `human_active` / `resolved`；`version` 用于乐观锁 |
| `messages` | `id`、`conversation_id`、`seq`、`role`、`content`、`tool_calls`、`tool_call_id`、`run_id`、`created_at` | **只追加**，包括工具调用和结果；`(conversation_id, seq)` 唯一 |
| `agent_runs` | `id`、`conversation_id`、`model`、`rounds`、工具轨迹、token 用量、耗时、`error_code`、`outcome`（JSON） | 每次运行的真实轨迹。界面卡片和看板都从这里取数 |
| `handoff_tickets` | `id`、`conversation_id`、`reason_code`、`reason_text`、`issue_summary`、`status`、时间戳 | 接管工单：`open → acknowledged → resolved` |
| `products`、`shipping_rules` | 都带 `merchant_id` | 商品和物流规则从种子文件导入，不再写死在代码里 |

看板统计一律用 SQL 实时聚合（配合索引），不再维护进程内计数器。开发环境用 SQLite（开 WAL），生产环境换 Postgres，数据库迁移交给 Alembic。

### 3.3 Agent 运行时

- **事件流：** `AgentRunner.run()` 是一个异步生成器，依次产出 `ToolStarted`、`ToolFinished`、`TextDelta`，最后是 `RunCompleted` 或 `RunFailed`。HTTP 层既可以把它转成 SSE 推给前端，也可以收集成一次性 JSON：流式和非流式共用一套逻辑。
- **工具契约：** 每个工具用一个 Pydantic 模型定义参数，JSON Schema 自动生成；工具返回 `ToolOutput(content, effects)`。
  - `effects` 是有类型的副作用声明，例如 `RequestHandoff(reason, issue)`、`FocusProducts(ids)`、`UpdateSlots(destination, quantity)`；
  - 运行结束后，由 `ConversationService` 在一个事务里统一落库。工具本身不写数据库，所以容易测试，也不会重复登记。
- **循环规则：** 未知工具、参数解析失败、参数校验失败，都作为工具错误消息回传给模型；每个工具有超时；同一轮里的多个工具调用并发执行；最后一轮用 `tool_choice="none"` 强制作答；检查 `finish_reason`；整次运行有总时限，并且比前端的超时短；每次运行都写入 `agent_runs`。
- **结构化结果：** 意图、语言、涉及的商品、是否需要人工、**中文商家摘要（含外文咨询的译文）**，由一次结构化的"事后分析"调用产出：可以用更便宜的模型，也可以关掉（见决策 D3）。关键词规则只保留做兜底和安全护栏（比如退款、投诉一律转人工），并改为按词边界匹配。上线前还可以加输出检查，比如回复里出现的价格必须和工具结果一致。
- **模型客户端：** 共享一个 `httpx.AsyncClient`，在 lifespan 里创建和关闭；对 429/5xx 和连接错误做指数退避重试；温度、`max_tokens` 可配置；记录 token 用量。

### 3.4 记忆设计

- **短期记忆：** 最近的消息（包括工具调用和结果，过长的截断）按 token 预算裁剪，而不是按条数。裁剪时，带 `tool_calls` 的助手消息和它对应的工具消息必须整组保留或整组丢弃。
- **会话状态（槽位）：** 关注的商品、目的国、数量、回复语言偏好、接管状态。由工具副作用和事后分析更新，以结构化的形式写进系统提示词，取代现在的"本轮业务分析"段落。
- **长对话摘要：** 历史超出预算时，把较早的消息压缩成摘要，存进 `conversations.summary`（异步执行，不拖慢回复）。
- **语言只有一个事实来源：** 经过校验的显式偏好优先，否则由模型根据客户最新的消息判断。
- **客户长期记忆**（姓名、国家、历史订单）：等接入真实渠道、有了客户身份以后再做。

### 3.5 并发与扩展

- **同一会话串行处理：** 单进程用按会话 ID 加的 `asyncio.Lock`；多实例时换成 Postgres advisory lock，或者基于 `version` 的乐观锁。消息只追加、不覆盖，从根上避免"整段覆盖丢数据"。
- **资源生命周期：** 数据库引擎、HTTP 客户端、Agent 运行器都在 lifespan 中创建，挂在 `app.state` 上，通过 FastAPI 依赖注入使用。导入模块不再产生任何 I/O。
- **异步数据库访问：** SQLAlchemy async + aiosqlite（开发）/ asyncpg（生产）。
- **限流与幂等：** `/agent/chat` 按 IP 和会话限流，以后再按商家加配额；客户端为每条消息带一个 ID，重发时直接返回已有结果。
- **事件与通知：** 服务层发布领域事件（如"创建了接管工单"），由后台任务消费，用来通知商家，取代现在的同步 hooks。

### 3.6 API 与前端

- **以会话为中心的接口：**
  - `POST /conversations`：创建会话，ID 由服务端生成；
  - `POST /conversations/{id}/messages`：发消息，返回 JSON；
  - `POST /conversations/{id}/messages/stream`：发消息，用 SSE 流式返回；
  - `GET /conversations/{id}/messages`：读取历史。

  `/reset`、`/handoff`、`/lang` 改成显式接口；斜杠指令只作为开发时的快捷方式，映射到同一组服务方法，并且不再计入统计。
- **契约：** 所有接口都有 Pydantic 响应模型和统一的错误码；前端类型由 OpenAPI 自动生成。
- **前端：** 把 `WorkspaceView` 拆成组件；用 Pinia 管理会话（ID 存在 `sessionStorage`）和看板（定时刷新）；流式渲染回复；"流程监控"由真实运行轨迹驱动；各处状态显示取自新的 `/status` 接口。

## 4. 需要你拍板的业务决策

括号里是我的建议默认值。`refactor-prompt.md` 第 2 节已经按这些默认值写好，交给执行模型之前请逐条确认或修改。

- **D1 多商家：** 现在就在所有业务表上加 `merchant_id` 吗？（建议：加，只建一个默认商家，不做管理界面。现在加成本很低，以后补很贵。）
- **D2 物流与报价规则：** 真实的可送达范围和价格规则由谁提供？（建议：拿到真实数据之前，演示种子数据只把西班牙标为可送达，沿用现在的演示行为；其他目的地一律返回"需商家确认"；报价保持单一美元价。）
- **D3 事后分析：** 是否接受每条消息多一次（小模型）调用，用来生成意图、语言和中文商家摘要？（建议：接受，并提供开关；关闭或失败时退回关键词规则。）
- **D4 人工接管语义：** 接管后机器人还要不要自动回复？（建议：待接管期间机器人继续回答，但不重复登记；商家确认接管后，机器人停止自动回复，只保存客户消息；商家标记解决后，机器人恢复。）
- **D5 旧数据：** `backend/data/workflow.db` 里的演示数据是迁移还是丢弃？（建议：丢弃，并提供一键重建种子数据的脚本。）
- **D6 新依赖：** 是否允许引入 SQLAlchemy 2、Alembic、aiosqlite、pytest、import-linter（后端）和 openapi-typescript、markdown-it（前端）？（建议：允许；同时保持"不装模型 SDK、不引入 Agent 框架"的原则不变。）
- **D7 部署目标：** 近期只需要单机演示，还是要上云、多实例？（这决定第 4 阶段要不要提前。建议：先按单机演示做，但在结构上给鉴权、限流和 Postgres 留好位置。）
- **D8 时间线：** 有没有固定的演示日期或截止时间？（如果有：先完成并交付第 0–1 阶段，第 2–3 阶段分批上线。）

## 5. 路线图

| 阶段 | 目标 | 主要内容 | 验收标准 | 相对工作量 |
|---|---|---|---|---|
| 0 安全网 | 先保证能放心地改 | uv 环境与锁文件、修正 README；ruff 清零并强制执行；CI；接口级契约测试；把已知缺陷写成"预期失败"的测试 | ruff 0 问题；测试全绿（缺陷测试标为预期失败）；构建通过 | S |
| 1 边界与工具 | 对外接口不变，内部理顺 | 拆分 `workflow.py`；lifespan + 依赖注入；Agent 核心不再依赖 HTTP 层；工具参数 Pydantic 化、副作用类型化；循环健壮性；共享 HTTP 客户端与重试；修复缺陷 1–11 | 缺陷 1–11 的测试转为通过；演示 4 步能跑；响应字段只增不减 | M |
| 2 状态与记忆 | 一套数据模型 | SQLAlchemy + Alembic；新表；消息只追加；会话锁；接管状态机；上下文构建器；结构化事后分析（修复缺陷 12）；离线评测集 | 并发测试通过；历史完整；西语咨询生成中文摘要 | L |
| 3 API 与前端 | 体验到位 | 会话接口 + SSE；错误码；幂等；OpenAPI 生成类型；前端组件化、Pinia、流式、真实轨迹、自动刷新；输入法与 Markdown 修复 | 构建通过；流式演示可用；刷新不丢会话 | M |
| 4 生产化（可选） | 能上线 | 商家鉴权、限流与配额、Postgres、请求 ID 与 token 成本监控、输出检查、数据保留策略、Docker、后台任务 | 取决于 D7 | M–L |
| 5 业务能力 | 更有用 | 政策/FAQ 知识库、物流与阶梯价规则、渠道接入、商家在控制台直接回复、接管通知 | 需要业务输入（D2） | L |

第 0–1 阶段几乎不依赖上面的业务决策，可以马上开始；第 2 阶段开始前需要确认 D1–D6。

**执行分工：** 后端由 GPT6.1solmax 按 [`refactor-prompt.md`](refactor-prompt.md) 执行；前端由 Claude 按 [`frontend-plan.md`](frontend-plan.md) 执行。两边通过接口契约 `docs/api-contract.md` 对接：前端起草，负责人确认。

## 6. 已知缺陷清单（全部已复现）

| # | 现象 | 根因位置 | 修复阶段 |
|---|---|---|---|
| 1 | 子串匹配误判："cancel"、"France" 命中耳机；"returning" 触发售后转人工；"lightweight"、"flight" 命中氛围灯；"especially" 被判为参数咨询；"你们客服会说英语吗？" 改用英文回复 | `services/workflow.py:440-507` | 1 |
| 2 | `/reset` 之后商品仍被记住；商品上下文也不随会话过期 | `agent/engine.py:67-69` | 1 |
| 3 | `/lang` 只对下一条消息有效，参数也不校验 | `agent/engine.py:194`、`agent/commands.py:46-50` | 1 |
| 4 | 斜杠指令被计入咨询统计，还作为历史发给模型 | `agent/engine.py:195-210` | 1 |
| 5 | 接管队列总是显示售后原因 | `services/workflow.py:267`、`284` | 1 |
| 6 | 不带 `session_id` 的请求共用一个会话 | `agent/engine.py:65` | 1 |
| 7 | 同一会话的并发请求会丢消息 | `agent/session.py:60-91` | 1 临时加锁，2 根治 |
| 8 | 多 worker 时看板数字自相矛盾 | `services/workflow.py:139-167` | 1 |
| 9 | 售后工具收到的问题摘要没有存下来 | `agent/tools/handoff.py:24-41` | 1 |
| 10 | 界面卡片与 Agent 实际行为不一致；工具查到的商品不进会话记忆 | `agent/engine.py:141-143`、`183-194` | 1 |
| 11 | 物流工具对任意目的地都说能送 | `agent/tools/catalog.py:89-100` | 1 |
| 12 | "中文商家摘要"不翻译，直接拼接外文原文 | `services/workflow.py:510-518` | 2 |

## 附录：复现方式

复现脚本的写法和现有测试一样：用脚本化的假模型（测试里的 `ScriptedProvider`）驱动 `AgentEngine`，每个用例使用独立的临时数据库，不需要真实的模型密钥。各缺陷的具体输入和期望结果见 [`refactor-prompt.md`](refactor-prompt.md) 第 6 节，第 0 阶段可以直接把它们改写成回归测试。
