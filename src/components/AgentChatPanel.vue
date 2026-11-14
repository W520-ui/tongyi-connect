<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

import { ApiError } from '../services/http'
import { sendAgentMessage, type AgentWorkflowData } from '../services/agent'

const emit = defineEmits<{
  workflowComplete: [result: AgentWorkflowData]
}>()

interface ChatMessage {
  id: number
  role: 'assistant' | 'user' | 'error'
  content: string
  workflow?: AgentWorkflowData
}

const sessionToken = typeof crypto !== 'undefined' && 'randomUUID' in crypto
  ? crypto.randomUUID()
  : Math.random().toString(36).slice(2)
const sessionId = `demo-${sessionToken}`
const input = ref('')
const isSending = ref(false)
const errorMessage = ref('')
const scrollContainer = ref<HTMLElement | null>(null)
const messages = ref<ChatMessage[]>([
  {
    id: 1,
    role: 'assistant',
    content: '你好，我是通译智联的跨境服务智能体。你可以先发送一条咨询消息进行联调。',
  },
])

const quickPrompts = [
  '请用英文回复：星云降噪耳机 Pro 支持发往西班牙吗？',
  '请查询光屿便携氛围灯的价格和物流时效。',
  '客户说耳机收到后无法开机，帮我登记售后。',
]

const canSend = computed(() => input.value.trim().length > 0 && !isSending.value)

const agentStatus = computed(() => {
  const latestWorkflow = [...messages.value]
    .reverse()
    .find((message) => message.workflow)?.workflow

  if (latestWorkflow?.source?.startsWith('native')) {
    return 'Agent 已接入'
  }

  return 'Agent 待命'
})

function parseAgentData(data: unknown): AgentWorkflowData | null {
  if (data && typeof data === 'object' && 'reply' in data) {
    return data as AgentWorkflowData
  }

  return null
}

function stringifyAgentData(data: unknown): string {
  if (typeof data === 'string') {
    return data
  }

  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>
    for (const key of ['response', 'message', 'content', 'text', 'reply']) {
      if (typeof record[key] === 'string') {
        return record[key]
      }
    }
  }

  return data ? JSON.stringify(data, null, 2) : 'Agent 已返回空结果。'
}

async function scrollToLatest() {
  await nextTick()
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
  }
}

async function sendMessage() {
  const content = input.value.trim()
  if (!content || isSending.value) {
    return
  }

  errorMessage.value = ''
  messages.value.push({ id: Date.now(), role: 'user', content })
  input.value = ''
  isSending.value = true
  await scrollToLatest()

  try {
    const response = await sendAgentMessage<AgentWorkflowData>({
      message: content,
      session_id: sessionId,
      username: 'demo-user',
      locale: 'zh-CN',
      flags: { enable_streaming: false },
    })
    const workflow = parseAgentData(response.data)
    const assistantMessage = {
      id: Date.now() + 1,
      role: 'assistant',
      content: workflow?.reply ?? stringifyAgentData(response.data),
      workflow: workflow ?? undefined,
    } satisfies ChatMessage
    messages.value.push(assistantMessage)
    if (workflow) {
      emit('workflowComplete', workflow)
    }
  } catch (error) {
    const message = error instanceof ApiError ? error.message : 'Agent 请求失败，请检查后端服务与模型配置。'
    errorMessage.value = message
    messages.value.push({ id: Date.now() + 1, role: 'error', content: message })
  } finally {
    isSending.value = false
    await scrollToLatest()
  }
}

function useQuickPrompt(prompt: string) {
  input.value = prompt
  void sendMessage()
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void sendMessage()
  }
}
</script>

<template>
  <section class="agent-card" aria-labelledby="agent-title">
    <div class="agent-card__header">
      <div>
        <div class="agent-card__eyebrow">通译智联 Agent</div>
        <h3 id="agent-title">跨境咨询联调</h3>
      </div>
      <span class="agent-card__status"><span aria-hidden="true"></span>{{ agentStatus }}</span>
    </div>

    <div class="quick-prompts" aria-label="演示场景">
      <span>演示场景</span>
      <button v-for="prompt in quickPrompts" :key="prompt" type="button" @click="useQuickPrompt(prompt)">
        {{ prompt }}
      </button>
    </div>

    <div ref="scrollContainer" class="message-list" aria-live="polite">
      <div v-for="message in messages" :key="message.id" class="message-row" :class="`message-row--${message.role}`">
        <div>
          <div class="message-bubble">{{ message.content }}</div>
          <div v-if="message.workflow" class="workflow-result">
            <div class="workflow-result__topline">
              <span class="workflow-tag">{{ message.workflow.intent_label }}</span>
              <span class="workflow-tag workflow-tag--muted">{{ message.workflow.language_label }}</span>
              <span class="workflow-confidence">置信度 {{ Math.round(message.workflow.confidence * 100) }}%</span>
            </div>
            <div class="workflow-result__grid">
              <div>
                <span>命中商品</span>
                <strong>{{ message.workflow.matched_product }}</strong>
              </div>
              <div>
                <span>商家摘要</span>
                <strong>{{ message.workflow.merchant_summary }}</strong>
              </div>
            </div>
            <div class="workflow-steps">
              <span v-for="(step, index) in message.workflow.steps" :key="`${message.id}-step-${step}`">
                <i>{{ index + 1 }}</i>{{ step }}
              </span>
            </div>
            <div class="task-plan">
              <span>任务拆解</span>
              <strong v-for="(task, index) in message.workflow.task_plan" :key="`${message.id}-task-${task}`">
                {{ index + 1 }}. {{ task }}
              </strong>
            </div>
            <div v-if="message.workflow.needs_human" class="handoff-alert">
              <strong>需要人工接管</strong>{{ message.workflow.handoff_reason }}
            </div>
          </div>
        </div>
      </div>
      <div v-if="isSending" class="message-row message-row--assistant">
        <div class="message-bubble message-bubble--pending">智能体正在处理…</div>
      </div>
    </div>

    <p v-if="errorMessage" class="agent-error" role="alert">{{ errorMessage }}</p>

    <form class="composer" @submit.prevent="sendMessage">
      <textarea
        v-model="input"
        rows="2"
        maxlength="20000"
        placeholder="输入一条跨境咨询，例如：请用英文回复，这款产品支持发往西班牙吗？"
        :disabled="isSending"
        @keydown="handleKeydown"
      ></textarea>
      <button type="submit" :disabled="!canSend">{{ isSending ? '处理中…' : '发送' }}</button>
    </form>
    <div class="agent-card__footer">{{ agentStatus }} · Agent 自动规划服务流程 · 会话 {{ sessionId }}</div>
  </section>
</template>

<style scoped>
.agent-card {
  display: flex;
  min-height: 560px;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 20px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.agent-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px;
  border-bottom: 1px solid var(--color-border);
}

.agent-card__eyebrow {
  margin-bottom: 6px;
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

h3 {
  margin: 0;
  color: var(--color-text);
  font-size: 20px;
}

.agent-card__status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #027a48;
  font-size: 12px;
  white-space: nowrap;
}

.agent-card__status span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #12b76a;
}

.quick-prompts {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  padding: 12px 28px;
  border-bottom: 1px solid var(--color-border);
  background: #fafbff;
  white-space: nowrap;
}

.quick-prompts > span {
  flex: 0 0 auto;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.quick-prompts button {
  min-width: auto;
  height: auto;
  padding: 7px 10px;
  border: 1px solid #dbe4ff;
  border-radius: 999px;
  color: #3156b8;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
}

.quick-prompts button:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.message-list {
  display: flex;
  min-height: 300px;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 24px 28px;
  background: #fcfcfd;
}

.message-row {
  display: flex;
  max-width: min(720px, 88%);
}

.message-row--user {
  align-self: flex-end;
}

.message-row--assistant,
.message-row--error {
  align-self: flex-start;
}

.message-bubble {
  padding: 11px 14px;
  border-radius: 14px;
  color: var(--color-text);
  background: #fff;
  box-shadow: 0 1px 2px rgb(16 24 40 / 6%);
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-row--user .message-bubble {
  color: #fff;
  background: var(--color-primary);
}

.message-row--error .message-bubble {
  color: #b42318;
  background: #fef3f2;
}

.workflow-result {
  width: min(720px, 88vw);
  margin-top: 8px;
  padding: 12px;
  border: 1px solid #e4e7ec;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 1px 2px rgb(16 24 40 / 4%);
}

.workflow-result__topline,
.workflow-steps,
.workflow-result__grid {
  display: flex;
  align-items: center;
  gap: 8px;
}

.workflow-result__topline {
  flex-wrap: wrap;
}

.workflow-tag {
  padding: 4px 8px;
  border-radius: 999px;
  color: #175cd3;
  background: #eff8ff;
  font-size: 11px;
  font-weight: 700;
}

.workflow-tag--muted {
  color: #475467;
  background: #f2f4f7;
}

.workflow-confidence {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.workflow-result__grid {
  align-items: stretch;
  margin-top: 10px;
}

.workflow-result__grid > div {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 4px;
  padding: 9px;
  border-radius: 8px;
  background: #f8fafc;
}

.workflow-result__grid span {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.workflow-result__grid strong {
  color: var(--color-text);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
}

.workflow-steps {
  align-items: flex-start;
  flex-wrap: wrap;
  margin-top: 10px;
}

.workflow-steps span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #475467;
  font-size: 11px;
}

.workflow-steps i {
  display: grid;
  width: 18px;
  height: 18px;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: #2563eb;
  font-style: normal;
  font-size: 10px;
  font-weight: 700;
}

.task-plan {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding-top: 9px;
  border-top: 1px dashed #e4e7ec;
}

.task-plan > span {
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 700;
}

.task-plan strong {
  padding: 4px 7px;
  border-radius: 5px;
  color: #344054;
  background: #f2f4f7;
  font-size: 10px;
  font-weight: 500;
}

.handoff-alert {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 11px;
  line-height: 1.6;
  color: #b54708;
  background: #fffaeb;
}

.handoff-alert strong {
  margin-right: 6px;
}

.message-bubble--pending {
  color: var(--color-text-secondary);
}

.agent-error {
  margin: 0;
  padding: 0 28px 12px;
  color: #b42318;
  font-size: 12px;
}

.composer {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 16px 28px;
  border-top: 1px solid var(--color-border);
  background: #fff;
}

textarea {
  min-height: 50px;
  flex: 1;
  resize: vertical;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  color: var(--color-text);
  outline: none;
  line-height: 1.5;
}

textarea:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

button {
  min-width: 76px;
  height: 44px;
  padding: 0 16px;
  border: 0;
  border-radius: 10px;
  color: #fff;
  background: var(--color-primary);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.agent-card__footer {
  overflow: hidden;
  padding: 0 28px 16px;
  color: var(--color-text-secondary);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .agent-card__header,
  .composer,
  .message-list {
    padding-inline: 16px;
  }

  .agent-card__footer,
  .agent-error {
    padding-inline: 16px;
  }

  .agent-card__header {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }

  .quick-prompts {
    padding-inline: 16px;
  }

  .workflow-result {
    width: 88vw;
  }

  .workflow-result__grid {
    flex-direction: column;
  }

  .composer {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
