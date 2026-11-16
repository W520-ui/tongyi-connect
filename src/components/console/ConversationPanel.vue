<script setup lang="ts">
import {
  Bot,
  CircleAlert,
  CircleCheck,
  Hand,
  Headset,
  LoaderCircle,
  Sparkles,
  TriangleAlert,
  UserRound,
  Wrench,
} from '@lucide/vue'
import { computed } from 'vue'

import type { ApiError } from '@/api/errors'
import type { HandoffTicket } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { CONVERSATION_STATUS_META, TONE_CLASSES, toolLabel } from '@/labels'
import type { InboxThread } from '@/stores/inbox'
import { clockTime, fromNow } from '@/utils/time'

const props = defineProps<{
  ticket: HandoffTicket | null
  thread: InboxThread | null
  loading?: boolean
  error?: ApiError | null
  /** True while an acknowledge/resolve request for this ticket is in flight. */
  busy?: boolean
}>()
const emit = defineEmits<{ acknowledge: [id: string]; resolve: [id: string]; reload: [] }>()

const statusMeta = computed(() => (props.thread ? CONVERSATION_STATUS_META[props.thread.conversation.status] : null))
const shortId = computed(() => (props.thread ? `#${props.thread.conversation.id.slice(0, 8)}` : ''))
const latestWorkflow = computed(() => {
  const messages = props.thread?.messages ?? []
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const workflow = messages[index]?.workflow
    if (workflow) return workflow
  }
  return null
})
const sourceLabel = computed(() => (latestWorkflow.value?.analysis_source === 'heuristic' ? '规则兜底' : '模型分析'))

function speaker(message: InboxThread['messages'][number]): string {
  if (message.role === 'user') return '客户'
  if (message.role === 'human_agent') return '商家'
  return message.workflow?.source === 'paused-for-human' ? '接管提示' : 'Agent'
}
</script>

<template>
  <section v-if="ticket && thread" class="flex min-h-0 flex-col overflow-hidden rounded-xl border bg-card">
    <header class="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3.5">
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <h2 class="text-base font-semibold">
            会话 <span class="font-mono text-sm font-normal text-muted-foreground">{{ shortId }}</span>
          </h2>
          <Badge v-if="statusMeta" :class="TONE_CLASSES[statusMeta.tone]">{{ statusMeta.label }}</Badge>
        </div>
        <p class="mt-0.5 text-xs text-muted-foreground">
          {{ ticket.language_label }} · {{ ticket.intent_label }} · {{ fromNow(ticket.created_at) }}转入
        </p>
      </div>
      <div class="flex items-center gap-2">
        <Button v-if="ticket.status === 'open'" size="sm" :disabled="busy" @click="emit('acknowledge', ticket.id)">
          <Hand />
          确认接管
        </Button>
        <Button
          v-if="ticket.status !== 'resolved'"
          size="sm"
          :variant="ticket.status === 'acknowledged' ? 'default' : 'outline'"
          :disabled="busy"
          @click="emit('resolve', ticket.id)"
        >
          <CircleCheck />
          标记解决
        </Button>
      </div>
    </header>

    <ScrollArea class="min-h-0 flex-1">
      <div class="flex flex-col gap-6 p-5">
        <div class="grid gap-3 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <div class="rounded-lg border p-4">
            <div class="mb-2 flex items-center gap-1.5 text-xs font-medium">
              <Sparkles class="size-3.5 text-brand" aria-hidden="true" />
              中文摘要
              <Badge class="ml-auto" :class="TONE_CLASSES.brand">{{ sourceLabel }}</Badge>
            </div>
            <p class="text-sm leading-relaxed text-muted-foreground">
              {{ latestWorkflow?.merchant_summary || '暂无摘要' }}
            </p>
          </div>
          <div class="rounded-lg bg-warning-soft p-4">
            <div class="mb-2 flex items-center gap-1.5 text-xs font-medium text-warning">
              <TriangleAlert class="size-3.5" aria-hidden="true" />
              转人工原因
            </div>
            <p class="text-sm font-medium">{{ ticket.reason_text }}</p>
            <p v-if="ticket.issue_summary" class="mt-1.5 text-xs leading-relaxed text-muted-foreground">
              {{ ticket.issue_summary }}
            </p>
          </div>
        </div>

        <div>
          <h3 class="mb-1 text-xs font-medium text-muted-foreground">对话记录</h3>
          <ol class="divide-y divide-dashed">
            <li v-for="message in thread.messages" :key="message.id" class="flex gap-3 py-3.5">
              <div
                class="grid size-7 shrink-0 place-items-center rounded-full"
                :class="message.role === 'user' ? 'bg-info-soft text-info' : 'border bg-background text-muted-foreground'"
                aria-hidden="true"
              >
                <component
                  :is="message.role === 'user' ? UserRound : message.role === 'human_agent' ? Headset : Bot"
                  class="size-3.5"
                />
              </div>
              <div class="min-w-0 flex-1">
                <div class="mb-1 flex items-baseline gap-2 text-xs">
                  <span class="font-medium">{{ speaker(message) }}</span>
                  <time class="text-muted-foreground" :datetime="message.created_at">
                    {{ clockTime(message.created_at, 'zh-CN') }}
                  </time>
                </div>
                <p class="text-sm leading-relaxed whitespace-pre-wrap">{{ message.content }}</p>
                <div v-if="message.workflow?.trace.length" class="mt-2 flex flex-wrap gap-1.5">
                  <Tooltip v-for="step in message.workflow.trace" :key="step.call_id">
                    <TooltipTrigger as-child>
                      <span
                        tabindex="0"
                        class="inline-flex cursor-default items-center gap-1 rounded-md border bg-muted/50 px-2 py-0.5 text-xs text-muted-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                      >
                        <Wrench class="size-3" aria-hidden="true" />
                        {{ toolLabel(step.name) }}
                        <span class="tabular-nums">{{ Math.round(step.latency_ms) }}ms</span>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      <span class="font-mono">{{ step.name }}({{ JSON.stringify(step.args) }})</span>
                    </TooltipContent>
                  </Tooltip>
                </div>
              </div>
            </li>
          </ol>
          <p v-if="!thread.messages.length" class="py-6 text-sm text-muted-foreground">这个会话还没有消息</p>
        </div>
      </div>
    </ScrollArea>
  </section>

  <section
    v-else-if="ticket && error"
    class="flex flex-col items-center justify-center gap-3 rounded-xl border bg-card p-12 text-center text-sm"
    role="alert"
  >
    <CircleAlert class="size-5 text-muted-foreground" aria-hidden="true" />
    <p class="text-muted-foreground">会话加载失败：{{ error.message }}</p>
    <Button variant="outline" size="sm" @click="emit('reload')">重新加载</Button>
  </section>

  <section
    v-else-if="ticket && loading"
    class="flex items-center justify-center gap-2 rounded-xl border bg-card p-12 text-sm text-muted-foreground"
    role="status"
  >
    <LoaderCircle class="size-4 animate-spin" aria-hidden="true" />
    正在加载会话…
  </section>

  <section v-else class="grid place-items-center rounded-xl border bg-card p-12 text-sm text-muted-foreground">
    在左侧选择一张工单查看会话
  </section>
</template>
