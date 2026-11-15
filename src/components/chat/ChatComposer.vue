<script setup lang="ts">
import { ArrowUp } from '@lucide/vue'
import { computed, ref } from 'vue'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { CustomerStrings } from '@/i18n/customer'

const props = defineProps<{ strings: CustomerStrings; disabled?: boolean }>()
const emit = defineEmits<{ send: [text: string] }>()

const text = ref('')
const canSend = computed(() => text.value.trim().length > 0 && !props.disabled)

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
  <form class="border-t px-4 pt-3 pb-2.5 sm:px-5" @submit.prevent="submit">
    <div
      class="flex items-end gap-2 rounded-xl border bg-background py-1.5 pr-1.5 pl-3 transition-[color,box-shadow] focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50"
    >
      <Textarea
        :model-value="text"
        rows="1"
        :maxlength="20000"
        :placeholder="strings.placeholder"
        class="max-h-36 min-h-9 resize-none border-0 bg-transparent px-0 py-2 shadow-none focus-visible:ring-0 dark:bg-transparent"
        @update:model-value="(value) => (text = String(value))"
        @keydown="onKeydown"
      />
      <Button type="submit" size="icon-sm" :disabled="!canSend" :aria-label="strings.send">
        <ArrowUp />
      </Button>
    </div>
    <p class="mt-2 px-1 text-[11px] text-muted-foreground">{{ strings.hint }}</p>
  </form>
</template>
