import { request } from './http'

export interface AgentChatFlags {
  enable_inline_genui?: boolean
  enable_default_system_prompt?: boolean
  enable_streaming?: boolean
  enable_reasoning?: boolean
}

export interface AgentChatRequest {
  message: string
  session_id?: string
  username?: string
  locale?: string
  config_id?: string
  config_name?: string
  selected_provider?: string
  selected_model?: string
  flags?: AgentChatFlags
}

export interface AgentChatResponse<T = unknown> {
  status: string
  data: T
  message?: string
}

export interface AgentWorkflowData {
  reply: string
  merchant_summary: string
  intent: string
  intent_label: string
  detected_intents: string[]
  detected_intent_labels: string[]
  task_plan: string[]
  language: string
  language_label: string
  confidence: number
  product_confidence: number
  matched_product: string
  matched_products: Array<{
    id: string
    name: string
    english_name: string
    category: string
    price_usd: number
    stock: number
    shipping_days: string
    specs: Record<string, string>
  }>
  needs_human: boolean
  handoff_reason: string | null
  steps: string[]
  source: 'astrbot' | 'astrbot+human-handoff' | 'local-demo'
  fallback_notice?: string
}

/**
 * 通过本项目后端调用 AstrBot，浏览器不直接接触 AstrBot API Key。
 */
export function sendAgentMessage<T = unknown>(payload: AgentChatRequest) {
  return request<AgentChatResponse<T>>('/v1/agent/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
    timeoutMs: 70_000,
  })
}
