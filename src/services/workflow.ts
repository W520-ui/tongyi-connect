import { request } from './http'

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

export interface DashboardOverview {
  total_conversations: number
  failed_requests: number
  human_handoffs: number
  pending_handoffs: number
  resolution_rate: number
  top_intent: string
  languages: Array<{ code: string; label: string; count: number }>
  intents: Array<{ code: string; label: string; count: number; ratio?: number }>
  started_at: string
}

export interface RecentConversation {
  id: string
  created_at: string
  session_id: string
  message: string
  reply: string
  merchant_summary: string
  intent_label: string
  language_label: string
  needs_human: boolean
  handoff_reason?: string
  human_acknowledged?: boolean
}

interface ApiEnvelope<T> {
  status: string
  data: T
}

export interface HealthStatus {
  status: 'ok'
  service: string
  version: string
}

export function getHealth() {
  return request<HealthStatus>('/v1/health')
}

export function getDashboardOverview() {
  return request<ApiEnvelope<DashboardOverview>>('/v1/dashboard/overview')
}

export function getProducts() {
  return request<ApiEnvelope<Product[]>>('/v1/catalog/products')
}

export function getRecentConversations(limit = 6) {
  return request<ApiEnvelope<RecentConversation[]>>(`/v1/dashboard/recent?limit=${limit}`)
}

export function getPendingHandoffs(limit = 20) {
  return request<ApiEnvelope<RecentConversation[]>>(`/v1/dashboard/handoffs?limit=${limit}`)
}

export function acknowledgeHandoff(recordId: string) {
  return request<ApiEnvelope<{ record_id: string }>>(`/v1/dashboard/handoffs/${encodeURIComponent(recordId)}/acknowledge`, {
    method: 'POST',
  })
}

