<script setup lang="ts">
import { CircleAlert, CircleCheck, Hand, MessagesSquare, Sparkles } from '@lucide/vue'
import { computed } from 'vue'

import type { RecentInquiry } from '@/api/types'
import KpiCard from '@/components/console/KpiCard.vue'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { usePolling } from '@/composables/usePolling'
import { TONE_CLASSES, type Tone } from '@/labels'
import { useDashboardStore } from '@/stores/dashboard'
import { fromNow } from '@/utils/time'

const LANGUAGE_COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)']

const dashboard = useDashboardStore()
usePolling(dashboard.refresh, 10_000)

const overview = computed(() => dashboard.overview)
const intents = computed(() => overview.value?.intents ?? [])
const intentMax = computed(() => Math.max(1, ...intents.value.map((item) => item.count)))
const languageCount = computed(() => (overview.value?.languages ?? []).reduce((sum, item) => sum + item.count, 0))

const languages = computed(() =>
  (overview.value?.languages ?? []).map((item, index) => ({
    ...item,
    color: LANGUAGE_COLORS[index % LANGUAGE_COLORS.length] ?? 'var(--chart-4)',
    share: Math.round((item.count / (languageCount.value || 1)) * 100),
  })),
)

// Solid segments with hard stops, so the donut stays flat (no blending).
const donutStyle = computed(() => {
  if (!languageCount.value) return { background: 'var(--muted)' }
  let start = 0
  const stops = languages.value.map((item) => {
    const end = start + (item.count / languageCount.value) * 360
    const stop = `${item.color} ${start}deg ${end}deg`
    start = end
    return stop
  })
  return { background: `conic-gradient(${stops.join(', ')})` }
})

const kpi = (value: number | string | undefined) => (value === undefined ? '—' : value)

// RecentInquiry only says whether a merchant took over, not whether the ticket
// is resolved yet, so "已转人工" covers both.
function inquiryStatus(row: RecentInquiry): { label: string; tone: Tone } {
  if (!row.needs_human) return { label: '自动完成', tone: 'success' }
  if (row.human_acknowledged) return { label: '已转人工', tone: 'info' }
  return { label: '待接管', tone: 'warning' }
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <div
      v-if="dashboard.error"
      class="flex items-start gap-2.5 rounded-xl border bg-card px-4 py-3 text-sm"
      role="alert"
    >
      <CircleAlert class="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
      <p class="text-muted-foreground">
        看板数据刷新失败：{{ dashboard.error.message }}
        <template v-if="overview">（下面显示的是上一次成功获取的数据）</template>
      </p>
    </div>

    <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard
        label="累计咨询"
        :value="kpi(overview?.total_conversations)"
        caption="每条客户消息记一次，不含指令"
        :icon="MessagesSquare"
      />
      <KpiCard
        label="自动解决率"
        :value="overview ? `${overview.resolution_rate}%` : '—'"
        caption="不需要人工就完成的咨询"
        :icon="CircleCheck"
      />
      <KpiCard label="待接管" :value="kpi(overview?.pending_handoffs)" caption="等待商家处理的工单" :icon="Hand" />
      <KpiCard label="热门意图" :value="kpi(overview?.top_intent)" caption="按咨询次数排名第一" :icon="Sparkles" />
    </section>

    <section class="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
      <Card>
        <CardHeader>
          <CardTitle>咨询意图分布</CardTitle>
          <CardDescription>一条咨询可能同时包含多个意图</CardDescription>
        </CardHeader>
        <CardContent class="flex flex-col gap-3.5">
          <p v-if="!intents.length" class="py-6 text-center text-sm text-muted-foreground">暂无数据</p>
          <div
            v-for="item in intents"
            :key="item.code"
            class="grid grid-cols-[72px_minmax(0,1fr)_40px] items-center gap-3 text-sm"
          >
            <span class="text-muted-foreground">{{ item.label }}</span>
            <div class="h-2 overflow-hidden rounded-full bg-muted">
              <div class="h-full rounded-full bg-chart-1" :style="{ width: `${Math.max(4, (item.count / intentMax) * 100)}%` }" />
            </div>
            <span class="text-right font-medium tabular-nums">{{ item.count }}</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>客户语言</CardTitle>
          <CardDescription>按咨询时使用的语言统计</CardDescription>
        </CardHeader>
        <CardContent class="flex flex-col items-center gap-6 sm:flex-row">
          <div class="grid size-36 shrink-0 place-items-center rounded-full" :style="donutStyle" role="img" aria-label="客户语言分布">
            <div class="flex size-24 flex-col items-center justify-center rounded-full bg-card">
              <span class="text-2xl font-semibold tabular-nums">{{ languageCount }}</span>
              <span class="text-xs text-muted-foreground">条咨询</span>
            </div>
          </div>
          <p v-if="!languages.length" class="w-full text-center text-sm text-muted-foreground">暂无数据</p>
          <ul v-else class="flex w-full flex-col gap-3 text-sm">
            <li v-for="item in languages" :key="item.code" class="grid grid-cols-[10px_minmax(0,1fr)_auto_44px] items-center gap-2.5">
              <span class="size-2.5 rounded-[3px]" :style="{ background: item.color }" aria-hidden="true" />
              <span class="text-muted-foreground">{{ item.label }}</span>
              <span class="font-medium tabular-nums">{{ item.count }}</span>
              <span class="text-right text-muted-foreground tabular-nums">{{ item.share }}%</span>
            </li>
          </ul>
        </CardContent>
      </Card>
    </section>

    <Card class="gap-4">
      <CardHeader>
        <CardTitle>最近咨询</CardTitle>
        <CardDescription>最新的客户消息与处理结果</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead class="w-24">时间</TableHead>
              <TableHead class="w-24">语言</TableHead>
              <TableHead class="w-28">意图</TableHead>
              <TableHead>客户消息</TableHead>
              <TableHead class="w-28 text-right">状态</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="!dashboard.recent.length">
              <TableCell colspan="5" class="py-8 text-center text-muted-foreground">暂无咨询</TableCell>
            </TableRow>
            <TableRow v-for="row in dashboard.recent" :key="row.id">
              <TableCell class="text-muted-foreground">{{ fromNow(row.created_at) }}</TableCell>
              <TableCell>{{ row.language_label }}</TableCell>
              <TableCell><Badge variant="outline" class="font-normal">{{ row.intent_label }}</Badge></TableCell>
              <TableCell class="max-w-0 truncate" :title="row.message">{{ row.message }}</TableCell>
              <TableCell class="text-right">
                <Badge :class="TONE_CLASSES[inquiryStatus(row).tone]">{{ inquiryStatus(row).label }}</Badge>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  </div>
</template>
