<script setup lang="ts">
import { MessageSquareText, Sparkles } from 'lucide-vue-next'
import { NIcon } from 'naive-ui'

import type { CustomerStrings } from '../../i18n/customer'

defineProps<{ strings: CustomerStrings }>()
const emit = defineEmits<{ pick: [text: string] }>()
</script>

<template>
  <div class="welcome">
    <div class="welcome-mark" aria-hidden="true"><NIcon :size="26" :component="Sparkles" /></div>
    <h2>{{ strings.welcomeTitle }}</h2>
    <p>{{ strings.welcomeBody }}</p>
    <div class="suggestions">
      <button v-for="text in strings.suggestions" :key="text" type="button" @click="emit('pick', text)">
        <NIcon :size="15" :component="MessageSquareText" aria-hidden="true" />
        {{ text }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.welcome {
  display: flex;
  max-width: 460px;
  flex-direction: column;
  align-items: center;
  margin: auto;
  padding: 24px 8px;
  text-align: center;
}

.welcome-mark {
  display: grid;
  width: 60px;
  height: 60px;
  place-items: center;
  border-radius: 20px;
  color: #fff;
  background: var(--mark-gradient);
  box-shadow: 0 16px 32px -14px rgba(15, 118, 110, 0.7);
}

h2 {
  margin: 20px 0 8px;
  color: var(--text-strong);
  font-size: 22px;
  letter-spacing: -0.02em;
}

p {
  margin: 0;
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.7;
}

.suggestions {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 10px;
  margin-top: 24px;
}

.suggestions button {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 14px;
  color: var(--text);
  background: var(--surface);
  cursor: pointer;
  font: inherit;
  font-size: 13.5px;
  text-align: left;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
}

.suggestions button:hover {
  border-color: rgba(15, 118, 110, 0.4);
  box-shadow: 0 8px 20px -14px rgba(15, 118, 110, 0.55);
  transform: translateY(-1px);
}

.suggestions button:focus-visible {
  outline: 3px solid var(--brand-ring);
  outline-offset: 2px;
}

.suggestions :deep(.n-icon) {
  color: var(--brand);
}
</style>
