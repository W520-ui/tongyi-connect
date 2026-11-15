<script setup lang="ts">
import { SendHorizontal } from 'lucide-vue-next'
import { NButton, NIcon, NInput } from 'naive-ui'
import { computed, ref } from 'vue'

import type { CustomerStrings } from '../../i18n/customer'

const props = defineProps<{ strings: CustomerStrings; disabled?: boolean }>()
const emit = defineEmits<{ send: [text: string] }>()

const text = ref('')
const canSend = computed(() => text.value.trim().length > 0 && !props.disabled)

const inputTheme = {
  color: 'transparent',
  colorFocus: 'transparent',
  boxShadowFocus: 'none',
  fontSizeMedium: '14.5px',
}

function submit() {
  if (!canSend.value) return
  emit('send', text.value.trim())
  text.value = ''
}

function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.shiftKey) return
  // Enter that confirms an IME candidate (e.g. pinyin) must not send the message.
  if (event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  submit()
}
</script>

<template>
  <form class="composer" @submit.prevent="submit">
    <div class="field">
      <NInput
        v-model:value="text"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 5 }"
        :bordered="false"
        :maxlength="20000"
        :placeholder="strings.placeholder"
        :theme-overrides="inputTheme"
        @keydown="onKeydown"
      />
      <NButton type="primary" circle attr-type="submit" :disabled="!canSend" :aria-label="strings.send">
        <template #icon><NIcon :component="SendHorizontal" /></template>
      </NButton>
    </div>
    <p class="hint">{{ strings.hint }}</p>
  </form>
</template>

<style scoped>
.composer {
  padding: 14px 18px 12px;
  border-top: 1px solid var(--line);
  background: var(--surface);
}

.field {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 6px 6px 6px 10px;
  border: 1px solid var(--line-strong);
  border-radius: 18px;
  background: var(--surface);
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.field:focus-within {
  border-color: var(--brand);
  box-shadow: 0 0 0 4px var(--brand-ring);
}

.hint {
  margin: 8px 4px 0;
  color: var(--text-faint);
  font-size: 11.5px;
}
</style>
