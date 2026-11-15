<script setup lang="ts">
import { Headset, TriangleAlert, Wrench } from 'lucide-vue-next'
import { NCard, NEmpty, NIcon, NScrollbar, NTab, NTabs, NTag } from 'naive-ui'
import type { Component } from 'vue'

import type { HandoffReasonCode, HandoffStatus, HandoffTicket } from '../../api/types'
import { HANDOFF_REASON_LABELS } from '../../labels'
import { fromNow } from '../../utils/time'

defineProps<{
  tickets: HandoffTicket[]
  selectedId: string | null
  tab: HandoffStatus
  counts: Record<HandoffStatus, number>
}>()
const emit = defineEmits<{ 'update:tab': [value: HandoffStatus]; select: [id: string] }>()

const REASON_ICONS: Record<HandoffReasonCode, Component> = {
  after_sales: Wrench,
  user_request: Headset,
  guardrail: TriangleAlert,
}

function onTab(value: string | number) {
  emit('update:tab', value as HandoffStatus)
}
</script>

<template>
  <NCard :bordered="false" class="tickets" content-class="tickets-content">
    <div class="tickets-head">
      <NTabs type="segment" size="small" :value="tab" @update:value="onTab">
        <NTab name="open">待接管 <span class="count">{{ counts.open }}</span></NTab>
        <NTab name="acknowledged">处理中 <span class="count">{{ counts.acknowledged }}</span></NTab>
        <NTab name="resolved">已解决 <span class="count">{{ counts.resolved }}</span></NTab>
      </NTabs>
    </div>
    <NScrollbar class="tickets-scroll">
      <div class="tickets-list">
        <button
          v-for="ticket in tickets"
          :key="ticket.id"
          type="button"
          class="ticket"
          :class="[`ticket--${ticket.status}`, { 'ticket--active': ticket.id === selectedId }]"
          @click="emit('select', ticket.id)"
        >
          <div class="ticket-top">
            <span class="lang">{{ ticket.language_label }}</span>
            <NTag size="small" :bordered="false" :type="ticket.reason_code === 'after_sales' ? 'warning' : 'info'">
              {{ ticket.intent_label }}
            </NTag>
            <time :datetime="ticket.created_at">{{ fromNow(ticket.created_at) }}</time>
          </div>
          <p class="ticket-message">{{ ticket.customer_message }}</p>
          <div class="ticket-meta">
            <NIcon :size="13" :component="REASON_ICONS[ticket.reason_code]" aria-hidden="true" />
            <span class="reason">{{ HANDOFF_REASON_LABELS[ticket.reason_code] }}</span>
            <template v-if="ticket.issue_summary">
              <span class="dot" aria-hidden="true">·</span>
              <span class="issue">{{ ticket.issue_summary }}</span>
            </template>
          </div>
        </button>
        <NEmpty v-if="!tickets.length" class="empty" description="这里暂时没有工单" />
      </div>
    </NScrollbar>
  </NCard>
</template>

<style scoped>
.tickets {
  display: flex;
  height: 100%;
  flex-direction: column;
  box-shadow: var(--shadow-card);
}

.tickets :deep(.tickets-content) {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  padding: 0;
}

.tickets-head {
  padding: 14px 14px 10px;
  border-bottom: 1px solid var(--line);
}

.count {
  margin-left: 4px;
  color: var(--text-faint);
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
}

.tickets-scroll {
  min-height: 0;
  flex: 1;
}

.tickets-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
}

.ticket {
  position: relative;
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 7px;
  padding: 12px 14px 12px 16px;
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: 14px;
  color: inherit;
  background: transparent;
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.ticket::before {
  position: absolute;
  top: 12px;
  bottom: 12px;
  left: 0;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--line-strong);
  content: '';
}

.ticket--open::before {
  background: #f59e0b;
}

.ticket--acknowledged::before {
  background: #6366f1;
}

.ticket--resolved::before {
  background: #22c55e;
}

.ticket:hover {
  background: var(--surface-muted);
}

.ticket--active,
.ticket--active:hover {
  border-color: rgba(15, 118, 110, 0.22);
  background: var(--brand-soft);
}

.ticket:focus-visible {
  outline: 3px solid var(--brand-ring);
  outline-offset: 1px;
}

.ticket-top {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.lang {
  padding: 1px 8px;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--text);
  font-weight: 600;
}

.ticket-top time {
  margin-left: auto;
  color: var(--text-faint);
}

.ticket-message {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--text-strong);
  font-size: 13.5px;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.ticket-meta {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 5px;
  color: var(--text-muted);
  font-size: 12px;
}

.ticket-meta .reason,
.ticket-meta .dot {
  flex: 0 0 auto;
  white-space: nowrap;
}

.ticket-meta .issue {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ticket-meta :deep(.n-icon) {
  flex: 0 0 auto;
}

.empty {
  padding: 40px 0;
}
</style>
