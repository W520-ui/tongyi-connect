<script setup lang="ts">
import { CupSoda, Headphones, Lamp, Package, Truck } from 'lucide-vue-next'
import { NIcon } from 'naive-ui'
import { computed, type Component } from 'vue'

import type { Language, Product } from '../../api/types'
import type { CustomerStrings } from '../../i18n/customer'
import { dayRange } from '../../utils/time'

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
  <article class="product">
    <div class="product-icon" aria-hidden="true"><NIcon :size="20" :component="icon" /></div>
    <div class="product-copy">
      <strong>{{ name }}</strong>
      <span>
        <NIcon :size="13" :component="Truck" aria-hidden="true" />
        {{ shipping }} · {{ strings.inStock(product.stock) }}
      </span>
    </div>
    <div class="price">{{ price }}</div>
  </article>
</template>

<style scoped>
.product {
  display: flex;
  width: min(420px, 100%);
  align-items: center;
  gap: 12px;
  padding: 10px 14px 10px 10px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--surface);
  box-shadow: 0 6px 18px -14px rgba(15, 23, 42, 0.35);
}

.product-icon {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 12px;
  color: var(--brand);
  background: linear-gradient(140deg, #ecfdf5 0%, #e0f2fe 100%);
}

.product-copy {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 3px;
}

.product-copy strong {
  overflow: hidden;
  color: var(--text-strong);
  font-size: 13.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-copy span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-muted);
  font-size: 12px;
}

.price {
  color: var(--text-strong);
  font-size: 15px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}
</style>
