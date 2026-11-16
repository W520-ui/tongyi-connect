<script setup lang="ts">
import { Bot, CircleAlert, Headset, RotateCw, UserRound } from '@lucide/vue'
import { computed } from 'vue'

import type { Language } from '@/api/types'
import { Button } from '@/components/ui/button'
import { type CustomerStrings, customerErrorKind } from '@/i18n/customer'
import type { ChatEntry } from '@/stores/chat'
import { clockTime } from '@/utils/time'

import ProductCard from './ProductCard.vue'

const props = defineProps<{
  entry: ChatEntry
  locale: Language
  strings: CustomerStrings
  streaming?: boolean
  /** Another message is on its way, so retrying must wait. */
  busy?: boolean
}>()
const emit = defineEmits<{ retry: [key: string] }>()

const isUser = computed(() => props.entry.role === 'user')
const isStaff = computed(() => props.entry.role === 'human_agent')
const products = computed(() => (props.streaming ? [] : props.entry.products))
const time = computed(() => clockTime(props.entry.createdAt, props.locale))
const failure = computed(() =>
  props.entry.status === 'failed' && props.entry.error
    ? props.strings.errors[customerErrorKind(props.entry.error.code)]
    : null,
)
// A rejected message (e.g. too long) cannot succeed by sending it again.
const canRetry = computed(() => props.entry.error?.code !== 'VALIDATION_ERROR')
</script>

<template>
  <div v-if="entry.notice" class="flex justify-center" role="status">
    <p class="flex max-w-[85%] items-start gap-2 rounded-xl border bg-background px-3.5 py-2.5 text-[13px] leading-relaxed text-muted-foreground">
      <Headset class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span>{{ entry.content }}</span>
    </p>
  </div>

  <div v-else class="flex items-end gap-2.5" :class="{ 'justify-end': isUser }">
    <div
      v-if="!isUser"
      class="mb-5 grid size-7 shrink-0 place-items-center rounded-full border bg-background text-muted-foreground"
      aria-hidden="true"
    >
      <component :is="isStaff ? UserRound : Bot" class="size-4" />
    </div>
    <div class="flex max-w-[80%] flex-col gap-2" :class="isUser ? 'items-end' : 'items-start'">
      <div
        class="whitespace-pre-wrap break-words px-3.5 py-2.5 text-[14.5px] leading-relaxed transition-opacity"
        :class="[
          isUser
            ? 'rounded-2xl rounded-br-md bg-primary text-primary-foreground'
            : 'rounded-2xl rounded-bl-md bg-muted text-foreground',
          entry.status === 'sending' && 'opacity-70',
        ]"
      >
        {{ entry.content
        }}<span
          v-if="streaming"
          class="ml-0.5 inline-block h-4 w-[3px] translate-y-0.5 animate-pulse rounded-sm bg-current opacity-60"
          aria-hidden="true"
        />
      </div>
      <ProductCard
        v-for="product in products"
        :key="product.id"
        :product="product"
        :locale="locale"
        :strings="strings"
      />
      <div v-if="failure" class="flex max-w-full flex-wrap items-center justify-end gap-x-2 gap-y-1 px-1 text-xs" role="alert">
        <span class="inline-flex items-center gap-1 text-destructive">
          <CircleAlert class="size-3.5 shrink-0" aria-hidden="true" />
          {{ strings.notSent }}
        </span>
        <span class="text-muted-foreground">{{ failure }}</span>
        <Button
          v-if="canRetry"
          variant="outline"
          size="xs"
          :disabled="busy"
          @click="emit('retry', entry.key)"
        >
          <RotateCw />
          {{ strings.retry }}
        </Button>
      </div>
      <time v-else class="px-1 text-[11px] text-muted-foreground" :datetime="entry.createdAt">{{ time }}</time>
    </div>
  </div>
</template>
