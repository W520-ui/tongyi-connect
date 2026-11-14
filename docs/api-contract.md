# 接口契约（草案 v0.1）

- **状态：** 草案，等负责人确认。确认之前，后端不要开始第 3 阶段。
- **起草：** 前端（Claude），2026-11-14
- **范围：** 后端第 1 阶段要提前交付的 `/status`，以及第 3 阶段的全部新接口；迁移期间要保留的旧接口见第 7 节。
- **与其他文档的关系：** 本文是 [`refactor-prompt.md`](refactor-prompt.md) 第 4.6 节的字段级展开。两者冲突时以本文为准（第 2 节的业务决策 D1–D8 除外）。修改本文需要负责人同意，并记入第 9 节的变更记录。

## 0. 通用约定

- **基础路径：** `/api/v1`。除 SSE 接口外，请求和响应都是 UTF-8 编码的 JSON。
- **字段命名：** snake_case。可空字段一律返回 `null`，不要省略。
- **时间：** ISO 8601 格式，带时区偏移，例如 `"2026-11-14T08:30:00+00:00"`。
- **ID：** 都是字符串。会话、消息、运行、工单的 ID 由服务端生成（UUID）；`client_message_id` 由前端生成。
- **成功响应：** `{"status": "ok", "data": <载荷>}`。HTTP 状态码为 200，创建资源时为 201。
- **错误响应：** 统一信封，见第 5 节。
- **商家接口：** 标有"商家"的接口要带请求头 `X-Merchant-Key`。后端只有在配置了 `MERCHANT_API_KEY` 时才校验；前端从环境变量 `VITE_MERCHANT_API_KEY` 读取，没设置就不发送。这只是演示用的占位：密钥会被打包进前端代码，真正的鉴权留到第 4 阶段。

## 1. 枚举

```ts
type Language = 'zh-CN' | 'en-US' | 'es-ES'
type Intent = 'quote' | 'logistics' | 'specs' | 'after_sales' | 'general'
type ConversationStatus = 'bot_active' | 'pending_human' | 'human_active' | 'resolved'
type HandoffStatus = 'open' | 'acknowledged' | 'resolved'
type HandoffReasonCode = 'after_sales' | 'user_request' | 'guardrail'
type HistoryRole = 'user' | 'assistant' | 'human_agent' // human_agent 预留给商家直接回复（第 5 阶段）
type ReplySource =
  | 'native' // 模型回复
  | 'native+human-handoff' // 模型回复，并且已登记人工接管
  | 'paused-for-human' // 会话处于 human_active，机器人没有调用模型，只返回固定提示
type AnalysisSource =
  | 'llm' // 事后分析由模型完成
  | 'heuristic' // 事后分析关闭或失败，退回关键词规则
  | 'pending' // 只出现在 SSE 的 completed 事件里：分析结果稍后由 analysis 事件送达
```

## 2. 数据结构

```ts
interface Product {
  id: string
  name: string
  english_name: string
  category: string
  price_usd: number
  stock: number
  shipping_days: string
  specs: Record<string, string>
}

interface ConversationState {
  focused_product_ids: string[]
  destination_country: string | null // ISO 3166-1 alpha-2，例如 "ES"
  quantity: number | null
}

interface HandoffTicket {
  id: string
  conversation_id: string
  status: HandoffStatus
  reason_code: HandoffReasonCode
  reason_text: string // 给商家看的原因，例如"用户主动请求人工接管"
  issue_summary: string | null // 模型调用 after_sales_record 时写的问题摘要
  customer_message: string // 触发工单的那条客户消息，最长 500 字符
  language_label: string // 例如"英语"
  intent_label: string // 例如"售后服务"
  created_at: string
  acknowledged_at: string | null
  resolved_at: string | null
}

interface Conversation {
  id: string
  status: ConversationStatus
  reply_language: Language | null // 显式的回复语言偏好；null 表示跟随客户
  state: ConversationState
  open_handoff: HandoffTicket | null // 尚未解决（open 或 acknowledged）的工单
  created_at: string
  updated_at: string
  last_message_at: string | null
}

interface ToolTraceEntry {
  call_id: string
  round: number // 从 0 开始的工具循环轮次
  name: string
  args: Record<string, unknown>
  ok: boolean
  latency_ms: number
  error: string | null // 给人看的简短原因，不含内部堆栈
}

// 一次"客户消息 → 机器人回复"的结果。前 18 个字段沿用现有 AgentWorkflowData 的名字和含义（source 新增了一个取值）。
interface AgentWorkflowData {
  reply: string
  merchant_summary: string // 中文；外文咨询要包含中文译文（D3）
  intent: Intent
  intent_label: string
  detected_intents: Intent[]
  detected_intent_labels: string[]
  task_plan: string[] // 展示用文案，前端不解析
  language: Language // 客户消息的语言
  language_label: string
  confidence: number // 0–1，仅供参考（见第 8 节问题 2）
  product_confidence: number // 0–1，仅供参考
  matched_product: string // 商品名；没有时为"未匹配具体商品"
  product_id: string | null
  matched_products: Product[] // 来自工具轨迹和会话状态，不再来自关键词猜测
  needs_human: boolean
  handoff_reason: string | null
  steps: string[] // 展示用文案，按真实执行顺序生成；结构化数据见 trace
  source: ReplySource
  // —— 以下为新增字段 ——
  conversation_id: string
  message_id: string // 这条客户消息的 ID
  client_message_id: string | null
  run_id: string | null // source 为 paused-for-human 时为 null
  replayed: boolean // true 表示命中幂等，返回的是之前保存的结果
  conversation_status: ConversationStatus // 处理完这条消息之后的会话状态
  analysis_source: AnalysisSource
  trace: ToolTraceEntry[]
}

interface HistoryMessage {
  id: string
  seq: number // 会话内从 1 开始递增
  role: HistoryRole
  content: string
  created_at: string
  client_message_id: string | null // 只有 user 消息可能有值
  workflow: AgentWorkflowData | null // 只有 assistant 消息有值，用于恢复界面上的卡片
}

interface SystemStatus {
  version: string
  llm_configured: boolean
  model: string | null // 没配置模型时为 null
  db_ok: boolean
}

interface DashboardOverview {
  total_conversations: number // 客户消息数：每条客户消息算一次咨询，不含斜杠指令（与现在的口径一致）
  failed_requests: number // 持久化计数，重启不清零
  human_handoffs: number // 累计创建的工单数
  pending_handoffs: number // status 为 open 的工单数
  resolution_rate: number // (total_conversations - human_handoffs) / total_conversations × 100，保留一位小数；没有数据时为 100
  top_intent: string // 意图的中文名；没有数据时为"暂无数据"
  languages: Array<{ code: string; label: string; count: number }>
  intents: Array<{ code: string; label: string; count: number }>
  started_at: string
}

interface RecentInquiry {
  id: string // 运行 ID
  conversation_id: string
  session_id: string // 兼容字段，等于 conversation_id，兼容层删除时一起去掉
  created_at: string
  message: string // 最长 180 字符
  reply: string // 最长 240 字符
  merchant_summary: string // 最长 240 字符
  intent_label: string
  language_label: string
  needs_human: boolean
  human_acknowledged: boolean
  handoff_reason: string | null
}
```

## 3. 接口

| 方法与路径 | 请求 | 成功响应的 `data` | 可能的错误码 |
|---|---|---|---|
| `GET /status` | — | `SystemStatus` | `INTERNAL_ERROR` |
| `POST /conversations` | `{ reply_language?: Language \| null }` | `Conversation`（201） | `VALIDATION_ERROR` |
| `GET /conversations/{id}` | — | `Conversation` | `CONVERSATION_NOT_FOUND` |
| `PATCH /conversations/{id}` | `{ reply_language: Language \| null }` | `Conversation` | `VALIDATION_ERROR`、`CONVERSATION_NOT_FOUND` |
| `GET /conversations/{id}/messages` | 查询参数：`limit`（默认 50，最大 200）、`before_seq`（可选） | `{ items: HistoryMessage[]; has_more: boolean }` | `CONVERSATION_NOT_FOUND` |
| `POST /conversations/{id}/messages` | `SendMessageRequest` | `AgentWorkflowData` | 见 3.2 |
| `POST /conversations/{id}/messages/stream` | `SendMessageRequest` | SSE 事件流，见第 4 节 | 见 3.2 |
| `POST /conversations/{id}/reset` | — | `{ previous_conversation_id: string; conversation: Conversation }`（201） | `CONVERSATION_NOT_FOUND` |
| `POST /conversations/{id}/handoff` | `{ reason_text?: string }` | `{ conversation: Conversation; ticket: HandoffTicket }` | `CONVERSATION_NOT_FOUND` |
| `GET /handoffs`（商家） | 查询参数：`status`（逗号分隔，默认 `open,acknowledged`）、`limit`（默认 20，最大 50） | `{ items: HandoffTicket[] }` | `VALIDATION_ERROR`、`UNAUTHORIZED` |
| `POST /handoffs/{id}/acknowledge`（商家） | — | `HandoffTicket` | `HANDOFF_NOT_FOUND`、`INVALID_STATE`、`UNAUTHORIZED` |
| `POST /handoffs/{id}/resolve`（商家） | — | `HandoffTicket` | `HANDOFF_NOT_FOUND`、`INVALID_STATE`、`UNAUTHORIZED` |
| `GET /dashboard/overview`（商家） | — | `DashboardOverview` | `UNAUTHORIZED` |
| `GET /dashboard/recent`（商家） | 查询参数：`limit`（默认 8，最大 20） | `RecentInquiry[]` | `UNAUTHORIZED` |
| `GET /catalog/products` | — | `Product[]` | — |

### 3.1 列表与排序

- `GET /conversations/{id}/messages` 按 `seq` 升序返回最新的 `limit` 条；带上 `before_seq` 时，返回 `seq` 小于它的、紧挨着的 `limit` 条。工具消息和斜杠指令不出现在历史里。
- `GET /handoffs` 按 `created_at` 倒序返回。
- `GET /dashboard/recent` 按 `created_at` 倒序返回。

### 3.2 发送消息

```ts
interface SendMessageRequest {
  content: string // 去掉首尾空白后 1–20000 个字符
  client_message_id?: string | null // 最长 64 个字符，只能包含字母、数字、下划线和连字符
}
```

- **幂等：** 同一会话里重复提交同一个 `client_message_id` 时，不再调用模型，直接返回之前保存的结果，并设置 `replayed: true`。如果第一次提交还在处理中，就等它处理完再返回。
- **串行：** 同一会话的消息按到达顺序逐条处理。等待超过 30 秒时返回 `CONVERSATION_BUSY`。
- **机器人暂停：** 会话处于 `human_active` 时，只保存客户消息，返回固定提示（见第 8 节问题 1），`source` 为 `paused-for-human`，`run_id` 为 `null`。
- **会话恢复：** 会话处于 `resolved` 时，收到新消息后回到 `bot_active`（D4）。
- **斜杠指令：** 内容以 `/` 开头时，按指令处理，并返回 `AgentWorkflowData`（`run_id` 为 `null`、`trace` 为空）。指令不写入历史，也不计入统计。
- **可能的错误码：** `VALIDATION_ERROR`、`CONVERSATION_NOT_FOUND`、`CONVERSATION_BUSY`、`LLM_NOT_CONFIGURED`、`LLM_TIMEOUT`、`AGENT_RUN_TIMEOUT`、`LLM_UPSTREAM_ERROR`、`LLM_BAD_RESPONSE`、`RATE_LIMITED`（预留）、`INTERNAL_ERROR`。

### 3.3 会话操作

- **重置：** `reset` 把当前会话标记为 `resolved`，再新建一个会话并返回；前端随后改用新会话的 ID。
- **转人工：** `handoff` 创建一张 `reason_code` 为 `user_request` 的工单，会话进入 `pending_human`。如果已有未解决的工单，就直接返回它，不重复创建。
- **确认接管：** `acknowledge` 只能作用于 `open` 的工单，之后工单变为 `acknowledged`，会话变为 `human_active`。
- **标记解决：** `resolve` 可以作用于 `open` 或 `acknowledged` 的工单，之后工单变为 `resolved`，会话变为 `resolved`。
- **状态不符：** 操作的对象不在允许的状态时，返回 `INVALID_STATE`。

## 4. 流式接口（SSE）

请求：`POST /api/v1/conversations/{id}/messages/stream`，请求头 `Accept: text/event-stream`，请求体为 `SendMessageRequest`。

- 请求本身有问题（校验失败、会话不存在、模型未配置等）时，直接返回普通的 JSON 错误响应（第 5 节），不建立事件流。
- 事件流一旦开始（HTTP 200、`Content-Type: text/event-stream`），后面出现的错误都用 `error` 事件告知。

每个事件的格式是 `event: <名称>`，加一行 `data: <单行 JSON>`，再加一个空行。

| 事件 | `data` | 说明 |
|---|---|---|
| `tool_started` | `{ call_id, round, name, args }` | 开始执行一次工具调用 |
| `tool_finished` | `{ call_id, round, name, ok, latency_ms, error }` | 这次工具调用结束 |
| `delta` | `{ round, text }` | 回复的增量文本 |
| `completed` | `{ data: AgentWorkflowData }` | 回复完成；以 `data.reply` 为最终文本 |
| `analysis` | `AnalysisUpdate`（见下） | 事后分析结果，用来更新卡片 |
| `error` | `{ code, message }` | 出错；流随即结束 |

```ts
interface AnalysisUpdate {
  analysis_source: 'llm' | 'heuristic'
  intent: Intent
  intent_label: string
  detected_intents: Intent[]
  detected_intent_labels: string[]
  language: Language
  language_label: string
  task_plan: string[]
  merchant_summary: string
  product_ids: string[]
  needs_human: boolean // 只是分析结果的标注，不会因此创建工单（D3）
  confidence: number
}
```

**顺序规则：**

1. 先是任意多个 `tool_started`、`tool_finished`、`delta`（可以交错），然后恰好一个 `completed`。
2. 如果 `completed.data.analysis_source` 是 `pending`，后面一定还会有一个 `analysis`；否则流在 `completed` 之后直接结束。
3. 任何时候都可能出现 `error`，出现后流结束，不会再有 `completed`。
4. 某一轮先输出了文本、后来又调用了工具时，这一轮的文本只是开场白，不是最终回复。前端收到同一轮的 `tool_started` 时，丢弃这一轮已经显示的增量文本；收到 `completed` 后，用 `data.reply` 替换显示的内容。
5. 后端每 15 秒发送一行注释 `: ping` 作为心跳；前端 30 秒收不到任何数据就中止，并提示重试。
6. 客户端中途断开时，后端仍然把这次运行完整处理完并落库；前端重新加载历史即可恢复。
7. 命中幂等（`replayed: true`）、斜杠指令、机器人暂停（`paused-for-human`）这三种情况，都没有工具事件和增量文本，直接发送 `completed`，其中的 `analysis_source` 不是 `pending`，所以流随后结束。

## 5. 错误

```json
{
  "status": "error",
  "error": {
    "code": "CONVERSATION_NOT_FOUND",
    "message": "会话不存在或已过期",
    "details": null
  },
  "detail": "会话不存在或已过期"
}
```

- `message` 是可以直接展示给商家的中文说明，不含密钥、上游服务的原始错误或内部堆栈。
- `details` 一般为 `null`；`VALIDATION_ERROR` 时是 `Array<{ loc: Array<string | number>; msg: string }>`。FastAPI 默认的 422 响应要改成这个信封。
- 顶层的 `detail` 只在迁移期间保留，内容与 `error.message` 相同，让旧前端也能显示错误；删除兼容层时一起去掉。

| 错误码 | HTTP 状态 | 含义 |
|---|---|---|
| `VALIDATION_ERROR` | 422 | 请求参数不合法 |
| `UNAUTHORIZED` | 401 | 商家密钥缺失或不正确（只在后端配置了密钥时出现） |
| `CONVERSATION_NOT_FOUND` | 404 | 会话不存在或已过期 |
| `HANDOFF_NOT_FOUND` | 404 | 工单不存在 |
| `INVALID_STATE` | 409 | 对象当前的状态不允许这个操作 |
| `CONVERSATION_BUSY` | 409 | 同一会话的上一条消息还没处理完，等待超时 |
| `RATE_LIMITED` | 429 | 请求太频繁（预留） |
| `LLM_NOT_CONFIGURED` | 503 | 后端没有配置模型密钥 |
| `LLM_UPSTREAM_ERROR` | 502 | 模型服务返回了错误 |
| `LLM_BAD_RESPONSE` | 502 | 模型服务的响应无法解析 |
| `LLM_TIMEOUT` | 504 | 单次模型调用超时 |
| `AGENT_RUN_TIMEOUT` | 504 | 整次运行超过总时限 |
| `INTERNAL_ERROR` | 500 | 其他未预期的错误 |

## 6. 前端这一侧的行为

后端不用实现这些，写在这里是为了让后端知道前端会怎么用接口：

- 会话 ID 存在 `sessionStorage`。页面加载时先调 `GET /conversations/{id}`：返回 `CONVERSATION_NOT_FOUND` 就新建会话，否则用 `GET /conversations/{id}/messages` 恢复历史。
- 默认使用流式接口；不能用流式的环境（比如测试）改用非流式接口。非流式请求的超时是 70 秒。
- 每条消息生成一个 `client_message_id`；网络错误或超时后，用户点"重试"会复用同一个 ID。
- 看板和工单列表每 10 秒刷新一次，页面隐藏时暂停。

## 7. 迁移期间保留的旧接口

在负责人通知"前端已迁移"之前，下面这些接口的路径和响应形状保持不变，只允许新增字段：

| 接口 | 迁移期间的要求 |
|---|---|
| `POST /agent/chat` | 请求字段不变；缺少 `session_id` 时由服务端新建会话；响应里新增 `session_id` |
| `GET /dashboard/overview` | 形状不变，统计口径按第 2 节的 `DashboardOverview` |
| `GET /dashboard/recent` | 形状不变，新增 `conversation_id` |
| `GET /dashboard/handoffs` | 形状不变；第 2 阶段之后，返回的 `id` 换成工单 ID |
| `POST /dashboard/handoffs/{record_id}/acknowledge` | 第 2 阶段之后按工单 ID 处理 |
| `GET /catalog/products`、`GET /health` | 不变 |

旧前端不会发送 `X-Merchant-Key`，所以迁移期间不要配置 `MERCHANT_API_KEY`，等前端迁移完成后再开启。

## 8. 待负责人确认的问题

1. **机器人暂停时的固定提示，按客户的语言给出。** 建议文案：
   - `zh-CN`：已转人工，商家会尽快回复您。
   - `en-US`：You've been connected to our team. A staff member will reply shortly.
   - `es-ES`：Le hemos transferido a nuestro equipo. Un agente le responderá en breve.

   `refactor-prompt.md` 的 D4 里只写了中文版本，确认后需要同步过去。
2. **"置信度"还要不要在界面上展示。** 现在显示的是写死的常数；新实现里只能来自事后分析的模型自评，参考价值有限。建议：保留字段，界面不再显示百分比。
3. **看板口径：** `total_conversations` 按客户消息数统计（与现在一致），`human_handoffs` 按工单数统计。这样一来，`resolution_rate` 会比现在略高：同一个会话里多次提到售后，只算一张工单。
4. **重置的语义：** 把旧会话标记为 `resolved`，并返回一个新会话。
5. **商家密钥放在前端环境变量里**只是演示用的占位，任何人都能从前端代码里读到它；真正的鉴权在第 4 阶段。

## 9. 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v0.1 | 2026-11-14 | 初稿 |
