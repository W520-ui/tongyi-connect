import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type { ConversationStatus, HandoffStatus, HandoffTicket } from '../api/types'
import { inboxThreads, tickets as fixtureTickets, type InboxThread } from '../fixtures/demo'

// Prototype store backed by fixtures; phase V2 loads the same shapes from
// GET /handoffs, GET /conversations/{id} and GET /conversations/{id}/messages.
export const useInboxStore = defineStore('inbox', () => {
  const tickets = ref<HandoffTicket[]>(structuredClone(fixtureTickets))
  const threads = ref<Record<string, InboxThread>>(structuredClone(inboxThreads))
  const tab = ref<HandoffStatus>('open')
  const selectedId = ref<string | null>(tickets.value.find((t) => t.status === 'open')?.id ?? null)

  const counts = computed<Record<HandoffStatus, number>>(() => ({
    open: tickets.value.filter((t) => t.status === 'open').length,
    acknowledged: tickets.value.filter((t) => t.status === 'acknowledged').length,
    resolved: tickets.value.filter((t) => t.status === 'resolved').length,
  }))
  const visible = computed(() => tickets.value.filter((t) => t.status === tab.value))
  const selected = computed(() => tickets.value.find((t) => t.id === selectedId.value) ?? null)
  const thread = computed(() => (selected.value ? (threads.value[selected.value.conversation_id] ?? null) : null))

  function select(id: string) {
    selectedId.value = id
  }

  function setTab(next: HandoffStatus) {
    tab.value = next
    selectedId.value = visible.value[0]?.id ?? null
  }

  function moveConversation(conversationId: string, status: ConversationStatus) {
    const current = threads.value[conversationId]
    if (current) current.conversation.status = status
  }

  function acknowledge(id: string) {
    const ticket = tickets.value.find((t) => t.id === id)
    if (!ticket || ticket.status !== 'open') return false
    ticket.status = 'acknowledged'
    ticket.acknowledged_at = new Date().toISOString()
    moveConversation(ticket.conversation_id, 'human_active')
    tab.value = 'acknowledged'
    return true
  }

  function resolve(id: string) {
    const ticket = tickets.value.find((t) => t.id === id)
    if (!ticket || ticket.status === 'resolved') return false
    ticket.status = 'resolved'
    ticket.resolved_at = new Date().toISOString()
    moveConversation(ticket.conversation_id, 'resolved')
    tab.value = 'resolved'
    return true
  }

  return { tickets, tab, selectedId, counts, visible, selected, thread, select, setTab, acknowledge, resolve }
})
