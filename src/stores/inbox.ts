import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'

import { conversationsApi, merchantApi } from '@/api/endpoints'
import { type ApiError, toApiError } from '@/api/errors'
import type { Conversation, HandoffStatus, HandoffTicket, HistoryMessage } from '@/api/types'

export interface InboxThread {
  conversation: Conversation
  messages: HistoryMessage[]
}

const ACTIVE_LIMIT = 50 // the maximum GET /handoffs allows
const RESOLVED_LIMIT = 20
const THREAD_LIMIT = 200

/** Handoff tickets (GET /handoffs) and the conversation behind the selected one. */
export const useInboxStore = defineStore('inbox', () => {
  const active = ref<HandoffTicket[]>([]) // open and acknowledged
  const resolved = ref<HandoffTicket[]>([]) // the most recent ones only
  const tab = ref<HandoffStatus>('open')
  const selectedId = ref<string | null>(null)
  const thread = ref<InboxThread | null>(null)
  const loaded = ref(false)
  const error = shallowRef<ApiError | null>(null)
  const threadError = shallowRef<ApiError | null>(null)
  const loadingThread = ref(false)
  /** Ticket whose acknowledge/resolve request is in flight. */
  const pendingAction = ref<string | null>(null)

  const tickets = computed(() => [...active.value, ...resolved.value])
  const counts = computed<Record<HandoffStatus, number>>(() => ({
    open: active.value.filter((ticket) => ticket.status === 'open').length,
    acknowledged: active.value.filter((ticket) => ticket.status === 'acknowledged').length,
    resolved: resolved.value.length,
  }))
  const visible = computed(() => tickets.value.filter((ticket) => ticket.status === tab.value))
  const selected = computed(() => tickets.value.find((ticket) => ticket.id === selectedId.value) ?? null)

  async function loadThread({ quiet = false } = {}): Promise<void> {
    const ticket = selected.value
    if (!ticket) {
      thread.value = null
      threadError.value = null
      return
    }
    const conversationId = ticket.conversation_id
    if (!quiet) {
      loadingThread.value = true
      if (thread.value?.conversation.id !== conversationId) thread.value = null
    }
    try {
      const [conversation, page] = await Promise.all([
        conversationsApi.get(conversationId),
        conversationsApi.messages(conversationId, { limit: THREAD_LIMIT }),
      ])
      if (selected.value?.conversation_id === conversationId) {
        thread.value = { conversation, messages: page.items }
        threadError.value = null
      }
    } catch (failure) {
      if (selected.value?.conversation_id === conversationId) threadError.value = toApiError(failure)
    } finally {
      if (!quiet) loadingThread.value = false
    }
  }

  /** Keeps the selection on the visible tab, then refreshes its conversation. */
  async function syncSelection({ quiet = false } = {}): Promise<void> {
    if (!visible.value.some((ticket) => ticket.id === selectedId.value)) {
      selectedId.value = visible.value[0]?.id ?? null
      quiet = false
    }
    await loadThread({ quiet })
  }

  async function refresh(): Promise<void> {
    try {
      const [open, done] = await Promise.all([
        merchantApi.handoffs({ status: ['open', 'acknowledged'], limit: ACTIVE_LIMIT }),
        merchantApi.handoffs({ status: ['resolved'], limit: RESOLVED_LIMIT }),
      ])
      active.value = open.items
      resolved.value = done.items
      error.value = null
      const first = !loaded.value
      loaded.value = true
      await syncSelection({ quiet: !first })
    } catch (failure) {
      error.value = toApiError(failure)
    }
  }

  async function select(id: string): Promise<void> {
    if (selectedId.value === id) return
    selectedId.value = id
    await loadThread()
  }

  async function setTab(next: HandoffStatus): Promise<void> {
    tab.value = next
    await syncSelection()
  }

  function store(ticket: HandoffTicket): void {
    active.value = active.value.filter((item) => item.id !== ticket.id)
    resolved.value = resolved.value.filter((item) => item.id !== ticket.id)
    if (ticket.status === 'resolved') resolved.value = [ticket, ...resolved.value]
    else active.value = [ticket, ...active.value]
  }

  async function act(id: string, action: (ticketId: string) => Promise<HandoffTicket>): Promise<HandoffTicket> {
    pendingAction.value = id
    try {
      const ticket = await action(id)
      store(ticket)
      // Follow the ticket to its new tab, as the merchant is working on it.
      tab.value = ticket.status
      selectedId.value = ticket.id
      await loadThread({ quiet: true })
      return ticket
    } catch (failure) {
      const apiError = toApiError(failure)
      // Someone else changed the ticket meanwhile: show the current state.
      if (apiError.code === 'INVALID_STATE' || apiError.code === 'HANDOFF_NOT_FOUND') await refresh()
      throw apiError
    } finally {
      pendingAction.value = null
    }
  }

  const acknowledge = (id: string) => act(id, merchantApi.acknowledge)
  const resolve = (id: string) => act(id, merchantApi.resolve)

  return {
    tickets,
    tab,
    selectedId,
    thread,
    loaded,
    error,
    threadError,
    loadingThread,
    pendingAction,
    counts,
    visible,
    selected,
    refresh,
    select,
    setTab,
    acknowledge,
    resolve,
  }
})
