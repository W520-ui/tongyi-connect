import type { Language } from '../api/types'

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
  welcomeTitle: string
  welcomeBody: string
  suggestions: readonly [string, string, string]
  poweredBy: string
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
    handoffTitle: "You're connected to our team",
    handoffBody: 'A staff member will reply here shortly. Feel free to add more details.',
    welcomeTitle: 'Hi there 👋',
    welcomeBody: 'Ask us anything about our products, prices or delivery. We reply in your language.',
    suggestions: [
      'Do you ship the ANC headphones to Spain?',
      'How much is the portable lamp?',
      "My headphones arrived and won't turn on",
    ],
    poweredBy: 'Powered by Tongyi Connect',
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
    handoffTitle: 'Te hemos conectado con nuestro equipo',
    handoffBody: 'Un agente te responderá aquí en breve. Puedes seguir añadiendo detalles.',
    welcomeTitle: '¡Hola! 👋',
    welcomeBody: 'Pregúntanos lo que quieras sobre productos, precios o entregas. Respondemos en tu idioma.',
    suggestions: [
      '¿Enviáis los auriculares ANC a España?',
      '¿Cuánto cuesta la lámpara portátil?',
      'Mis auriculares llegaron y no encienden',
    ],
    poweredBy: 'Con la tecnología de Tongyi Connect',
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
    handoffTitle: '已为你转接人工客服',
    handoffBody: '商家会尽快在这里回复你，你也可以继续补充细节。',
    welcomeTitle: '你好 👋',
    welcomeBody: '商品、价格、物流，有什么想问的都可以直接说。',
    suggestions: ['降噪耳机能发往西班牙吗？', '便携氛围灯多少钱？', '耳机收到后无法开机'],
    poweredBy: '由 通译智联 提供支持',
    shipsIn: (days) => `${days} 个工作日送达`,
    inStock: (count) => `库存 ${count}`,
  },
}
