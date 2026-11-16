<script setup lang="ts">
import { Activity, ChartColumn, ExternalLink, Inbox, KeyRound, Moon, Package, Sun } from '@lucide/vue'
import { computed, type Component } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { usePolling } from '@/composables/usePolling'
import { useDashboardStore } from '@/stores/dashboard'
import { useInboxStore } from '@/stores/inbox'
import { useSystemStore } from '@/stores/system'
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
const dashboard = useDashboardStore()
const system = useSystemStore()
const { isDark, toggle } = useConsoleTheme()

// A.7: ticket lists refresh every 10 s (paused while the tab is hidden). Polling
// here keeps the sidebar count current on every console page.
usePolling(inbox.refresh, 10_000)
usePolling(system.refresh, 30_000)

const title = computed(() => route.meta.title ?? '')
const subtitle = computed(() => route.meta.subtitle ?? '')
const themeLabel = computed(() => (isDark.value ? '切换到浅色' : '切换到深色'))

const modelPill = computed(() => {
  if (system.error) return { ok: false, text: '后端未连接' }
  if (!system.status) return { ok: null, text: '正在检查后端…' }
  return system.status.llm_configured
    ? { ok: true, text: `模型已连接 · ${system.status.model ?? ''}` }
    : { ok: false, text: '模型未配置' }
})
const needsKey = computed(
  () => inbox.error?.code === 'UNAUTHORIZED' || dashboard.error?.code === 'UNAUTHORIZED',
)
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
          <RouterLink
            :to="{ name: 'system' }"
            class="hidden items-center gap-2 rounded-md border px-2.5 py-1 text-xs text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 sm:inline-flex"
          >
            <span
              class="size-1.5 rounded-full"
              :class="modelPill.ok === null ? 'bg-muted-foreground/50' : modelPill.ok ? 'bg-success' : 'bg-warning'"
              aria-hidden="true"
            />
            {{ modelPill.text }}
          </RouterLink>
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
        <div
          v-if="needsKey && route.name !== 'system'"
          class="mb-4 flex flex-wrap items-center gap-3 rounded-xl border bg-warning-soft px-4 py-3 text-sm text-warning"
          role="alert"
        >
          <KeyRound class="size-4 shrink-0" aria-hidden="true" />
          <p class="flex-1">后端开启了商家密钥校验，请先填写商家密钥，否则收件箱和看板无法加载。</p>
          <Button as-child size="sm" variant="outline">
            <RouterLink :to="{ name: 'system' }">去填写</RouterLink>
          </Button>
        </div>
        <RouterView />
      </main>
    </div>
  </div>
</template>
