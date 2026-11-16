<script setup lang="ts">
import { Headset, TriangleAlert, Wrench } from '@lucide/vue'
import type { Component } from 'vue'

import type { HandoffReasonCode, HandoffStatus, HandoffTicket } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { HANDOFF_REASON_LABELS, HANDOFF_STATUS_META, TONE_CLASSES } from '@/labels'
import { cn } from '@/lib/utils'
import { fromNow } from '@/utils/time'

defineProps<{
  tickets: HandoffTicket[]
  selectedId: string | null
  tab: HandoffStatus
  counts: Record<HandoffStatus, number>
  loading?: boolean
  /** The list could not be loaded at all (nothing to show yet). */
  failed?: boolean
}>()
const emit = defineEmits<{ 'update:tab': [value: HandoffStatus]; select: [id: string] }>()

const STATUSES: HandoffStatus[] = ['open', 'acknowledged', 'resolved']

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
  <section class="flex min-h-0 flex-col overflow-hidden rounded-xl border bg-card">
    <div class="border-b p-3">
      <Tabs :model-value="tab" @update:model-value="onTab">
        <TabsList class="w-full">
          <TabsTrigger v-for="status in STATUSES" :key="status" :value="status">
            {{ HANDOFF_STATUS_META[status].label }}
            <span class="text-xs text-muted-foreground tabular-nums">{{ counts[status] }}</span>
          </TabsTrigger>
        </TabsList>
      </Tabs>
    </div>

    <ScrollArea class="min-h-0 flex-1">
      <ul class="divide-y">
        <li v-for="ticket in tickets" :key="ticket.id">
          <button
            type="button"
            :class="
              cn(
                'relative flex w-full cursor-pointer flex-col gap-1.5 px-4 py-3.5 text-left transition-colors outline-none hover:bg-muted/60 focus-visible:bg-muted/60',
                ticket.id === selectedId && 'bg-muted hover:bg-muted',
              )
            "
            @click="emit('select', ticket.id)"
          >
            <span v-if="ticket.id === selectedId" class="absolute inset-y-0 left-0 w-0.5 bg-foreground" aria-hidden="true" />
            <div class="flex items-center gap-2 text-xs">
              <Badge variant="outline" class="font-normal">{{ ticket.language_label }}</Badge>
              <Badge :class="TONE_CLASSES[ticket.reason_code === 'after_sales' ? 'warning' : 'info']">
                {{ ticket.intent_label }}
              </Badge>
              <time class="ml-auto text-muted-foreground" :datetime="ticket.created_at">{{ fromNow(ticket.created_at) }}</time>
            </div>
            <p class="line-clamp-2 text-sm leading-relaxed">{{ ticket.customer_message }}</p>
            <div class="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
              <component :is="REASON_ICONS[ticket.reason_code]" class="size-3.5 shrink-0" aria-hidden="true" />
              <span class="shrink-0">{{ HANDOFF_REASON_LABELS[ticket.reason_code] }}</span>
              <template v-if="ticket.issue_summary">
                <span aria-hidden="true">·</span>
                <span class="truncate">{{ ticket.issue_summary }}</span>
              </template>
            </div>
          </button>
        </li>
      </ul>
      <p v-if="failed" class="px-4 py-12 text-center text-sm text-muted-foreground">工单列表暂时无法加载</p>
      <p v-else-if="loading" class="px-4 py-12 text-center text-sm text-muted-foreground" role="status">正在加载工单…</p>
      <p v-else-if="!tickets.length" class="px-4 py-12 text-center text-sm text-muted-foreground">这里暂时没有工单</p>
    </ScrollArea>
  </section>
</template>
