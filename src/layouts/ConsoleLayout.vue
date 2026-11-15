<script setup lang="ts">
import { Activity, ChartColumn, ExternalLink, Inbox, Moon, Package, Sun } from '@lucide/vue'
import { computed, type Component } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { systemStatus } from '@/fixtures/demo'
import { useInboxStore } from '@/stores/inbox'
import { useConsoleTheme } from '@/theme'

interface NavItem {
  name: string
  label: string
  icon: Component
}

const NAV: NavItem[] = [
  { name: 'inbox', label: '收件箱', icon: Inbox },
  { name: 'dashboard', label: '数据看板', icon: ChartColumn },
  { name: 'catalog', label: '商品资料', icon: Package },
  { name: 'system', label: '系统状态', icon: Activity },
]

const route = useRoute()
const inbox = useInboxStore()
const { isDark, toggle } = useConsoleTheme()
const status = systemStatus

const title = computed(() => route.meta.title ?? '')
const subtitle = computed(() => route.meta.subtitle ?? '')
const themeLabel = computed(() => (isDark.value ? '切换到浅色' : '切换到深色'))
</script>

<template>
  <div class="flex h-svh bg-background text-foreground">
    <aside class="hidden w-60 shrink-0 flex-col border-r bg-sidebar md:flex">
      <div class="flex h-16 items-center gap-2.5 px-5">
        <div
          class="grid size-8 place-items-center rounded-lg bg-brand text-sm font-semibold text-brand-foreground"
          aria-hidden="true"
        >
          通
        </div>
        <div class="leading-tight">
          <p class="text-sm font-semibold">通译智联</p>
          <p class="text-xs text-muted-foreground">商家控制台</p>
        </div>
      </div>

      <nav class="flex flex-col gap-0.5 px-3 py-2" aria-label="主导航">
        <RouterLink
          v-for="item in NAV"
          :key="item.name"
          :to="{ name: item.name }"
          class="flex h-9 items-center gap-2.5 rounded-md px-2.5 text-sm text-muted-foreground transition-colors outline-none hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
          active-class="bg-sidebar-accent font-medium text-sidebar-accent-foreground"
        >
          <component :is="item.icon" class="size-4" aria-hidden="true" />
          <span class="flex-1">{{ item.label }}</span>
          <Badge
            v-if="item.name === 'inbox' && inbox.counts.open"
            class="min-w-5 rounded-full bg-warning-soft px-1.5 text-warning tabular-nums"
          >
            {{ inbox.counts.open }}
          </Badge>
        </RouterLink>
      </nav>

      <div class="mt-auto p-3">
        <a
          href="/chat"
          target="_blank"
          rel="noopener"
          class="flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ExternalLink class="size-4" aria-hidden="true" />
          打开客户窗口
        </a>
      </div>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <header class="flex h-16 shrink-0 items-center justify-between gap-4 border-b px-4 sm:px-6">
        <div class="flex min-w-0 items-center gap-3">
          <nav class="flex items-center gap-1 md:hidden" aria-label="主导航">
            <RouterLink
              v-for="item in NAV"
              :key="item.name"
              :to="{ name: item.name }"
              :aria-label="item.label"
              class="grid size-8 place-items-center rounded-md text-muted-foreground"
              active-class="bg-muted text-foreground"
            >
              <component :is="item.icon" class="size-4" />
            </RouterLink>
          </nav>
          <div class="min-w-0">
            <h1 class="truncate text-base font-semibold">{{ title }}</h1>
            <p class="hidden truncate text-xs text-muted-foreground sm:block">{{ subtitle }}</p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <Badge variant="outline" class="hidden font-normal text-muted-foreground lg:inline-flex">原型 · 演示数据</Badge>
          <span class="hidden items-center gap-2 rounded-md border px-2.5 py-1 text-xs text-muted-foreground sm:inline-flex">
            <span
              class="size-1.5 rounded-full"
              :class="status.llm_configured ? 'bg-success' : 'bg-warning'"
              aria-hidden="true"
            />
            {{ status.llm_configured ? `模型已连接 · ${status.model}` : '模型未配置' }}
          </span>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button variant="ghost" size="icon-sm" :aria-label="themeLabel" @click="toggle">
                <Sun v-if="isDark" />
                <Moon v-else />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{{ themeLabel }}</TooltipContent>
          </Tooltip>
        </div>
      </header>

      <main class="min-h-0 flex-1 overflow-y-auto bg-muted/40 p-4 [scrollbar-width:thin] sm:p-6">
        <RouterView />
      </main>
    </div>
  </div>
</template>
