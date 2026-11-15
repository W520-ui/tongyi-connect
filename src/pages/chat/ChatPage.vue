<script setup lang="ts">
import { Headset } from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import type { HistoryMessage, HistoryRole, Language, Product } from '@/api/types'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatHeader from '@/components/chat/ChatHeader.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import TypingIndicator from '@/components/chat/TypingIndicator.vue'
import WelcomePanel from '@/components/chat/WelcomePanel.vue'
import { customerChat, demoProducts } from '@/fixtures/demo'
import { customerStrings } from '@/i18n/customer'

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
  return {
    id: `local-${seq}`,
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

function clearTimers() {
  timers.forEach((id) => window.clearTimeout(id))
  timers.clear()
}

function reset() {
  clearTimers()
  messages.value = []
  typing.value = false
  streamingId.value = null
  handedOff.value = false
}

onMounted(() => void scrollToEnd(false))
onBeforeUnmount(clearTimers)
</script>

<template>
  <div class="flex min-h-svh flex-col items-center justify-center bg-muted/50 sm:p-6">
    <section
      class="flex h-svh w-full max-w-3xl flex-col overflow-hidden bg-background sm:h-[min(860px,calc(100svh-6rem))] sm:rounded-2xl sm:border"
      aria-label="Customer support chat"
    >
      <ChatHeader
        v-model:locale="locale"
        :strings="t"
        :handed-off="handedOff"
        @handoff="handedOff = true"
        @reset="reset"
      />

      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="-translate-y-1 opacity-0"
        leave-active-class="transition duration-150 ease-in"
        leave-to-class="-translate-y-1 opacity-0"
      >
        <div v-if="handedOff" class="flex items-start gap-3 border-b bg-warning-soft px-5 py-3 text-warning" role="status">
          <Headset class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div class="text-[13px] leading-relaxed">
            <p class="font-medium">{{ t.handoffTitle }}</p>
            <p>{{ t.handoffBody }}</p>
          </div>
        </div>
      </Transition>

      <div ref="scroller" class="flex flex-1 flex-col gap-5 overflow-y-auto px-4 py-6 [scrollbar-width:thin] sm:px-6">
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
    <p class="mt-3 hidden text-xs text-muted-foreground sm:block">{{ t.poweredBy }}</p>
  </div>
</template>
