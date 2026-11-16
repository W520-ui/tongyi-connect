<script setup lang="ts">
import { Boxes, CircleAlert, CupSoda, Headphones, Lamp, LoaderCircle, Package, Truck } from '@lucide/vue'
import { type Component, onMounted } from 'vue'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useCatalogStore } from '@/stores/catalog'

const ICONS: Record<string, Component> = {
  'headset-pro': Headphones,
  'lamp-mini': Lamp,
  'bottle-lite': CupSoda,
}

const price = new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'USD' })
const catalog = useCatalogStore()
onMounted(catalog.refresh)
</script>

<template>
  <div
    v-if="catalog.error && !catalog.loaded"
    class="flex flex-col items-center gap-3 rounded-xl border bg-card p-12 text-center text-sm"
    role="alert"
  >
    <CircleAlert class="size-5 text-muted-foreground" aria-hidden="true" />
    <p class="text-muted-foreground">商品资料加载失败：{{ catalog.error.message }}</p>
    <Button variant="outline" size="sm" @click="catalog.refresh">重新加载</Button>
  </div>
  <div
    v-else-if="!catalog.loaded"
    class="flex items-center justify-center gap-2 rounded-xl border bg-card p-12 text-sm text-muted-foreground"
    role="status"
  >
    <LoaderCircle class="size-4 animate-spin" aria-hidden="true" />
    正在加载商品资料…
  </div>
  <p v-else-if="!catalog.products.length" class="rounded-xl border bg-card p-12 text-center text-sm text-muted-foreground">
    还没有商品资料
  </p>
  <div v-else class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
    <Card v-for="product in catalog.products" :key="product.id" class="py-5">
      <CardContent class="px-5">
        <div class="flex items-center gap-3">
          <div class="grid size-10 shrink-0 place-items-center rounded-lg bg-muted" aria-hidden="true">
            <component :is="ICONS[product.id] ?? Package" class="size-5" />
          </div>
          <div class="min-w-0 flex-1">
            <p class="truncate font-medium">{{ product.name }}</p>
            <p class="truncate text-xs text-muted-foreground">{{ product.english_name }}</p>
          </div>
          <Badge variant="outline" class="font-normal">{{ product.category }}</Badge>
        </div>

        <p class="mt-5 text-2xl font-semibold tracking-tight tabular-nums">{{ price.format(product.price_usd) }}</p>
        <div class="mt-1 flex gap-4 text-xs text-muted-foreground">
          <span class="inline-flex items-center gap-1"><Boxes class="size-3.5" aria-hidden="true" />库存 {{ product.stock }}</span>
          <span class="inline-flex items-center gap-1"><Truck class="size-3.5" aria-hidden="true" />{{ product.shipping_days }}</span>
        </div>

        <dl class="mt-4 grid grid-cols-2 gap-2">
          <div v-for="(value, key) in product.specs" :key="key" class="rounded-md bg-muted/60 px-3 py-2">
            <dt class="text-xs text-muted-foreground">{{ key }}</dt>
            <dd class="mt-0.5 text-sm font-medium">{{ value }}</dd>
          </div>
        </dl>

        <p class="mt-4 font-mono text-xs text-muted-foreground">{{ product.id }}</p>
      </CardContent>
    </Card>
  </div>
</template>
