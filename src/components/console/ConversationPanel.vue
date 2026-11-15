<script setup lang="ts">
import { Bot, CircleCheck, Hand, Sparkles, TriangleAlert, UserRound, Wrench } from 'lucide-vue-next'
import { NButton, NCard, NEmpty, NIcon, NScrollbar, NTag, NTooltip } from 'naive-ui'
import { computed } from 'vue'

import type { HandoffTicket } from '../../api/types'
import type { InboxThread } from '../../fixtures/demo'
import { CONVERSATION_STATUS_META, toolLabel } from '../../labels'
import { clockTime, fromNow } from '../../utils/time'

const props = defineProps<{ ticket: HandoffTicket | null; thread: InboxThread | null }>()
const emit = defineEmits<{ acknowledge: [id: string]; resolve: [id: string] }>()

const statusMeta = computed(() =>
  props.thread ? CONVERSATION_STATUS_META[props.thread.conversation.status] : null,
)
const shortId = computed(() => props.thread?.conversation.id.replace(/^conv-/, '#') ?? '')
const latestWorkflow = computed(() => {
  const messages = props.thread?.messages ?? []
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const workflow = messages[index]?.workflow
    if (workflow) return workflow
  }
  return null
})
const sourceLabel = computed(() =>
  latestWorkflow.value?.analysis_source === 'heuristic' ? '规则兜底' : '模型分析',
)
</script>

<template>
  <NCard v-if="ticket && thread" :bordered="false" class="panel" content-class="panel-content">
    <header class="panel-head">
      <div class="panel-title">
        <div class="title-line">
          <h2>会话 <span class="mono">{{ shortId }}</span></h2>
          <NTag v-if="statusMeta" size="small" :bordered="false" :type="statusMeta.type">{{ statusMeta.label }}</NTag>
        </div>
        <p>{{ ticket.language_label }} · {{ ticket.intent_label }} · {{ fromNow(ticket.created_at) }}转入</p>
      </div>
      <div class="panel-actions">
        <NButton v-if="ticket.status === 'open'" type="primary" @click="emit('acknowledge', ticket.id)">
          <template #icon><NIcon :component="Hand" /></template>
          确认接管
        </NButton>
        <NButton
          v-if="ticket.status !== 'resolved'"
          :type="ticket.status === 'acknowledged' ? 'primary' : 'default'"
          :secondary="ticket.status !== 'acknowledged'"
          @click="emit('resolve', ticket.id)"
        >
          <template #icon><NIcon :component="CircleCheck" /></template>
          标记解决
        </NButton>
      </div>
    </header>

    <NScrollbar class="panel-scroll">
      <div class="panel-body">
        <section class="insights">
          <div class="insight insight--summary">
            <div class="insight-label">
              <NIcon :size="15" :component="Sparkles" aria-hidden="true" />
              中文摘要
              <span class="insight-source">{{ sourceLabel }}</span>
            </div>
            <p>{{ latestWorkflow?.merchant_summary || '暂无摘要' }}</p>
          </div>
          <div class="insight insight--reason">
            <div class="insight-label">
              <NIcon :size="15" :component="TriangleAlert" aria-hidden="true" />
              转人工原因
            </div>
            <p class="reason">{{ ticket.reason_text }}</p>
            <p v-if="ticket.issue_summary" class="issue">{{ ticket.issue_summary }}</p>
          </div>
        </section>

        <section class="transcript" aria-label="对话记录">
          <h3>对话记录</h3>
          <div
            v-for="message in thread.messages"
            :key="message.id"
            class="turn"
            :class="message.role === 'user' ? 'turn--customer' : 'turn--agent'"
          >
            <div class="turn-avatar" aria-hidden="true">
              <NIcon :size="15" :component="message.role === 'user' ? UserRound : Bot" />
            </div>
            <div class="turn-body">
              <div class="turn-who">
                <strong>{{ message.role === 'user' ? '客户' : 'Agent' }}</strong>
                <time :datetime="message.created_at">{{ clockTime(message.created_at, 'zh-CN') }}</time>
              </div>
              <div class="turn-text">{{ message.content }}</div>
              <div v-if="message.workflow?.trace.length" class="trace">
                <NTooltip v-for="step in message.workflow.trace" :key="step.call_id">
                  <template #trigger>
                    <span class="trace-chip" :class="{ 'trace-chip--fail': !step.ok }">
                      <NIcon :size="12" :component="Wrench" aria-hidden="true" />
                      {{ toolLabel(step.name) }}
                      <em>{{ step.latency_ms }}ms</em>
                    </span>
                  </template>
                  <span class="mono">{{ step.name }}({{ JSON.stringify(step.args) }})</span>
                </NTooltip>
              </div>
            </div>
          </div>
        </section>
      </div>
    </NScrollbar>
  </NCard>

  <NCard v-else :bordered="false" class="panel panel--empty">
    <NEmpty description="在左侧选择一张工单查看会话" />
  </NCard>
</template>

<style scoped>
.panel {
  display: flex;
  height: 100%;
  flex-direction: column;
  box-shadow: var(--shadow-card);
}

.panel :deep(.panel-content) {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  padding: 0;
}

.panel--empty {
  align-items: center;
  justify-content: center;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 22px;
  border-bottom: 1px solid var(--line);
}

.title-line {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-line h2 {
  margin: 0;
  color: var(--text-strong);
  font-size: 16px;
}

.title-line .mono {
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 500;
}

.panel-title p {
  margin: 4px 0 0;
  color: var(--text-muted);
  font-size: 12.5px;
}

.panel-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
}

.panel-scroll {
  min-height: 0;
  flex: 1;
}

.panel-body {
  display: flex;
  flex-direction: column;
  gap: 22px;
  padding: 20px 22px 26px;
}

.insights {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: 14px;
}

.insight {
  padding: 14px 16px;
  border-radius: 14px;
}

.insight--summary {
  border: 1px solid rgba(15, 118, 110, 0.16);
  background: linear-gradient(135deg, var(--brand-soft) 0%, transparent 100%);
}

.insight--reason {
  border: 1px solid rgba(217, 119, 6, 0.18);
  background: var(--warn-soft);
}

.insight-label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  color: var(--text-strong);
  font-size: 12.5px;
  font-weight: 600;
}

.insight--summary .insight-label :deep(.n-icon) {
  color: var(--brand);
}

.insight--reason .insight-label :deep(.n-icon) {
  color: var(--warn);
}

.insight-source {
  margin-left: auto;
  padding: 1px 8px;
  border-radius: 999px;
  color: var(--brand);
  background: var(--brand-soft);
  font-size: 11px;
  font-weight: 500;
}

.insight p {
  margin: 0;
  color: var(--text);
  font-size: 13.5px;
  line-height: 1.7;
}

.insight .reason {
  color: var(--text-strong);
  font-weight: 600;
}

.insight .issue {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 12.5px;
}

.transcript h3 {
  margin: 0 0 14px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.turn {
  display: flex;
  gap: 12px;
  padding: 12px 0;
}

.turn + .turn {
  border-top: 1px dashed var(--line);
}

.turn-avatar {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  place-items: center;
  border-radius: 50%;
}

.turn--customer .turn-avatar {
  color: var(--info);
  background: var(--info-soft);
}

.turn--agent .turn-avatar {
  color: var(--brand);
  background: var(--brand-soft);
}

.turn-body {
  min-width: 0;
  flex: 1;
}

.turn-who {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12.5px;
}

.turn-who strong {
  color: var(--text-strong);
}

.turn-who time {
  color: var(--text-faint);
  font-size: 11.5px;
}

.turn-text {
  color: var(--text);
  font-size: 13.5px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.trace {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.trace-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--text);
  background: var(--surface-muted);
  cursor: default;
  font-size: 11.5px;
}

.trace-chip em {
  color: var(--text-faint);
  font-style: normal;
  font-variant-numeric: tabular-nums;
}

.trace-chip--fail {
  border-color: rgba(220, 38, 38, 0.3);
  color: #b91c1c;
}

@media (max-width: 1180px) {
  .insights {
    grid-template-columns: 1fr;
  }
}
</style>
