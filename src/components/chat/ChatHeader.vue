<script setup lang="ts">
import { Headset, RotateCcw, Store } from 'lucide-vue-next'
import { NButton, NIcon, NSelect, NTooltip } from 'naive-ui'

import type { Language } from '../../api/types'
import type { CustomerStrings } from '../../i18n/customer'
import { LANGUAGE_META } from '../../labels'

defineProps<{ strings: CustomerStrings; handedOff: boolean }>()
const locale = defineModel<Language>('locale', { required: true })
const emit = defineEmits<{ handoff: []; reset: [] }>()

const languageOptions = (Object.keys(LANGUAGE_META) as Language[]).map((code) => ({
  label: LANGUAGE_META[code].native,
  value: code,
}))
</script>

<template>
  <header class="chat-header">
    <div class="identity">
      <div class="store-mark" aria-hidden="true"><NIcon :size="20" :component="Store" /></div>
      <div class="identity-copy">
        <strong>Tongyi Demo Store</strong>
        <span><i class="online-dot" aria-hidden="true" />{{ strings.status }}</span>
      </div>
    </div>
    <div class="actions">
      <NSelect
        v-model:value="locale"
        class="lang-select"
        size="small"
        :options="languageOptions"
        :aria-label="strings.language"
      />
      <NButton size="small" secondary :disabled="handedOff" @click="emit('handoff')">
        <template #icon><NIcon :component="Headset" /></template>
        {{ strings.talkToHuman }}
      </NButton>
      <NTooltip>
        <template #trigger>
          <NButton size="small" quaternary circle :aria-label="strings.newChat" @click="emit('reset')">
            <template #icon><NIcon :component="RotateCcw" /></template>
          </NButton>
        </template>
        {{ strings.newChat }}
      </NTooltip>
    </div>
  </header>
</template>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
}

.identity {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.store-mark {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 13px;
  color: #fff;
  background: var(--mark-gradient);
  box-shadow: 0 8px 18px -8px rgba(15, 118, 110, 0.6);
}

.identity-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.identity-copy strong {
  color: var(--text-strong);
  font-size: 15px;
  letter-spacing: -0.01em;
}

.identity-copy span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  overflow: hidden;
  color: var(--text-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.online-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}

.actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.lang-select {
  width: 112px;
}

@media (max-width: 600px) {
  .chat-header {
    flex-wrap: wrap;
  }

  .actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
