// Prototype-only demo data shaped exactly like the API contract.
// Phase V2 replaces this with the mock backend and real API calls.
import type {
  AgentWorkflowData,
  Conversation,
  DashboardOverview,
  HandoffTicket,
  HistoryMessage,
  HistoryRole,
  Product,
  RecentInquiry,
  SystemStatus,
  ToolTraceEntry,
} from '../api/types'
import { minutesAgo } from '../utils/time'

const headset: Product = {
  id: 'headset-pro',
  name: '星云降噪耳机 Pro',
  english_name: 'Nebula ANC Headphones Pro',
  category: '3C 数码',
  price_usd: 39,
  stock: 268,
  shipping_days: '5–8 个工作日',
  specs: { 续航: '40 小时', 蓝牙: '5.3', 重量: '248g', 颜色: '曜石黑、云雾白' },
}

const lamp: Product = {
  id: 'lamp-mini',
  name: '光屿便携氛围灯',
  english_name: 'Luma Portable Ambient Lamp',
  category: '家居用品',
  price_usd: 24,
  stock: 154,
  shipping_days: '6–10 个工作日',
  specs: { 续航: '18 小时', 充电: 'USB-C', 重量: '390g', 防护: 'IPX4' },
}

const bottle: Product = {
  id: 'bottle-lite',
  name: '澄野保温杯 Lite',
  english_name: 'Clearfield Insulated Bottle Lite',
  category: '生活方式',
  price_usd: 18,
  stock: 412,
  shipping_days: '7–12 个工作日',
  specs: { 容量: '500ml', 材质: '304 不锈钢', 保温: '12 小时', 重量: '285g' },
}

export const products: Product[] = [headset, lamp, bottle]
export const demoProducts = { headset, lamp, bottle }

let callCounter = 0
function call(
  name: string,
  args: Record<string, unknown>,
  latency: number,
  round = 0,
): ToolTraceEntry {
  callCounter += 1
  return { call_id: `call_${callCounter}`, round, name, args, ok: true, latency_ms: latency, error: null }
}

type WorkflowFields = Partial<AgentWorkflowData> & Pick<AgentWorkflowData, 'reply' | 'conversation_id'>

function workflow(fields: WorkflowFields): AgentWorkflowData {
  return {
    merchant_summary: '',
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
    message_id: '',
    client_message_id: null,
    run_id: `run_${fields.conversation_id}`,
    replayed: false,
    conversation_status: 'bot_active',
    analysis_source: 'llm',
    trace: [],
    ...fields,
  }
}

function message(
  conversationId: string,
  seq: number,
  role: HistoryRole,
  content: string,
  minutes: number,
  wf: AgentWorkflowData | null = null,
): HistoryMessage {
  return {
    id: `${conversationId}-m${seq}`,
    seq,
    role,
    content,
    created_at: minutesAgo(minutes),
    client_message_id: null,
    workflow: wf,
  }
}

function conversation(
  id: string,
  status: Conversation['status'],
  minutes: number,
  focused: string[],
  openHandoff: HandoffTicket | null,
): Conversation {
  return {
    id,
    status,
    reply_language: null,
    state: { focused_product_ids: focused, destination_country: null, quantity: null },
    open_handoff: openHandoff,
    created_at: minutesAgo(minutes + 10),
    updated_at: minutesAgo(minutes),
    last_message_at: minutesAgo(minutes),
  }
}

// ---------------------------------------------------------------- customer chat

const CHAT_ID = 'conv-demo-chat'

export const customerChat: HistoryMessage[] = [
  message(CHAT_ID, 1, 'user', 'Hi! Do you ship the Nebula ANC Headphones Pro to Spain?', 6),
  message(
    CHAT_ID,
    2,
    'assistant',
    "Yes, we do! The Nebula ANC Headphones Pro ships to Spain in 5–8 business days. It's USD 39.00 and in stock right now.",
    6,
    workflow({
      reply: '',
      conversation_id: CHAT_ID,
      intent: 'logistics',
      intent_label: '物流查询',
      matched_product: headset.name,
      product_id: headset.id,
      matched_products: [headset],
    }),
  ),
  message(CHAT_ID, 3, 'user', 'Great. Which colors are available?', 4),
  message(
    CHAT_ID,
    4,
    'assistant',
    'It comes in Obsidian Black and Cloud White. Both versions have 40 hours of battery life and Bluetooth 5.3.',
    4,
    workflow({ reply: '', conversation_id: CHAT_ID, intent: 'specs', intent_label: '产品参数' }),
  ),
]

// ---------------------------------------------------------------- inbox

const ticketA: HandoffTicket = {
  id: 'ticket-7f3a',
  conversation_id: 'conv-7f3a',
  status: 'open',
  reason_code: 'after_sales',
  reason_text: '售后、退款或质量问题需要人工核实',
  issue_summary: "Headphones won't power on after delivery; customer requests a replacement.",
  customer_message: "I received them yesterday but they won't turn on at all. I'd like a replacement.",
  language_label: '英语',
  intent_label: '售后服务',
  created_at: minutesAgo(4),
  acknowledged_at: null,
  resolved_at: null,
}

const ticketB: HandoffTicket = {
  id: 'ticket-2c91',
  conversation_id: 'conv-2c91',
  status: 'open',
  reason_code: 'user_request',
  reason_text: '用户主动请求人工接管',
  issue_summary: null,
  customer_message: 'Hola, ¿puedo hablar con una persona? Necesito una factura con el NIF de mi empresa.',
  language_label: '西班牙语',
  intent_label: '综合咨询',
  created_at: minutesAgo(9),
  acknowledged_at: null,
  resolved_at: null,
}

const ticketC: HandoffTicket = {
  id: 'ticket-5d02',
  conversation_id: 'conv-5d02',
  status: 'acknowledged',
  reason_code: 'after_sales',
  reason_text: '售后、退款或质量问题需要人工核实',
  issue_summary: '保温杯收货时杯身有凹痕，客户希望退货',
  customer_message: '保温杯收到的时候杯身有一块凹痕，可以退货吗？',
  language_label: '中文',
  intent_label: '售后服务',
  created_at: minutesAgo(52),
  acknowledged_at: minutesAgo(40),
  resolved_at: null,
}

const ticketD: HandoffTicket = {
  id: 'ticket-91be',
  conversation_id: 'conv-91be',
  status: 'resolved',
  reason_code: 'after_sales',
  reason_text: '售后、退款或质量问题需要人工核实',
  issue_summary: 'Lamp stops charging after about 10 minutes.',
  customer_message: 'The lamp stops charging after 10 minutes. Is it defective?',
  language_label: '英语',
  intent_label: '售后服务',
  created_at: minutesAgo(190),
  acknowledged_at: minutesAgo(170),
  resolved_at: minutesAgo(120),
}

export const tickets: HandoffTicket[] = [ticketA, ticketB, ticketC, ticketD]

export interface InboxThread {
  conversation: Conversation
  messages: HistoryMessage[]
}

export const inboxThreads: Record<string, InboxThread> = {
  'conv-7f3a': {
    conversation: conversation('conv-7f3a', 'pending_human', 4, [headset.id], ticketA),
    messages: [
      message('conv-7f3a', 1, 'user', 'Hi, do you ship the Nebula ANC Headphones Pro to Spain?', 14),
      message(
        'conv-7f3a',
        2,
        'assistant',
        "Yes! The Nebula ANC Headphones Pro ships to Spain in 5–8 business days and costs USD 39.00. It's in stock right now.",
        14,
        workflow({
          reply: '',
          conversation_id: 'conv-7f3a',
          intent: 'logistics',
          intent_label: '物流查询',
          detected_intents: ['logistics', 'quote'],
          detected_intent_labels: ['物流查询', '询价'],
          matched_product: headset.name,
          product_id: headset.id,
          matched_products: [headset],
          merchant_summary: '客户（英语）询问星云降噪耳机 Pro 能否寄往西班牙；已告知 5–8 个工作日送达，售价 39 美元。',
          trace: [
            call('catalog_search', { query: 'Nebula ANC Headphones Pro' }, 11),
            call('catalog_shipping', { product_id: 'headset-pro', destination_country: 'ES' }, 9, 1),
            call('catalog_quote', { product_id: 'headset-pro' }, 7, 1),
          ],
        }),
      ),
      message('conv-7f3a', 3, 'user', ticketA.customer_message, 4),
      message(
        'conv-7f3a',
        4,
        'assistant',
        "I'm really sorry about that. I've logged your replacement request, and a member of our team will follow up with you here shortly.",
        4,
        workflow({
          reply: '',
          conversation_id: 'conv-7f3a',
          intent: 'after_sales',
          intent_label: '售后服务',
          detected_intents: ['after_sales'],
          detected_intent_labels: ['售后服务'],
          matched_product: headset.name,
          product_id: headset.id,
          matched_products: [headset],
          needs_human: true,
          handoff_reason: ticketA.reason_text,
          source: 'native+human-handoff',
          conversation_status: 'pending_human',
          merchant_summary:
            '客户（英语）反馈星云降噪耳机 Pro 收货后完全无法开机，要求换货。译文：我昨天收到耳机，但完全开不了机，希望换一副新的。',
          trace: [
            call(
              'after_sales_record',
              { issue: ticketA.issue_summary, product_id: 'headset-pro' },
              14,
            ),
          ],
        }),
      ),
    ],
  },
  'conv-2c91': {
    conversation: conversation('conv-2c91', 'pending_human', 9, [], ticketB),
    messages: [
      message('conv-2c91', 1, 'user', ticketB.customer_message, 9),
      message(
        'conv-2c91',
        2,
        'assistant',
        '¡Claro! Te he puesto en contacto con nuestro equipo. Una persona te atenderá en breve para ayudarte con la factura.',
        9,
        workflow({
          reply: '',
          conversation_id: 'conv-2c91',
          language: 'es-ES',
          language_label: '西班牙语',
          needs_human: true,
          handoff_reason: ticketB.reason_text,
          source: 'native+human-handoff',
          conversation_status: 'pending_human',
          merchant_summary:
            '客户（西班牙语）要求转人工，需要开具带公司税号（NIF）的发票。译文：你好，可以转真人吗？我需要一张带公司税号的发票。',
        }),
      ),
    ],
  },
  'conv-5d02': {
    conversation: conversation('conv-5d02', 'human_active', 40, [bottle.id], ticketC),
    messages: [
      message('conv-5d02', 1, 'user', ticketC.customer_message, 52),
      message(
        'conv-5d02',
        2,
        'assistant',
        '非常抱歉给你带来不好的体验！我已经登记了你的退货诉求，商家会尽快联系你确认处理方式。',
        52,
        workflow({
          reply: '',
          conversation_id: 'conv-5d02',
          language: 'zh-CN',
          language_label: '中文',
          intent: 'after_sales',
          intent_label: '售后服务',
          detected_intents: ['after_sales'],
          detected_intent_labels: ['售后服务'],
          matched_product: bottle.name,
          product_id: bottle.id,
          matched_products: [bottle],
          needs_human: true,
          handoff_reason: ticketC.reason_text,
          source: 'native+human-handoff',
          conversation_status: 'pending_human',
          merchant_summary: '客户（中文）反馈澄野保温杯 Lite 收货时杯身有凹痕，申请退货。',
          trace: [
            call('after_sales_record', { issue: ticketC.issue_summary, product_id: 'bottle-lite' }, 12),
          ],
        }),
      ),
    ],
  },
  'conv-91be': {
    conversation: conversation('conv-91be', 'resolved', 120, [lamp.id], null),
    messages: [
      message('conv-91be', 1, 'user', ticketD.customer_message, 190),
      message(
        'conv-91be',
        2,
        'assistant',
        "Sorry to hear that! I've recorded the charging issue so our team can check it and arrange a solution for you.",
        190,
        workflow({
          reply: '',
          conversation_id: 'conv-91be',
          intent: 'after_sales',
          intent_label: '售后服务',
          matched_product: lamp.name,
          product_id: lamp.id,
          matched_products: [lamp],
          needs_human: true,
          handoff_reason: ticketD.reason_text,
          source: 'native+human-handoff',
          merchant_summary: '客户（英语）反馈光屿便携氛围灯充电约 10 分钟后就停止充电，怀疑有质量问题。',
          trace: [call('after_sales_record', { issue: ticketD.issue_summary, product_id: 'lamp-mini' }, 10)],
        }),
      ),
    ],
  },
}

// ---------------------------------------------------------------- dashboard

export const overview: DashboardOverview = {
  total_conversations: 128,
  failed_requests: 2,
  human_handoffs: 9,
  pending_handoffs: 2,
  resolution_rate: 93,
  top_intent: '物流查询',
  languages: [
    { code: 'en-US', label: '英语', count: 64 },
    { code: 'zh-CN', label: '中文', count: 41 },
    { code: 'es-ES', label: '西班牙语', count: 23 },
  ],
  intents: [
    { code: 'logistics', label: '物流查询', count: 52 },
    { code: 'quote', label: '询价', count: 47 },
    { code: 'specs', label: '产品参数', count: 21 },
    { code: 'general', label: '综合咨询', count: 18 },
    { code: 'after_sales', label: '售后服务', count: 9 },
  ],
  started_at: minutesAgo(60 * 24 * 7),
}

function inquiry(
  id: string,
  minutes: number,
  message: string,
  intent: string,
  language: string,
  needsHuman = false,
  acknowledged = false,
): RecentInquiry {
  return {
    id: `run-${id}`,
    conversation_id: id,
    session_id: id,
    created_at: minutesAgo(minutes),
    message,
    reply: '',
    merchant_summary: '',
    intent_label: intent,
    language_label: language,
    needs_human: needsHuman,
    human_acknowledged: acknowledged,
    handoff_reason: needsHuman ? '需要人工跟进' : null,
  }
}

export const recentInquiries: RecentInquiry[] = [
  inquiry('conv-7f3a', 4, ticketA.customer_message, '售后服务', '英语', true),
  inquiry('conv-2c91', 9, ticketB.customer_message, '综合咨询', '西班牙语', true),
  inquiry('conv-a4e8', 18, 'How much is the portable lamp if I order 20 units?', '询价', '英语'),
  inquiry('conv-6b13', 31, '降噪耳机支持同时连接两台设备吗？', '产品参数', '中文'),
  inquiry('conv-5d02', 52, ticketC.customer_message, '售后服务', '中文', true, true),
  inquiry('conv-c7d4', 70, '¿Cuánto tarda el envío del termo a México?', '物流查询', '西班牙语'),
]

export const systemStatus: SystemStatus = {
  version: '0.2.0-preview',
  llm_configured: true,
  model: 'gpt-4o-mini',
  db_ok: true,
}
