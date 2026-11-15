<script setup lang="ts">
import { Bot } from 'lucide-vue-next'
import { NIcon } from 'naive-ui'
import { computed } from 'vue'

import type { HistoryMessage, Language } from '../../api/types'
import type { CustomerStrings } from '../../i18n/customer'
import { clockTime } from '../../utils/time'
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
  <div class="row" :class="isUser ? 'row--user' : 'row--agent'">
    <div v-if="!isUser" class="avatar" aria-hidden="true"><NIcon :size="16" :component="Bot" /></div>
    <div class="stack">
      <div class="bubble" :class="{ 'bubble--streaming': streaming }">{{ message.content }}</div>
      <ProductCard
        v-for="product in products"
        :key="product.id"
        :product="product"
        :locale="locale"
        :strings="strings"
      />
      <time class="time" :datetime="message.created_at">{{ time }}</time>
    </div>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.row--user {
  justify-content: flex-end;
}

.avatar {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  place-items: center;
  margin-bottom: 22px;
  border: 1px solid rgba(15, 118, 110, 0.14);
  border-radius: 50%;
  color: var(--brand);
  background: var(--brand-soft);
}

.stack {
  display: flex;
  max-width: min(78%, 540px);
  flex-direction: column;
  gap: 8px;
}

.row--user .stack {
  align-items: flex-end;
}

.bubble {
  padding: 11px 15px;
  font-size: 14.5px;
  line-height: 1.62;
  white-space: pre-wrap;
  word-break: break-word;
}

.row--agent .bubble {
  border-radius: 18px 18px 18px 6px;
  color: var(--text-strong);
  background: #f1f5f4;
}

.row--user .bubble {
  border-radius: 18px 18px 6px 18px;
  color: #fff;
  background: var(--brand-gradient);
  box-shadow: 0 10px 20px -12px rgba(15, 118, 110, 0.7);
}

.bubble--streaming::after {
  display: inline-block;
  width: 7px;
  height: 15px;
  margin-left: 3px;
  border-radius: 2px;
  background: currentColor;
  content: '';
  opacity: 0.45;
  vertical-align: -2px;
  animation: caret 1s steps(2) infinite;
}

.time {
  padding: 0 4px;
  color: var(--text-faint);
  font-size: 11px;
}

@keyframes caret {
  50% {
    opacity: 0;
  }
}
</style>
