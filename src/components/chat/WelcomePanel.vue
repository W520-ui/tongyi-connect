<script setup lang="ts">
import { MessageSquareText, Sparkles } from '@lucide/vue'

import type { CustomerStrings } from '@/i18n/customer'

defineProps<{ strings: CustomerStrings }>()
const emit = defineEmits<{ pick: [text: string] }>()
</script>

<template>
  <div class="m-auto flex w-full max-w-md flex-col items-center px-2 py-6 text-center">
    <div class="grid size-12 place-items-center rounded-xl bg-primary text-primary-foreground" aria-hidden="true">
      <Sparkles class="size-5" />
    </div>
    <h2 class="mt-5 text-xl font-semibold tracking-tight">{{ strings.welcomeTitle }}</h2>
    <p class="mt-2 text-sm leading-relaxed text-muted-foreground">{{ strings.welcomeBody }}</p>
    <div class="mt-6 flex w-full flex-col gap-2">
      <button
        v-for="text in strings.suggestions"
        :key="text"
        type="button"
        class="flex cursor-pointer items-center gap-2.5 rounded-xl border bg-background px-3.5 py-3 text-left text-[13.5px] transition-colors outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50"
        @click="emit('pick', text)"
      >
        <MessageSquareText class="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        {{ text }}
      </button>
    </div>
  </div>
</template>
