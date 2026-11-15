<script setup lang="ts">
import type { Component } from 'vue'

import { Card, CardContent } from '@/components/ui/card'

defineProps<{
  label: string
  value: string | number
  caption: string
  icon: Component
}>()
</script>

<template>
  <Card class="gap-0 py-5">
    <CardContent class="px-5">
      <div class="flex items-center justify-between">
        <span class="text-sm text-muted-foreground">{{ label }}</span>
        <component :is="icon" class="size-4 text-muted-foreground" aria-hidden="true" />
      </div>
      <div class="mt-3 text-3xl font-semibold tracking-tight tabular-nums">{{ value }}</div>
      <p class="mt-1 text-xs text-muted-foreground">{{ caption }}</p>
    </CardContent>
  </Card>
</template>
