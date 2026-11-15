<script setup lang="ts">
import { CupSoda, Headphones, Lamp, Package, Truck } from '@lucide/vue'
import { computed, type Component } from 'vue'

import type { Language, Product } from '@/api/types'
import type { CustomerStrings } from '@/i18n/customer'
import { dayRange } from '@/utils/time'

const props = defineProps<{ product: Product; locale: Language; strings: CustomerStrings }>()

const ICONS: Record<string, Component> = {
  'headset-pro': Headphones,
  'lamp-mini': Lamp,
  'bottle-lite': CupSoda,
}

const icon = computed(() => ICONS[props.product.id] ?? Package)
const name = computed(() => (props.locale === 'zh-CN' ? props.product.name : props.product.english_name))
const shipping = computed(() => {
  const range = dayRange(props.product.shipping_days)
  return range ? props.strings.shipsIn(range) : props.product.shipping_days
})
const price = computed(() =>
  new Intl.NumberFormat(props.locale, { style: 'currency', currency: 'USD' }).format(props.product.price_usd),
)
</script>

<template>
  <article class="flex w-full max-w-md items-center gap-3 rounded-xl border bg-background p-2.5 pr-3.5">
    <div class="grid size-10 shrink-0 place-items-center rounded-lg bg-muted text-foreground" aria-hidden="true">
      <component :is="icon" class="size-5" />
    </div>
    <div class="min-w-0 flex-1">
      <p class="truncate text-[13px] font-medium">{{ name }}</p>
      <p class="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
        <Truck class="size-3.5 shrink-0" aria-hidden="true" />
        <span class="truncate">{{ shipping }} · {{ strings.inStock(product.stock) }}</span>
      </p>
    </div>
    <p class="text-sm font-semibold tabular-nums">{{ price }}</p>
  </article>
</template>
