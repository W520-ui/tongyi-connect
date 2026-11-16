// One function per endpoint in appendix A.3. Merchant routes send X-Merchant-Key.

import { request } from './client'
import { streamMessage } from './stream'
import type {
  AgentWorkflowData,
  Conversation,
  DashboardOverview,
  HandoffResult,
  HandoffStatus,
  HandoffTicket,
  Language,
  MessagePage,
  Product,
  RecentInquiry,
  ResetResult,
  SendMessageRequest,
  SystemStatus,
} from './types'

const path = (id: string) => `/conversations/${encodeURIComponent(id)}`

// A non-streaming reply may take as long as a whole agent run (A.7: 70 s).
const SEND_TIMEOUT_MS = 70_000

export const conversationsApi = {
  create: (replyLanguage: Language | null = null) =>
    request<Conversation>('/conversations', { method: 'POST', body: { reply_language: replyLanguage } }),

  get: (id: string) => request<Conversation>(path(id)),

  setReplyLanguage: (id: string, replyLanguage: Language | null) =>
    request<Conversation>(path(id), { method: 'PATCH', body: { reply_language: replyLanguage } }),

  messages: (id: string, { limit = 50, beforeSeq }: { limit?: number; beforeSeq?: number } = {}) =>
    request<MessagePage>(`${path(id)}/messages`, { query: { limit, before_seq: beforeSeq } }),

  send: (id: string, body: SendMessageRequest, signal?: AbortSignal) =>
    request<AgentWorkflowData>(`${path(id)}/messages`, {
      method: 'POST',
      body,
      signal,
      timeoutMs: SEND_TIMEOUT_MS,
    }),

  stream: streamMessage,

  reset: (id: string) => request<ResetResult>(`${path(id)}/reset`, { method: 'POST' }),

  handoff: (id: string, reasonText?: string) =>
    request<HandoffResult>(`${path(id)}/handoff`, {
      method: 'POST',
      body: reasonText ? { reason_text: reasonText } : {},
    }),
}

export const merchantApi = {
  handoffs: ({ status = ['open', 'acknowledged'], limit = 50 }: { status?: HandoffStatus[]; limit?: number } = {}) =>
    request<{ items: HandoffTicket[] }>('/handoffs', { merchant: true, query: { status: status.join(','), limit } }),

  acknowledge: (id: string) =>
    request<HandoffTicket>(`/handoffs/${encodeURIComponent(id)}/acknowledge`, { method: 'POST', merchant: true }),

  resolve: (id: string) =>
    request<HandoffTicket>(`/handoffs/${encodeURIComponent(id)}/resolve`, { method: 'POST', merchant: true }),

  overview: () => request<DashboardOverview>('/dashboard/overview', { merchant: true }),

  recent: (limit = 8) => request<RecentInquiry[]>('/dashboard/recent', { merchant: true, query: { limit } }),
}

export const publicApi = {
  status: () => request<SystemStatus>('/status'),
  products: () => request<Product[]>('/catalog/products'),
}
