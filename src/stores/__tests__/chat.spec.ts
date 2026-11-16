import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { conversation, fail, frame, ok, product, routeFetch, sse, ticket, workflow } from '@/test/http'

import { useChatStore } from '../chat'

const CONVERSATION_KEY = 'tongyi:conversation-id'
const STREAM = 'POST /conversations/c1/messages/stream'
const EMPTY_PAGE = { items: [], has_more: false }

beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  localStorage.clear()
})
afterEach(() => vi.unstubAllGlobals())

/** A store already connected to conversation c1 with no history. */
async function connected(routes: Parameters<typeof routeFetch>[0] = {}) {
  sessionStorage.setItem(CONVERSATION_KEY, 'c1')
  const http = routeFetch({
    'GET /conversations/c1': () => ok(conversation()),
    'GET /conversations/c1/messages': () => ok(EMPTY_PAGE),
    ...routes,
  })
  const chat = useChatStore()
  await chat.connect()
  return { chat, ...http }
}

describe('connecting', () => {
  it('restores the saved conversation and rebuilds product cards from history', async () => {
    sessionStorage.setItem(CONVERSATION_KEY, 'c1')
    routeFetch({
      'GET /conversations/c1': () => ok(conversation()),
      'GET /conversations/c1/messages': () =>
        ok({
          items: [
            { id: 'm1', seq: 1, role: 'user', content: 'Headphones?', created_at: '2026-11-15T08:00:00+00:00', client_message_id: 'x', workflow: null },
            {
              id: 'm2',
              seq: 2,
              role: 'assistant',
              content: 'USD 39',
              created_at: '2026-11-15T08:00:01+00:00',
              client_message_id: null,
              workflow: workflow({ reply: 'USD 39', matched_products: [product] }),
            },
          ],
          has_more: true,
        }),
    })
    const chat = useChatStore()
    await chat.connect()
    expect(chat.phase).toBe('ready')
    expect(chat.entries.map((entry) => [entry.role, entry.content])).toEqual([
      ['user', 'Headphones?'],
      ['assistant', 'USD 39'],
    ])
    expect(chat.entries[1]?.products).toEqual([product])
    expect(chat.hasMore).toBe(true)
  })

  it('starts a new conversation when the saved one has expired', async () => {
    sessionStorage.setItem(CONVERSATION_KEY, 'gone')
    const { calls } = routeFetch({
      'GET /conversations/gone': () => fail('CONVERSATION_NOT_FOUND', 404),
      'POST /conversations': () => ok(conversation({ id: 'c2' }), 201),
      'GET /conversations/c2/messages': () => ok(EMPTY_PAGE),
    })
    const chat = useChatStore()
    await chat.connect()
    expect(chat.conversation?.id).toBe('c2')
    expect(sessionStorage.getItem(CONVERSATION_KEY)).toBe('c2')
    // Without an explicit choice the bot follows the customer's language.
    expect(calls.find((call) => call.method === 'POST')?.body).toEqual({ reply_language: null })
  })

  it('reports a backend that cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const chat = useChatStore()
    await chat.connect()
    expect(chat.phase).toBe('failed')
    expect(chat.connectError?.code).toBe('NETWORK_ERROR')
  })
})

describe('sending', () => {
  it('streams the reply, drops a discarded preamble and shows the final text with products', async () => {
    const { chat, calls } = await connected({
      [STREAM]: () =>
        sse([
          frame('delta', { round: 0, text: 'Let me check' }),
          frame('tool_started', { call_id: 'a', round: 0, name: 'catalog_shipping', args: {} }),
          frame('tool_finished', { call_id: 'a', round: 0, name: 'catalog_shipping', ok: true, latency_ms: 9, error: null }),
          frame('delta', { round: 1, text: 'Ships in 5–8 days' }),
          frame('completed', { data: workflow({ reply: 'Ships in 5–8 days.', matched_products: [product] }) }),
          frame('analysis', { analysis_source: 'llm' }),
        ]),
    })
    await chat.send('  Do you ship to Spain?  ')

    expect(chat.entries.map((entry) => [entry.role, entry.content, entry.status])).toEqual([
      ['user', 'Do you ship to Spain?', 'done'],
      ['assistant', 'Ships in 5–8 days.', 'done'],
    ])
    expect(chat.entries[1]?.products).toEqual([product])
    expect(chat.busy).toBe(false)
    expect(chat.waiting).toBe(false)
    const body = calls.find((call) => call.path.endsWith('/stream'))?.body as Record<string, string>
    expect(body.content).toBe('Do you ship to Spain?')
    expect(body.client_message_id).toMatch(/^[A-Za-z0-9_-]{1,64}$/)
  })

  it('marks a message failed and retries it with the same client_message_id', async () => {
    const { chat, calls } = await connected({
      [STREAM]: [
        () => Promise.reject(new TypeError('Failed to fetch')),
        () => sse([frame('completed', { data: workflow({ reply: 'Hello again', replayed: true }) })]),
      ],
    })
    await chat.send('Hello')
    const entry = chat.entries[0]
    expect(entry?.status).toBe('failed')
    expect(entry?.error?.code).toBe('NETWORK_ERROR')
    expect(chat.entries).toHaveLength(1)

    await chat.retry(entry?.key ?? '')
    const ids = calls.filter((call) => call.path.endsWith('/stream')).map((call) => (call.body as { client_message_id: string }).client_message_id)
    expect(ids).toHaveLength(2)
    expect(ids[0]).toBe(ids[1])
    expect(chat.entries.map((item) => [item.role, item.content, item.status])).toEqual([
      ['user', 'Hello', 'done'],
      ['assistant', 'Hello again', 'done'],
    ])
  })

  it('shows the fixed prompt as a notice while a person handles the chat', async () => {
    const { chat } = await connected({
      [STREAM]: () =>
        sse([
          frame('completed', {
            data: workflow({
              reply: "You've been connected to our team.",
              source: 'paused-for-human',
              run_id: null,
              conversation_status: 'human_active',
              analysis_source: 'heuristic',
            }),
          }),
        ]),
    })
    await chat.send('Anyone there?')
    expect(chat.entries[1]?.notice).toBe(true)
    expect(chat.status).toBe('human_active')
    expect(chat.handedOff).toBe(true)
  })

  it('follows a typed /reset to the conversation the backend opened', async () => {
    const { chat } = await connected({
      [STREAM]: () => sse([frame('completed', { data: workflow({ reply: '已新建会话', run_id: null, conversation_id: 'c2' }) })]),
      'GET /conversations/c2': () => ok(conversation({ id: 'c2' })),
      'GET /conversations/c2/messages': () => ok(EMPTY_PAGE),
    })
    await chat.send('/reset')
    expect(chat.conversation?.id).toBe('c2')
    expect(sessionStorage.getItem(CONVERSATION_KEY)).toBe('c2')
    expect(chat.entries).toEqual([])
  })
})

describe('conversation actions', () => {
  it('asks for a person and reflects the pending state', async () => {
    const { chat } = await connected({
      'POST /conversations/c1/handoff': () =>
        ok({ conversation: conversation({ status: 'pending_human' }), ticket: ticket({ reason_code: 'user_request' }) }),
    })
    await chat.requestHandoff()
    expect(chat.status).toBe('pending_human')
    expect(chat.handedOff).toBe(true)
  })

  it('switching the language also sets the reply language and remembers the choice', async () => {
    const { chat, calls } = await connected({
      'PATCH /conversations/c1': () => ok(conversation({ reply_language: 'es-ES' })),
    })
    await chat.setLocale('es-ES')
    expect(calls.find((call) => call.method === 'PATCH')?.body).toEqual({ reply_language: 'es-ES' })
    expect(chat.conversation?.reply_language).toBe('es-ES')
    expect(localStorage.getItem('tongyi:chat-locale')).toBe('es-ES')
  })

  it('starts a new chat through the reset endpoint and keeps the chosen language', async () => {
    localStorage.setItem('tongyi:chat-locale', 'zh-CN')
    const { chat, calls } = await connected({
      'POST /conversations/c1/reset': () => ok({ previous_conversation_id: 'c1', conversation: conversation({ id: 'c3' }) }, 201),
      'PATCH /conversations/c3': () => ok(conversation({ id: 'c3', reply_language: 'zh-CN' })),
    })
    await chat.startNewChat()
    expect(chat.conversation).toMatchObject({ id: 'c3', reply_language: 'zh-CN' })
    expect(sessionStorage.getItem(CONVERSATION_KEY)).toBe('c3')
    expect(calls.find((call) => call.method === 'PATCH')?.body).toEqual({ reply_language: 'zh-CN' })
  })
})
