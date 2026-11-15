<script setup lang="ts">
import { RouterLink } from 'vue-router'

import { Button } from '@/components/ui/button'
</script>

<template>
  <main class="grid min-h-svh place-items-center bg-muted/40 p-6">
    <div class="flex max-w-sm flex-col items-center text-center">
      <p class="font-mono text-sm text-muted-foreground">404</p>
      <h1 class="mt-2 text-2xl font-semibold tracking-tight">页面不存在</h1>
      <p class="mt-2 text-sm text-muted-foreground">这个地址没有对应的页面。</p>
      <div class="mt-6 flex gap-2">
        <Button as-child>
          <RouterLink to="/console/inbox">商家控制台</RouterLink>
        </Button>
        <Button variant="outline" as-child>
          <RouterLink to="/chat">客户窗口</RouterLink>
        </Button>
      </div>
    </div>
  </main>
</template>
