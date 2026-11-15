<script setup lang="ts">
import { Headset } from 'lucide-vue-next'
import { NIcon } from 'naive-ui'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import type { HistoryMessage, HistoryRole, Language, Product } from '../../api/types'
import ChatComposer from '../../components/chat/ChatComposer.vue'
import ChatHeader from '../../components/chat/ChatHeader.vue'
import ChatMessage from '../../components/chat/ChatMessage.vue'
import TypingIndicator from '../../components/chat/TypingIndicator.vue'
import WelcomePanel from '../../components/chat/WelcomePanel.vue'
import { customerChat, demoProducts } from '../../fixtures/demo'
import { customerStrings } from '../../i18n/customer'

// Prototype only: replies are simulated locally. Phase V2 swaps this for the
// conversation store, the mock backend and real SSE streaming.
type Topic = 'shipping' | 'lamp' | 'handoff' | 'generic'

const REPLIES: Record<Language, Record<Topic, string>> = {
  'en-US': {
    shipping: 'Yes! The Nebula ANC Headphones Pro ships to Spain in 5–8 business days and costs USD 39.00.',
    lamp: 'The Luma Portable Ambient Lamp is USD 24.00 and ships in 6–10 business days. It runs for 18 hours on one charge.',
    handoff: "I'm sorry to hear that. I've logged your request, and a member of our team will follow up here shortly.",
    generic: 'Happy to help! Which product are you interested in, and where should it be delivered?',
  },
  'es-ES': {
    shipping: '¡Sí! Los Nebula ANC Headphones Pro se envían a España en 5–8 días hábiles y cuestan 39,00 USD.',
    lamp: 'La Luma Portable Ambient Lamp cuesta 24,00 USD y se envía en 6–10 días hábiles. Tiene 18 horas de autonomía.',
    handoff: 'Siento mucho lo ocurrido. He registrado tu solicitud y una persona de nuestro equipo te responderá aquí en breve.',
    generic: '¡Con gusto te ayudo! ¿Qué producto te interesa y a qué país debemos enviarlo?',
  },
  'zh-CN': {
    shipping: '可以的！星云降噪耳机 Pro 发往西班牙大约 5–8 个工作日，售价 39 美元。',
    lamp: '光屿便携氛围灯售价 24 美元，6–10 个工作日送达，充满电可以用 18 小时。',
    handoff: '非常抱歉给你带来不便！我已经登记了你的诉求，商家会尽快在这里联系你。',
    generic: '很乐意帮忙！你想了解哪款商品？需要寄到哪个国家？',
  },
}

const TOPIC_PRODUCTS: Record<Topic, Product[]> = {
  shipping: [demoProducts.headset],
  lamp: [demoProducts.lamp],
  handoff: [],
  generic: [],
}

function topicOf(text: string): Topic {
  if (/won.?t turn on|broken|damaged|refund|\breturn\b|no encienden?|roto|devol|坏|无法开机|退货|退款/i.test(text)) {
    return 'handoff'
  }
  if (/\blamp\b|lámpara|氛围灯/i.test(text)) return 'lamp'
  if (/\bship|deliver|envi|envío|españa|spain|西班牙|发往|物流/i.test(text)) return 'shipping'
  return 'generic'
}

const locale = ref<Language>('en-US')
const t = computed(() => customerStrings[locale.value])
const messages = ref<HistoryMessage[]>(customerChat.map((message) => ({ ...message })))
const typing = ref(false)
const streamingId = ref<string | null>(null)
const handedOff = ref(false)
const scroller = ref<HTMLElement | null>(null)

let seq = messages.value.length
const timers = new Set<number>()

function later(callback: () => void, ms: number) {
  const id = window.setTimeout(() => {
    timers.delete(id)
    callback()
  }, ms)
  timers.add(id)
}

function makeMessage(role: HistoryRole, content: string, products: Product[] = []): HistoryMessage {
  seq += 1
  const id = `local-${seq}`
  return {
    id,
    seq,
    role,
    content,
    created_at: new Date().toISOString(),
    client_message_id: null,
    workflow:
      role === 'assistant' && products.length
        ? ({ matched_products: products } as unknown as HistoryMessage['workflow'])
        : null,
  }
}

async function scrollToEnd(smooth = true) {
  await nextTick()
  const el = scroller.value
  if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
}

function send(text: string) {
  if (typing.value || streamingId.value) return
  messages.value.push(makeMessage('user', text))
  typing.value = true
  void scrollToEnd()

  const topic = topicOf(text)
  const reply = REPLIES[locale.value][topic]
  later(() => {
    typing.value = false
    messages.value.push(makeMessage('assistant', '', TOPIC_PRODUCTS[topic]))
    const target = messages.value[messages.value.length - 1]
    if (!target) return
    streamingId.value = target.id
    let shown = 0
    const tick = () => {
      shown = Math.min(reply.length, shown + 3)
      target.content = reply.slice(0, shown)
      void scrollToEnd(false)
      if (shown < reply.length) {
        later(tick, 18)
        return
      }
      streamingId.value = null
      if (topic === 'handoff') handedOff.value = true
      void scrollToEnd()
    }
    tick()
  }, 850)
}

function reset() {
  timers.forEach((id) => window.clearTimeout(id))
  timers.clear()
  messages.value = []
  typing.value = false
  streamingId.value = null
  handedOff.value = false
}

onMounted(() => void scrollToEnd(false))
onBeforeUnmount(() => timers.forEach((id) => window.clearTimeout(id)))
</script>

<template>
  <div class="chat-page">
    <section class="chat-shell" aria-label="Customer support chat">
      <ChatHeader
        v-model:locale="locale"
        :strings="t"
        :handed-off="handedOff"
        @handoff="handedOff = true"
        @reset="reset"
      />

      <Transition name="slide">
        <div v-if="handedOff" class="handoff-banner" role="status">
          <NIcon :size="18" :component="Headset" aria-hidden="true" />
          <div>
            <strong>{{ t.handoffTitle }}</strong>
            <span>{{ t.handoffBody }}</span>
          </div>
        </div>
      </Transition>

      <div ref="scroller" class="chat-body">
        <WelcomePanel v-if="!messages.length" :strings="t" @pick="send" />
        <ChatMessage
          v-for="message in messages"
          :key="message.id"
          :message="message"
          :locale="locale"
          :strings="t"
          :streaming="message.id === streamingId"
        />
        <TypingIndicator v-if="typing" :label="t.typing" />
      </div>

      <ChatComposer :strings="t" :disabled="typing || Boolean(streamingId)" @send="send" />
    </section>
    <p class="powered">{{ t.poweredBy }}</p>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 28px 16px 18px;
  background:
    radial-gradient(900px 520px at 10% -10%, rgba(45, 212, 191, 0.26), transparent 62%),
    radial-gradient(760px 480px at 108% 2%, rgba(99, 102, 241, 0.16), transparent 58%),
    linear-gradient(180deg, #f8fafc 0%, #edf3f5 100%);
}

.chat-shell {
  display: flex;
  width: min(780px, 100%);
  height: min(880px, calc(100vh - 92px));
  min-height: 520px;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 26px;
  background: var(--surface);
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 28px 70px -30px rgba(15, 23, 42, 0.32);
}

.handoff-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid rgba(217, 119, 6, 0.18);
  color: #92400e;
  background: linear-gradient(90deg, #fffbeb 0%, #fff7ed 100%);
}

.handoff-banner > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12.5px;
  line-height: 1.55;
}

.handoff-banner strong {
  font-size: 13.5px;
}

.chat-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 18px;
  overflow-y: auto;
  padding: 26px 22px;
  scroll-behavior: smooth;
  scrollbar-color: rgba(100, 116, 139, 0.35) transparent;
  scrollbar-width: thin;
}

.powered {
  margin: 14px 0 0;
  color: var(--text-faint);
  font-size: 12px;
  letter-spacing: 0.01em;
}

.slide-enter-active,
.slide-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 600px) {
  .chat-page {
    padding: 0;
  }

  .chat-shell {
    height: 100vh;
    min-height: 0;
    border: 0;
    border-radius: 0;
  }

  .powered {
    display: none;
  }
}
</style>
