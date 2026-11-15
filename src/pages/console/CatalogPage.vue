<script setup lang="ts">
import { CupSoda, Headphones, Lamp, Package, Truck, Boxes } from 'lucide-vue-next'
import { NCard, NIcon, NTag } from 'naive-ui'
import type { Component } from 'vue'

import { products } from '../../fixtures/demo'

const ICONS: Record<string, Component> = {
  'headset-pro': Headphones,
  'lamp-mini': Lamp,
  'bottle-lite': CupSoda,
}

const price = new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'USD' })
</script>

<template>
  <div class="catalog">
    <NCard v-for="product in products" :key="product.id" :bordered="false" class="product">
      <div class="product-head">
        <div class="product-icon" aria-hidden="true">
          <NIcon :size="22" :component="ICONS[product.id] ?? Package" />
        </div>
        <div class="product-names">
          <strong>{{ product.name }}</strong>
          <span>{{ product.english_name }}</span>
        </div>
        <NTag size="small" :bordered="false">{{ product.category }}</NTag>
      </div>

      <div class="product-price">{{ price.format(product.price_usd) }}</div>

      <div class="product-facts">
        <span><NIcon :size="14" :component="Boxes" aria-hidden="true" />库存 {{ product.stock }}</span>
        <span><NIcon :size="14" :component="Truck" aria-hidden="true" />{{ product.shipping_days }}</span>
      </div>

      <dl class="specs">
        <div v-for="(value, key) in product.specs" :key="key">
          <dt>{{ key }}</dt>
          <dd>{{ value }}</dd>
        </div>
      </dl>

      <div class="product-id mono">{{ product.id }}</div>
    </NCard>
  </div>
</template>

<style scoped>
.catalog {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.product {
  box-shadow: var(--shadow-card);
}

.product-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.product-icon {
  display: grid;
  width: 46px;
  height: 46px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 14px;
  color: var(--brand);
  background: var(--brand-soft);
}

.product-names {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.product-names strong {
  color: var(--text-strong);
  font-size: 15px;
}

.product-names span {
  overflow: hidden;
  color: var(--text-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-price {
  margin-top: 18px;
  color: var(--text-strong);
  font-size: 26px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.product-facts {
  display: flex;
  gap: 16px;
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 12.5px;
}

.product-facts span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.specs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 16px 0 0;
}

.specs div {
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--surface-muted);
}

.specs dt {
  color: var(--text-faint);
  font-size: 11.5px;
}

.specs dd {
  margin: 2px 0 0;
  color: var(--text-strong);
  font-size: 13px;
  font-weight: 500;
}

.product-id {
  margin-top: 14px;
  color: var(--text-faint);
  font-size: 11.5px;
}
</style>
