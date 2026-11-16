<script setup lang="ts">
import { Bot } from '@lucide/vue'

defineProps<{ label: string; activity?: string | null }>()
</script>

<template>
  <div class="flex items-center gap-2.5" role="status" :aria-label="activity || label">
    <div class="grid size-7 shrink-0 place-items-center rounded-full border bg-background text-muted-foreground">
      <Bot class="size-4" aria-hidden="true" />
    </div>
    <div class="flex items-center gap-1 rounded-2xl rounded-bl-md bg-muted px-4 py-3.5">
      <span
        v-for="dot in 3"
        :key="dot"
        class="size-1.5 animate-bounce rounded-full bg-muted-foreground/60"
        :style="{ animationDelay: `${(dot - 1) * 150}ms` }"
      />
    </div>
    <span v-if="activity" class="text-xs text-muted-foreground" aria-hidden="true">{{ activity }}</span>
  </div>
</template>
