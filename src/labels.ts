import type { ConversationStatus, HandoffReasonCode, HandoffStatus, Language } from './api/types'

export type Tone = 'neutral' | 'brand' | 'success' | 'info' | 'warning'

/** Flat badge colors per tone; pair with the shadcn `Badge` component. */
export const TONE_CLASSES: Record<Tone, string> = {
  neutral: 'bg-muted text-muted-foreground',
  brand: 'bg-brand-soft text-brand',
  success: 'bg-success-soft text-success',
  info: 'bg-info-soft text-info',
  warning: 'bg-warning-soft text-warning',
}

export const LANGUAGE_META: Record<Language, { label: string; native: string; short: string }> = {
  'zh-CN': { label: '中文', native: '中文', short: '中' },
  'en-US': { label: '英语', native: 'English', short: 'EN' },
  'es-ES': { label: '西班牙语', native: 'Español', short: 'ES' },
}

export const CONVERSATION_STATUS_META: Record<ConversationStatus, { label: string; tone: Tone }> = {
  bot_active: { label: '机器人接待中', tone: 'success' },
  pending_human: { label: '待人工接管', tone: 'warning' },
  human_active: { label: '人工处理中', tone: 'info' },
  resolved: { label: '已解决', tone: 'neutral' },
}

export const HANDOFF_STATUS_META: Record<HandoffStatus, { label: string; tone: Tone }> = {
  open: { label: '待接管', tone: 'warning' },
  acknowledged: { label: '处理中', tone: 'info' },
  resolved: { label: '已解决', tone: 'success' },
}

export const HANDOFF_REASON_LABELS: Record<HandoffReasonCode, string> = {
  after_sales: '售后诉求',
  user_request: '客户要求',
  guardrail: '规则兜底',
}

export const TOOL_LABELS: Record<string, string> = {
  catalog_search: '检索商品',
  catalog_quote: '查询报价',
  catalog_shipping: '查询物流',
  catalog_specs: '查询参数',
  after_sales_record: '登记售后',
  knowledge_search: '检索知识库',
}

export function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name
}
