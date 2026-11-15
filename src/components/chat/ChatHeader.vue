<script setup lang="ts">
import { Headset, RotateCcw, Store } from '@lucide/vue'

import type { Language } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { CustomerStrings } from '@/i18n/customer'
import { LANGUAGE_META } from '@/labels'

defineProps<{ strings: CustomerStrings; handedOff: boolean }>()
const locale = defineModel<Language>('locale', { required: true })
const emit = defineEmits<{ handoff: []; reset: [] }>()

const languages = Object.keys(LANGUAGE_META) as Language[]

function setLocale(value: unknown) {
  if (typeof value === 'string' && value in LANGUAGE_META) locale.value = value as Language
}
</script>

<template>
  <header class="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-5">
    <div class="flex min-w-0 items-center gap-3">
      <div class="grid size-9 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground" aria-hidden="true">
        <Store class="size-[18px]" />
      </div>
      <div class="min-w-0">
        <p class="truncate text-sm font-semibold">Tongyi Demo Store</p>
        <p class="flex items-center gap-1.5 truncate text-xs text-muted-foreground">
          <span class="size-1.5 shrink-0 rounded-full bg-success" aria-hidden="true" />
          {{ strings.status }}
        </p>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <Select :model-value="locale" @update:model-value="setLocale">
        <SelectTrigger size="sm" class="w-[118px]" :aria-label="strings.language">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem v-for="code in languages" :key="code" :value="code">
            {{ LANGUAGE_META[code].native }}
          </SelectItem>
        </SelectContent>
      </Select>
      <Button variant="outline" size="sm" :disabled="handedOff" @click="emit('handoff')">
        <Headset />
        {{ strings.talkToHuman }}
      </Button>
      <Tooltip>
        <TooltipTrigger as-child>
          <Button variant="ghost" size="icon-sm" :aria-label="strings.newChat" @click="emit('reset')">
            <RotateCcw />
          </Button>
        </TooltipTrigger>
        <TooltipContent>{{ strings.newChat }}</TooltipContent>
      </Tooltip>
    </div>
  </header>
</template>
