import type { Language } from '../api/types'

/** What went wrong, in words a customer can act on. Internal details never reach this page. */
export type CustomerErrorKind = 'network' | 'timeout' | 'busy' | 'unavailable' | 'invalid' | 'rateLimited' | 'expired'

/** Shown while the assistant runs a tool. The tool names themselves stay internal. */
export type ActivityKind = 'search' | 'quote' | 'shipping' | 'specs' | 'afterSales' | 'other'

export interface CustomerStrings {
  status: string
  language: string
  talkToHuman: string
  newChat: string
  placeholder: string
  hint: string
  send: string
  typing: string
  handoffTitle: string
  handoffBody: string
  staffTitle: string
  staffBody: string
  welcomeTitle: string
  welcomeBody: string
  suggestions: readonly [string, string, string]
  poweredBy: string
  connecting: string
  connectFailed: string
  tryAgain: string
  retry: string
  notSent: string
  earlier: string
  dismiss: string
  errors: Record<CustomerErrorKind, string>
  activity: Record<ActivityKind, string>
  shipsIn: (days: string) => string
  inStock: (count: number) => string
}

export const customerStrings: Record<Language, CustomerStrings> = {
  'en-US': {
    status: 'AI assistant · usually replies in seconds',
    language: 'Language',
    talkToHuman: 'Talk to a person',
    newChat: 'New chat',
    placeholder: 'Ask about products, prices or shipping…',
    hint: 'Enter to send · Shift + Enter for a new line',
    send: 'Send',
    typing: 'Assistant is typing',
    handoffTitle: "You're in the queue for our team",
    handoffBody: 'A staff member will pick up this chat shortly. The assistant keeps helping until then.',
    staffTitle: 'A team member is handling your chat',
    staffBody: 'A staff member will get back to you shortly. Feel free to add more details.',
    welcomeTitle: 'Hi there 👋',
    welcomeBody: 'Ask us anything about our products, prices or delivery. We reply in your language.',
    suggestions: [
      'Do you ship the ANC headphones to Spain?',
      'How much is the portable lamp?',
      "My headphones arrived and won't turn on",
    ],
    poweredBy: 'Powered by Tongyi Connect',
    connecting: 'Connecting…',
    connectFailed: "We couldn't start the chat.",
    tryAgain: 'Try again',
    retry: 'Retry',
    notSent: 'Not sent',
    earlier: 'Show earlier messages',
    dismiss: 'Dismiss',
    errors: {
      network: "We can't reach the store right now. Check your connection and try again.",
      timeout: 'The reply is taking too long. Please try again.',
      busy: "We're still answering your previous message. Please wait a moment.",
      unavailable: 'Our assistant is unavailable right now. Please try again later.',
      invalid: "This message can't be sent. Please shorten it and try again.",
      rateLimited: 'Too many messages at once. Please wait a moment.',
      expired: 'This chat has expired. Start a new chat to continue.',
    },
    activity: {
      search: 'Searching our catalog…',
      quote: 'Checking the price…',
      shipping: 'Checking delivery options…',
      specs: 'Looking up the details…',
      afterSales: 'Logging your request…',
      other: 'Looking that up…',
    },
    shipsIn: (days) => `Ships in ${days} business days`,
    inStock: (count) => `${count} in stock`,
  },
  'es-ES': {
    status: 'Asistente IA · suele responder en segundos',
    language: 'Idioma',
    talkToHuman: 'Hablar con una persona',
    newChat: 'Nueva conversación',
    placeholder: 'Pregunta por productos, precios o envíos…',
    hint: 'Intro para enviar · Mayús + Intro para nueva línea',
    send: 'Enviar',
    typing: 'El asistente está escribiendo',
    handoffTitle: 'Estás en la cola de nuestro equipo',
    handoffBody: 'Una persona atenderá este chat en breve. Mientras tanto, el asistente sigue ayudándote.',
    staffTitle: 'Una persona de nuestro equipo atiende tu chat',
    staffBody: 'Te responderá en breve. Puedes seguir añadiendo detalles.',
    welcomeTitle: '¡Hola! 👋',
    welcomeBody: 'Pregúntanos lo que quieras sobre productos, precios o entregas. Respondemos en tu idioma.',
    suggestions: [
      '¿Enviáis los auriculares ANC a España?',
      '¿Cuánto cuesta la lámpara portátil?',
      'Mis auriculares llegaron y no encienden',
    ],
    poweredBy: 'Con la tecnología de Tongyi Connect',
    connecting: 'Conectando…',
    connectFailed: 'No pudimos iniciar el chat.',
    tryAgain: 'Reintentar',
    retry: 'Reintentar',
    notSent: 'No enviado',
    earlier: 'Ver mensajes anteriores',
    dismiss: 'Cerrar',
    errors: {
      network: 'No podemos conectar con la tienda ahora mismo. Revisa tu conexión e inténtalo de nuevo.',
      timeout: 'La respuesta está tardando demasiado. Inténtalo de nuevo.',
      busy: 'Aún estamos respondiendo a tu mensaje anterior. Espera un momento.',
      unavailable: 'Nuestro asistente no está disponible ahora. Inténtalo más tarde.',
      invalid: 'No se puede enviar este mensaje. Acórtalo e inténtalo de nuevo.',
      rateLimited: 'Demasiados mensajes seguidos. Espera un momento.',
      expired: 'Este chat ha caducado. Inicia una nueva conversación para continuar.',
    },
    activity: {
      search: 'Buscando en el catálogo…',
      quote: 'Consultando el precio…',
      shipping: 'Consultando opciones de envío…',
      specs: 'Consultando los detalles…',
      afterSales: 'Registrando tu solicitud…',
      other: 'Consultando…',
    },
    shipsIn: (days) => `Envío en ${days} días hábiles`,
    inStock: (count) => `${count} en stock`,
  },
  'zh-CN': {
    status: 'AI 助手 · 通常几秒内回复',
    language: '语言',
    talkToHuman: '转人工',
    newChat: '新会话',
    placeholder: '问问商品、价格或物流…',
    hint: 'Enter 发送 · Shift + Enter 换行',
    send: '发送',
    typing: '助手正在输入',
    handoffTitle: '已为你排队转接人工客服',
    handoffBody: '商家会尽快接手这个会话，在此之前助手会继续为你解答。',
    staffTitle: '人工客服正在处理你的会话',
    staffBody: '商家会尽快回复你，你也可以继续补充细节。',
    welcomeTitle: '你好 👋',
    welcomeBody: '商品、价格、物流，有什么想问的都可以直接说。',
    suggestions: ['降噪耳机能发往西班牙吗？', '便携氛围灯多少钱？', '耳机收到后无法开机'],
    poweredBy: '由 通译智联 提供支持',
    connecting: '正在连接…',
    connectFailed: '暂时无法连接客服。',
    tryAgain: '重新连接',
    retry: '重试',
    notSent: '发送失败',
    earlier: '查看更早的消息',
    dismiss: '关闭',
    errors: {
      network: '暂时连不上店铺，请检查网络后重试。',
      timeout: '回复时间太长了，请重试。',
      busy: '上一条消息还在处理中，请稍等片刻。',
      unavailable: '智能助手暂时不可用，请稍后再试。',
      invalid: '这条消息无法发送，请缩短后重试。',
      rateLimited: '消息发得太快了，请稍等片刻。',
      expired: '这个会话已经过期，请开始新会话。',
    },
    activity: {
      search: '正在查找商品…',
      quote: '正在查询价格…',
      shipping: '正在查询物流…',
      specs: '正在查询商品参数…',
      afterSales: '正在登记你的诉求…',
      other: '正在查询…',
    },
    shipsIn: (days) => `${days} 个工作日送达`,
    inStock: (count) => `库存 ${count}`,
  },
}

const ACTIVITY_BY_TOOL: Record<string, ActivityKind> = {
  catalog_search: 'search',
  catalog_quote: 'quote',
  catalog_shipping: 'shipping',
  catalog_specs: 'specs',
  after_sales_record: 'afterSales',
}

export function activityKind(toolName: string): ActivityKind {
  return ACTIVITY_BY_TOOL[toolName] ?? 'other'
}

const ERROR_KIND_BY_CODE: Record<string, CustomerErrorKind> = {
  NETWORK_ERROR: 'network',
  REQUEST_TIMEOUT: 'timeout',
  STREAM_STALLED: 'timeout',
  STREAM_INTERRUPTED: 'timeout',
  LLM_TIMEOUT: 'timeout',
  AGENT_RUN_TIMEOUT: 'timeout',
  CONVERSATION_BUSY: 'busy',
  VALIDATION_ERROR: 'invalid',
  RATE_LIMITED: 'rateLimited',
  CONVERSATION_NOT_FOUND: 'expired',
}

export function customerErrorKind(code: string): CustomerErrorKind {
  return ERROR_KIND_BY_CODE[code] ?? 'unavailable'
}

/** UI language from the browser: Spanish and Chinese when preferred, English otherwise. */
export function preferredLocale(languages: readonly string[] = navigator.languages ?? []): Language {
  for (const tag of languages) {
    const primary = tag.toLowerCase().split('-')[0]
    if (primary === 'es') return 'es-ES'
    if (primary === 'zh') return 'zh-CN'
    if (primary === 'en') return 'en-US'
  }
  return 'en-US'
}
