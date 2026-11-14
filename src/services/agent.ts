import { request } from './http'

export interface AgentChatFlags {
  enable_streaming?: boolean
}

export interface AgentChatRequest {
  message: string
  session_id?: string
  username?: string
  locale?: string
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
  source: 'native' | 'native+human-handoff'
}

/**
 * 通过本项目后端调用自研 Agent 运行时，浏览器不直接接触模型密钥。
 */
export function sendAgentMessage<T = unknown>(payload: AgentChatRequest) {
  return request<AgentChatResponse<T>>('/v1/agent/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
    timeoutMs: 70_000,
  })
}
