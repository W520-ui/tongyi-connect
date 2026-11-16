// Test helpers: build backend responses (A.0 / A.5 / A.4) and route a fake fetch.

import { vi } from 'vitest'

import type { AgentWorkflowData, Conversation, HandoffTicket, Product } from '@/api/types'

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

export const ok = (data: unknown, status = 200) => json({ status: 'ok', data }, status)

export const fail = (code: string, status: number, message = `${code} message`, details: unknown = null) =>
  json({ status: 'error', error: { code, message, details }, detail: message }, status)

export const frame = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`

export function sse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } })
}

export interface Call {
  method: string
  path: string
  url: string
  body: unknown
  headers: Record<string, string>
}

type Handler = (call: Call) => Response | Promise<Response>

/**
 * Replaces fetch with a router keyed by "METHOD /path" (path without /api/v1 or query).
 * A handler list answers successive calls in order; the last one repeats.
 */
export function routeFetch(routes: Record<string, Handler | Handler[]>) {
  const calls: Call[] = []
  const unexpected: string[] = []
  const counts = new Map<string, number>()
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), 'http://localhost')
    const method = (init.method ?? 'GET').toUpperCase()
    const path = url.pathname.replace(/^\/api\/v1/, '')
    const call: Call = {
      method,
      path,
      url: `${url.pathname}${url.search}`,
      body: init.body ? JSON.parse(String(init.body)) : undefined,
      headers: { ...(init.headers as Record<string, string> | undefined) },
    }
    calls.push(call)
    const key = `${method} ${path}`
    const route = routes[key]
    if (!route) {
      unexpected.push(key)
      throw new TypeError(`Unexpected request: ${key}`)
    }
    const handlers = Array.isArray(route) ? route : [route]
    const index = counts.get(key) ?? 0
    counts.set(key, index + 1)
    const handler = handlers[Math.min(index, handlers.length - 1)]
    if (!handler) throw new TypeError(`No handler for ${key}`)
    return handler(call)
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls, unexpected, fetchMock }
}

export const product: Product = {
  id: 'headset-pro',
  name: '星云降噪耳机 Pro',
  english_name: 'Nebula ANC Headphones Pro',
  category: '3C 数码',
  price_usd: 39,
  stock: 268,
  shipping_days: '5–8 个工作日',
  specs: { 续航: '40 小时' },
}

export function conversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: 'c1',
    status: 'bot_active',
    reply_language: null,
    state: { focused_product_ids: [], destination_country: null, quantity: null },
    open_handoff: null,
    created_at: '2026-11-15T08:00:00+00:00',
    updated_at: '2026-11-15T08:00:00+00:00',
    last_message_at: null,
    ...overrides,
  }
}

export function ticket(overrides: Partial<HandoffTicket> = {}): HandoffTicket {
  return {
    id: 't1',
    conversation_id: 'c1',
    status: 'open',
    reason_code: 'after_sales',
    reason_text: '售后诉求需要人工核实',
    issue_summary: 'Headphones arrived broken',
    customer_message: "My headphones won't turn on",
    language_label: '英语',
    intent_label: '售后服务',
    created_at: '2026-11-15T08:00:00+00:00',
    acknowledged_at: null,
    resolved_at: null,
    ...overrides,
  }
}

export function workflow(overrides: Partial<AgentWorkflowData> = {}): AgentWorkflowData {
  return {
    reply: 'Hello!',
    merchant_summary: '客户打招呼',
    intent: 'general',
    intent_label: '综合咨询',
    detected_intents: ['general'],
    detected_intent_labels: ['综合咨询'],
    task_plan: [],
    language: 'en-US',
    language_label: '英语',
    confidence: 0.9,
    product_confidence: 0,
    matched_product: '未匹配具体商品',
    product_id: null,
    matched_products: [],
    needs_human: false,
    handoff_reason: null,
    steps: [],
    source: 'native',
    conversation_id: 'c1',
    message_id: 'm1',
    client_message_id: null,
    run_id: 'r1',
    replayed: false,
    conversation_status: 'bot_active',
    analysis_source: 'pending',
    trace: [],
    ...overrides,
  }
}
