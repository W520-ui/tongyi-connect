<script setup lang="ts">
import { CircleAlert, Headset, LoaderCircle, UserRound, X } from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatHeader from '@/components/chat/ChatHeader.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import TypingIndicator from '@/components/chat/TypingIndicator.vue'
import WelcomePanel from '@/components/chat/WelcomePanel.vue'
import { Button } from '@/components/ui/button'
import { usePolling } from '@/composables/usePolling'
import { activityKind, customerErrorKind, customerStrings } from '@/i18n/customer'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()
const t = computed(() => customerStrings[chat.locale])
const scroller = ref<HTMLElement | null>(null)

const ready = computed(() => chat.phase === 'ready')
const staffJoined = computed(() => chat.status === 'human_active')
const activityText = computed(() => (chat.activity ? t.value.activity[activityKind(chat.activity)] : null))
const noticeText = computed(() => (chat.notice ? t.value.errors[customerErrorKind(chat.notice.code)] : null))
const lastEntry = computed(() => chat.entries[chat.entries.length - 1])

// While a person is involved, pick up the merchant acknowledging or resolving the chat.
usePolling(chat.refreshStatus, 10_000, () => ready.value && chat.handedOff)

function nearBottom(el: HTMLElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight < 120
}

async function scrollToEnd(smooth = true) {
  await nextTick()
  const el = scroller.value
  if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
}

// Anything that changes the height near the end: new messages, streamed text,
// product cards appearing after a reply, the handoff banner, the error notice.
const layout = computed(() =>
  [
    chat.entries.length,
    lastEntry.value?.content,
    lastEntry.value?.products.length,
    lastEntry.value?.status,
    chat.waiting,
    chat.streamingKey,
    chat.handedOff,
    chat.notice?.code,
  ].join('|'),
)
// Measured before Vue updates the DOM: was the customer reading the end?
let following = true
watch(layout, () => (following = !scroller.value || nearBottom(scroller.value)), { flush: 'pre' })
watch(
  layout,
  () => {
    // Their own message always scrolls into view; otherwise only follow the end.
    if (following || lastEntry.value?.role === 'user') void scrollToEnd(false)
  },
  { flush: 'post' },
)

async function loadOlder() {
  const el = scroller.value
  const before = el ? el.scrollHeight - el.scrollTop : 0
  await chat.loadOlder()
  await nextTick()
  // Keep the message the customer was looking at in place.
  if (el) el.scrollTop = el.scrollHeight - before
}

onMounted(async () => {
  await chat.connect()
  void scrollToEnd(false)
})
onBeforeUnmount(chat.cancel)
</script>

<template>
  <div class="flex min-h-svh flex-col items-center justify-center bg-muted/50 sm:p-6">
    <section
      class="flex h-svh w-full max-w-3xl flex-col overflow-hidden bg-background sm:h-[min(860px,calc(100svh-6rem))] sm:rounded-2xl sm:border"
      aria-label="Customer support chat"
    >
      <ChatHeader
        :locale="chat.locale"
        :strings="t"
        :handed-off="chat.handedOff"
        :disabled="!ready || chat.busy"
        @update:locale="chat.setLocale"
        @handoff="chat.requestHandoff"
        @reset="chat.startNewChat"
      />

      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="-translate-y-1 opacity-0"
        leave-active-class="transition duration-150 ease-in"
        leave-to-class="-translate-y-1 opacity-0"
      >
        <div
          v-if="chat.handedOff"
          class="flex items-start gap-3 border-b px-5 py-3"
          :class="staffJoined ? 'bg-info-soft text-info' : 'bg-warning-soft text-warning'"
          role="status"
        >
          <component :is="staffJoined ? UserRound : Headset" class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div class="text-[13px] leading-relaxed">
            <p class="font-medium">{{ staffJoined ? t.staffTitle : t.handoffTitle }}</p>
            <p>{{ staffJoined ? t.staffBody : t.handoffBody }}</p>
          </div>
        </div>
      </Transition>

      <div v-if="chat.phase === 'failed'" class="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
        <CircleAlert class="size-6 text-muted-foreground" aria-hidden="true" />
        <p class="font-medium">{{ t.connectFailed }}</p>
        <p v-if="chat.connectError" class="max-w-sm text-sm text-muted-foreground">
          {{ t.errors[customerErrorKind(chat.connectError.code)] }}
        </p>
        <Button variant="outline" size="sm" @click="chat.connect">{{ t.tryAgain }}</Button>
      </div>

      <div
        v-else-if="!ready"
        class="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground"
        role="status"
      >
        <LoaderCircle class="size-4 animate-spin" aria-hidden="true" />
        {{ t.connecting }}
      </div>

      <div
        v-else
        ref="scroller"
        class="flex flex-1 flex-col gap-5 overflow-y-auto px-4 py-6 [scrollbar-width:thin] sm:px-6"
        aria-live="polite"
      >
        <div v-if="chat.hasMore" class="flex justify-center">
          <Button variant="ghost" size="sm" :disabled="chat.loadingOlder" @click="loadOlder">
            <LoaderCircle v-if="chat.loadingOlder" class="animate-spin" />
            {{ t.earlier }}
          </Button>
        </div>
        <WelcomePanel v-if="!chat.entries.length && !chat.waiting" :strings="t" @pick="chat.send" />
        <ChatMessage
          v-for="entry in chat.entries"
          :key="entry.key"
          :entry="entry"
          :locale="chat.locale"
          :strings="t"
          :streaming="entry.key === chat.streamingKey"
          :busy="chat.busy"
          @retry="chat.retry"
        />
        <TypingIndicator v-if="chat.waiting" :label="t.typing" :activity="activityText" />
      </div>

      <div v-if="noticeText" class="flex items-start gap-2 border-t bg-muted/60 px-5 py-2.5 text-[13px]" role="alert">
        <CircleAlert class="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
        <p class="flex-1 text-muted-foreground">{{ noticeText }}</p>
        <button
          type="button"
          class="cursor-pointer rounded text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
          :aria-label="t.dismiss"
          @click="chat.dismissNotice"
        >
          <X class="size-4" />
        </button>
      </div>

      <ChatComposer :strings="t" :disabled="!ready || chat.busy" @send="chat.send" />
    </section>
    <p class="mt-3 hidden text-xs text-muted-foreground sm:block">{{ t.poweredBy }}</p>
  </div>
</template>
