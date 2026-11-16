// Types from the API contract v0.1 (docs/backend-prompt.md, appendix A).
// Keep this file in sync with the contract; field names are snake_case on purpose.

export type Language = 'zh-CN' | 'en-US' | 'es-ES'
export type Intent = 'quote' | 'logistics' | 'specs' | 'after_sales' | 'general'
export type ConversationStatus = 'bot_active' | 'pending_human' | 'human_active' | 'resolved'
export type HandoffStatus = 'open' | 'acknowledged' | 'resolved'
export type HandoffReasonCode = 'after_sales' | 'user_request' | 'guardrail'
export type HistoryRole = 'user' | 'assistant' | 'human_agent'
export type ReplySource = 'native' | 'native+human-handoff' | 'paused-for-human'
export type AnalysisSource = 'llm' | 'heuristic' | 'pending'

export interface Product {
  id: string
  name: string
  english_name: string
  category: string
  price_usd: number
  stock: number
  shipping_days: string
  specs: Record<string, string>
}

export interface ConversationState {
  focused_product_ids: string[]
  destination_country: string | null
  quantity: number | null
}

export interface HandoffTicket {
  id: string
  conversation_id: string
  status: HandoffStatus
  reason_code: HandoffReasonCode
  reason_text: string
  issue_summary: string | null
  customer_message: string
  language_label: string
  intent_label: string
  created_at: string
  acknowledged_at: string | null
  resolved_at: string | null
}

export interface Conversation {
  id: string
  status: ConversationStatus
  reply_language: Language | null
  state: ConversationState
  open_handoff: HandoffTicket | null
  created_at: string
  updated_at: string
  last_message_at: string | null
}

export interface ToolTraceEntry {
  call_id: string
  round: number
  name: string
  args: Record<string, unknown>
  ok: boolean
  latency_ms: number
  error: string | null
}

export interface AgentWorkflowData {
  reply: string
  merchant_summary: string
  intent: Intent
  intent_label: string
  detected_intents: Intent[]
  detected_intent_labels: string[]
  task_plan: string[]
  language: Language
  language_label: string
  confidence: number
  product_confidence: number
  matched_product: string
  product_id: string | null
  matched_products: Product[]
  needs_human: boolean
  handoff_reason: string | null
  steps: string[]
  source: ReplySource
  conversation_id: string
  message_id: string
  client_message_id: string | null
  run_id: string | null
  replayed: boolean
  conversation_status: ConversationStatus
  analysis_source: AnalysisSource
  trace: ToolTraceEntry[]
}

export interface HistoryMessage {
  id: string
  seq: number
  role: HistoryRole
  content: string
  created_at: string
  client_message_id: string | null
  workflow: AgentWorkflowData | null
}

export interface SystemStatus {
  version: string
  llm_configured: boolean
  model: string | null
  db_ok: boolean
}

export interface DistributionItem {
  code: string
  label: string
  count: number
}

export interface DashboardOverview {
  total_conversations: number
  failed_requests: number
  human_handoffs: number
  pending_handoffs: number
  resolution_rate: number
  top_intent: string
  languages: DistributionItem[]
  intents: DistributionItem[]
  started_at: string
}

// The backend also returns issue_summary here for the legacy route (A.6); the console does not use it.
export interface RecentInquiry {
  id: string
  conversation_id: string
  session_id: string
  created_at: string
  message: string
  reply: string
  merchant_summary: string
  intent_label: string
  language_label: string
  needs_human: boolean
  human_acknowledged: boolean
  handoff_reason: string | null
}

export interface SendMessageRequest {
  content: string
  client_message_id?: string | null
}

export interface MessagePage {
  items: HistoryMessage[]
  has_more: boolean
}

export interface ResetResult {
  previous_conversation_id: string
  conversation: Conversation
}

export interface HandoffResult {
  conversation: Conversation
  ticket: HandoffTicket
}

// SSE event payloads (A.4).
export interface ToolStartedEvent {
  call_id: string
  round: number
  name: string
  args: Record<string, unknown>
}

export interface ToolFinishedEvent {
  call_id: string
  round: number
  name: string
  ok: boolean
  latency_ms: number
  error: string | null
}

export interface DeltaEvent {
  round: number
  text: string
}

export interface StreamErrorEvent {
  code: string
  message: string
}

export interface AnalysisUpdate {
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
  needs_human: boolean
  confidence: number
}
