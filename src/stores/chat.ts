import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'

import { conversationsApi } from '@/api/endpoints'
import { type ApiError, isAbortError, isApiError, toApiError } from '@/api/errors'
import { ReplyBuffer } from '@/api/stream'
import type { AgentWorkflowData, Conversation, HistoryMessage, HistoryRole, Language, Product } from '@/api/types'
import { preferredLocale } from '@/i18n/customer'
import { newClientMessageId } from '@/utils/id'

// A.7: the conversation lives in sessionStorage, so a new tab starts a new chat.
const CONVERSATION_KEY = 'tongyi:conversation-id'
// Saved only after the customer picks a language themselves.
const LOCALE_KEY = 'tongyi:chat-locale'
const PAGE_SIZE = 50
const LANGUAGES: readonly Language[] = ['zh-CN', 'en-US', 'es-ES']

export interface ChatEntry {
  key: string
  seq: number | null
  role: HistoryRole
  content: string
  createdAt: string
  products: Product[]
  /** Customer messages go sending → done or failed; replies are always done. */
  status: 'sending' | 'done' | 'failed'
  clientMessageId: string | null
  error: ApiError | null
  /** The fixed reply sent while a person handles the chat (source paused-for-human). */
  notice: boolean
}

function storageGet(storage: () => Storage, key: string): string | null {
  try {
    return storage().getItem(key)
  } catch {
    return null
  }
}

function storageSet(storage: () => Storage, key: string, value: string | null): void {
  try {
    if (value === null) storage().removeItem(key)
    else storage().setItem(key, value)
  } catch {
    // Private browsing can block storage; the chat still works for this page view.
  }
}

function isLanguage(value: unknown): value is Language {
  return LANGUAGES.includes(value as Language)
}

function fromHistory(message: HistoryMessage): ChatEntry {
  return {
    key: message.id,
    seq: message.seq,
    role: message.role,
    content: message.content,
    createdAt: message.created_at,
    products: message.workflow?.matched_products ?? [],
    status: 'done',
    clientMessageId: message.client_message_id,
    error: null,
    notice: message.workflow?.source === 'paused-for-human',
  }
}

export const useChatStore = defineStore('chat', () => {
  const savedLocale = storageGet(() => localStorage, LOCALE_KEY)
  const chosenLocale = ref<Language | null>(isLanguage(savedLocale) ? savedLocale : null)
  const locale = ref<Language>(chosenLocale.value ?? preferredLocale())

  const conversation = ref<Conversation | null>(null)
  const entries = ref<ChatEntry[]>([])
  const hasMore = ref(false)
  const phase = ref<'idle' | 'connecting' | 'ready' | 'failed'>('idle')
  const connectError = shallowRef<ApiError | null>(null)
  const loadingOlder = ref(false)
  /** A message is on its way; the composer stays disabled meanwhile. */
  const busy = ref(false)
  /** Sent, but no reply text yet: show the typing indicator. */
  const waiting = ref(false)
  const streamingKey = ref<string | null>(null)
  /** Name of the tool the assistant is running, for a friendly status line. */
  const activity = ref<string | null>(null)
  /** A failure that is not tied to one message (handoff, language, new chat…). */
  const notice = shallowRef<ApiError | null>(null)

  let inflight: AbortController | null = null
  let keySeed = 0

  const status = computed(() => conversation.value?.status ?? 'bot_active')
  const handedOff = computed(() => status.value === 'pending_human' || status.value === 'human_active')

  function nextKey(): string {
    keySeed += 1
    return `local-${keySeed}`
  }

  function adopt(next: Conversation): void {
    conversation.value = next
    storageSet(() => sessionStorage, CONVERSATION_KEY, next.id)
  }

  async function loadLatest(): Promise<void> {
    const id = conversation.value?.id
    if (!id) return
    const page = await conversationsApi.messages(id, { limit: PAGE_SIZE })
    entries.value = page.items.map(fromHistory)
    hasMore.value = page.has_more
  }

  /** Restores the saved conversation, or starts a new one when it is gone (A.7). */
  async function connect(): Promise<void> {
    if (phase.value === 'connecting') return
    phase.value = 'connecting'
    connectError.value = null
    try {
      const saved = storageGet(() => sessionStorage, CONVERSATION_KEY)
      let current: Conversation | null = null
      if (saved) {
        try {
          current = await conversationsApi.get(saved)
        } catch (error) {
          if (!isApiError(error, 'CONVERSATION_NOT_FOUND')) throw error
        }
      }
      adopt(current ?? (await conversationsApi.create(chosenLocale.value)))
      await loadLatest()
      phase.value = 'ready'
    } catch (error) {
      connectError.value = toApiError(error)
      phase.value = 'failed'
    }
  }

  async function loadOlder(): Promise<void> {
    const id = conversation.value?.id
    const oldest = entries.value.find((entry) => entry.seq !== null)?.seq
    if (!id || !oldest || loadingOlder.value) return
    loadingOlder.value = true
    try {
      const page = await conversationsApi.messages(id, { limit: PAGE_SIZE, beforeSeq: oldest })
      entries.value = [...page.items.map(fromHistory), ...entries.value]
      hasMore.value = page.has_more
    } catch (error) {
      notice.value = toApiError(error)
    } finally {
      loadingOlder.value = false
    }
  }

  async function switchTo(conversationId: string): Promise<void> {
    adopt(await conversationsApi.get(conversationId))
    await loadLatest()
  }

  function settle(entry: ChatEntry, reply: ChatEntry, data: AgentWorkflowData): void {
    entry.status = 'done'
    reply.content = data.reply
    reply.products = data.matched_products
    reply.notice = data.source === 'paused-for-human'
    streamingKey.value = null
    activity.value = null
    waiting.value = false
    if (conversation.value?.id === data.conversation_id) {
      conversation.value = { ...conversation.value, status: data.conversation_status }
    }
  }

  async function deliver(entry: ChatEntry): Promise<void> {
    const id = conversation.value?.id
    if (!id || busy.value) return
    busy.value = true
    waiting.value = true
    entry.status = 'sending'
    entry.error = null

    const controller = new AbortController()
    inflight = controller
    const buffer = new ReplyBuffer()
    let reply: ChatEntry | null = null
    // A holder object, because TypeScript does not track assignments made inside callbacks.
    const outcome: { data: AgentWorkflowData | null } = { data: null }

    const showReply = (): ChatEntry => {
      if (!reply) {
        entries.value.push({
          key: nextKey(),
          seq: null,
          role: 'assistant',
          content: '',
          createdAt: new Date().toISOString(),
          products: [],
          status: 'done',
          clientMessageId: null,
          error: null,
          notice: false,
        })
        reply = entries.value[entries.value.length - 1] ?? null
        waiting.value = false
      }
      return reply as ChatEntry
    }

    const dropReply = () => {
      if (!reply) return
      const stale = reply
      entries.value = entries.value.filter((item) => item !== stale)
      reply = null
    }

    try {
      await conversationsApi.stream(
        id,
        { content: entry.content, client_message_id: entry.clientMessageId },
        {
          onToolStarted: ({ round, name }) => {
            buffer.toolStarted(round)
            activity.value = name
            // The preamble of this round was discarded: go back to the typing indicator.
            if (reply && !buffer.text) {
              dropReply()
              streamingKey.value = null
              waiting.value = true
            }
          },
          onToolFinished: () => {
            activity.value = null
          },
          onDelta: ({ round, text }) => {
            buffer.delta(round, text)
            const target = showReply()
            target.content = buffer.text
            streamingKey.value = target.key
            activity.value = null
          },
          onCompleted: (data) => {
            outcome.data = data
            settle(entry, showReply(), data)
          },
        },
        { signal: controller.signal },
      )
    } catch (error) {
      // After `completed` the reply is already shown; a later failure only loses the analysis.
      if (!isAbortError(error) && !outcome.data) {
        entry.status = 'failed'
        entry.error = toApiError(error)
        dropReply()
      }
    } finally {
      if (inflight === controller) inflight = null
      busy.value = false
      waiting.value = false
      streamingKey.value = null
      activity.value = null
    }

    // A typed "/reset" closes this conversation and answers from a new one.
    // Skip it when the customer already moved on (e.g. pressed "New chat" meanwhile).
    const result = outcome.data
    if (result && conversation.value?.id === id && result.conversation_id !== id) {
      try {
        await switchTo(result.conversation_id)
      } catch (error) {
        notice.value = toApiError(error)
      }
    }
  }

  async function send(text: string): Promise<void> {
    const content = text.trim()
    if (!content || busy.value || phase.value !== 'ready') return
    entries.value.push({
      key: nextKey(),
      seq: null,
      role: 'user',
      content,
      createdAt: new Date().toISOString(),
      products: [],
      status: 'sending',
      clientMessageId: newClientMessageId(),
      error: null,
      notice: false,
    })
    const entry = entries.value[entries.value.length - 1]
    if (entry) await deliver(entry)
  }

  /** Sends a failed message again with the same client_message_id (A.7). */
  async function retry(key: string): Promise<void> {
    const entry = entries.value.find((item) => item.key === key && item.status === 'failed')
    if (!entry || busy.value) return
    if (isApiError(entry.error, 'CONVERSATION_NOT_FOUND')) {
      // The conversation expired; continue in a fresh one.
      const next = await conversationsApi.create(chosenLocale.value).catch((error: unknown) => {
        notice.value = toApiError(error)
        return null
      })
      if (!next) return
      adopt(next)
      entries.value = entries.value.filter((item) => item === entry)
    }
    await deliver(entry)
  }

  async function startNewChat(): Promise<void> {
    inflight?.abort()
    notice.value = null
    const id = conversation.value?.id
    if (!id) return connect()
    try {
      const result = await conversationsApi.reset(id)
      let next = result.conversation
      if (chosenLocale.value && next.reply_language !== chosenLocale.value) {
        next = await conversationsApi.setReplyLanguage(next.id, chosenLocale.value)
      }
      adopt(next)
      entries.value = []
      hasMore.value = false
    } catch (error) {
      if (isApiError(error, 'CONVERSATION_NOT_FOUND')) {
        storageSet(() => sessionStorage, CONVERSATION_KEY, null)
        conversation.value = null
        entries.value = []
        phase.value = 'idle'
        return connect()
      }
      notice.value = toApiError(error)
    }
  }

  async function requestHandoff(): Promise<void> {
    const id = conversation.value?.id
    if (!id || handedOff.value) return
    try {
      const result = await conversationsApi.handoff(id)
      conversation.value = result.conversation
    } catch (error) {
      notice.value = toApiError(error)
    }
  }

  /** Switching the interface language also sets the reply language (frontend plan, section 2). */
  async function setLocale(next: Language): Promise<void> {
    locale.value = next
    chosenLocale.value = next
    storageSet(() => localStorage, LOCALE_KEY, next)
    const id = conversation.value?.id
    if (!id || conversation.value?.reply_language === next) return
    try {
      const updated = await conversationsApi.setReplyLanguage(id, next)
      if (conversation.value?.id === updated.id) conversation.value = updated
    } catch (error) {
      notice.value = toApiError(error)
    }
  }

  /** Picks up status changes made by the merchant (acknowledged, resolved). */
  async function refreshStatus(): Promise<void> {
    const id = conversation.value?.id
    if (!id || busy.value) return
    try {
      const latest = await conversationsApi.get(id)
      if (conversation.value?.id === latest.id) conversation.value = latest
    } catch {
      // Keep the last known state; the next message reports real problems.
    }
  }

  function dismissNotice(): void {
    notice.value = null
  }

  /** Stops a reply in progress; the backend still finishes and saves it (A.4 rule 6). */
  function cancel(): void {
    inflight?.abort()
  }

  return {
    locale,
    conversation,
    entries,
    hasMore,
    phase,
    connectError,
    loadingOlder,
    busy,
    waiting,
    streamingKey,
    activity,
    notice,
    status,
    handedOff,
    connect,
    loadOlder,
    send,
    retry,
    startNewChat,
    requestHandoff,
    setLocale,
    refreshStatus,
    dismissNotice,
    cancel,
  }
})
