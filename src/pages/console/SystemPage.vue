<script setup lang="ts">
import { Cpu, Database, Info, KeyRound, RefreshCw, Server } from '@lucide/vue'
import { type Component, computed, onMounted, ref } from 'vue'
import { toast } from 'vue-sonner'

import { getMerchantKey, setMerchantKey } from '@/api/merchant-key'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { TONE_CLASSES } from '@/labels'
import { useDashboardStore } from '@/stores/dashboard'
import { useInboxStore } from '@/stores/inbox'
import { useSystemStore } from '@/stores/system'
import { clockTime } from '@/utils/time'

interface StatusItem {
  title: string
  icon: Component
  ok: boolean | null // null: unknown because the backend is unreachable
  value: string
  detail: string
}

const system = useSystemStore()
const inbox = useInboxStore()
const dashboard = useDashboardStore()
onMounted(system.refresh)

const items = computed<StatusItem[]>(() => {
  const status = system.status
  const reachable = Boolean(status) && !system.error
  return [
    {
      title: '后端 API',
      icon: Server,
      ok: reachable,
      value: reachable && status ? `版本 ${status.version}` : '无法连接',
      detail: reachable ? 'FastAPI 服务，接口契约 v0.1' : (system.error?.message ?? '正在检查…'),
    },
    {
      title: '对话模型',
      icon: Cpu,
      ok: reachable && status ? status.llm_configured : null,
      value: status ? (status.llm_configured ? (status.model ?? '已配置') : '未配置') : '—',
      detail:
        status && !status.llm_configured
          ? '后端还没有配置模型密钥，客户发消息会提示助手暂不可用'
          : 'OpenAI 兼容接口，密钥只保存在后端',
    },
    {
      title: '数据库',
      icon: Database,
      ok: reachable && status ? status.db_ok : null,
      value: status ? (status.db_ok ? '连接正常' : '无法连接') : '—',
      detail: '会话、消息、工单与运行轨迹',
    },
  ]
})

function badge(ok: boolean | null) {
  if (ok === null) return { label: '未知', tone: TONE_CLASSES.neutral }
  return ok ? { label: '正常', tone: TONE_CLASSES.success } : { label: '需要处理', tone: TONE_CLASSES.warning }
}

const keyInput = ref('')
const keySaved = ref(Boolean(getMerchantKey()))

function saveKey() {
  setMerchantKey(keyInput.value)
  keySaved.value = Boolean(getMerchantKey())
  keyInput.value = ''
  toast.success(keySaved.value ? '商家密钥已保存在这个浏览器' : '商家密钥已清除')
  void inbox.refresh()
  void dashboard.refresh()
}

function clearKey() {
  keyInput.value = ''
  saveKey()
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <section class="grid gap-4 md:grid-cols-3">
      <Card v-for="item in items" :key="item.title" class="py-5">
        <CardContent class="px-5">
          <div class="flex items-center justify-between">
            <div class="grid size-9 place-items-center rounded-lg bg-muted" aria-hidden="true">
              <component :is="item.icon" class="size-4" />
            </div>
            <Badge :class="badge(item.ok).tone">{{ badge(item.ok).label }}</Badge>
          </div>
          <p class="mt-4 text-sm text-muted-foreground">{{ item.title }}</p>
          <p class="mt-1 text-lg font-semibold tracking-tight">{{ item.value }}</p>
          <p class="mt-1 text-xs text-muted-foreground">{{ item.detail }}</p>
        </CardContent>
      </Card>
    </section>

    <Card class="gap-4">
      <CardHeader>
        <CardTitle class="flex items-center gap-2">
          <KeyRound class="size-4 text-muted-foreground" aria-hidden="true" />
          商家密钥
          <Badge :class="keySaved ? TONE_CLASSES.success : TONE_CLASSES.neutral">{{ keySaved ? '已设置' : '未设置' }}</Badge>
        </CardTitle>
        <CardDescription>
          后端配置了 MERCHANT_API_KEY 时，收件箱和看板需要这个密钥。密钥只保存在当前浏览器，不会写进前端代码。
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form class="flex flex-col gap-2 sm:flex-row" @submit.prevent="saveKey">
          <Input
            :model-value="keyInput"
            type="password"
            autocomplete="off"
            placeholder="输入后端配置的商家密钥"
            aria-label="商家密钥"
            class="sm:max-w-sm"
            @update:model-value="(value) => (keyInput = String(value))"
          />
          <div class="flex gap-2">
            <Button type="submit" :disabled="!keyInput.trim()">保存</Button>
            <Button v-if="keySaved" type="button" variant="outline" @click="clearKey">清除</Button>
          </div>
        </form>
      </CardContent>
    </Card>

    <div class="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-4 text-sm">
      <Info class="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <p class="flex-1 leading-relaxed text-muted-foreground">
        状态来自
        <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">GET /api/v1/status</code>
        ，每 30 秒自动检查一次<template v-if="system.checkedAt">，上次检查 {{ clockTime(system.checkedAt, 'zh-CN') }}</template>。
      </p>
      <Button variant="outline" size="sm" @click="system.refresh">
        <RefreshCw />
        立即检查
      </Button>
    </div>
  </div>
</template>
