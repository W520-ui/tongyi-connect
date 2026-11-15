<script setup lang="ts">
import { Bot } from '@lucide/vue'
import { computed } from 'vue'

import type { HistoryMessage, Language } from '@/api/types'
import type { CustomerStrings } from '@/i18n/customer'
import { clockTime } from '@/utils/time'

import ProductCard from './ProductCard.vue'

const props = defineProps<{
  message: HistoryMessage
  locale: Language
  strings: CustomerStrings
  streaming?: boolean
}>()

const isUser = computed(() => props.message.role === 'user')
const products = computed(() => (props.streaming ? [] : (props.message.workflow?.matched_products ?? [])))
const time = computed(() => clockTime(props.message.created_at, props.locale))
</script>

<template>
  <div class="flex items-end gap-2.5" :class="{ 'justify-end': isUser }">
    <div
      v-if="!isUser"
      class="mb-5 grid size-7 shrink-0 place-items-center rounded-full border bg-background text-muted-foreground"
      aria-hidden="true"
    >
      <Bot class="size-4" />
    </div>
    <div class="flex max-w-[80%] flex-col gap-2" :class="isUser ? 'items-end' : 'items-start'">
      <div
        class="whitespace-pre-wrap break-words px-3.5 py-2.5 text-[14.5px] leading-relaxed"
        :class="
          isUser
            ? 'rounded-2xl rounded-br-md bg-primary text-primary-foreground'
            : 'rounded-2xl rounded-bl-md bg-muted text-foreground'
        "
      >
        {{ message.content
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
      <time class="px-1 text-[11px] text-muted-foreground" :datetime="message.created_at">{{ time }}</time>
    </div>
  </div>
</template>
