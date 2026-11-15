<script setup lang="ts">
import { CircleCheck, Hand, MessagesSquare, Sparkles } from 'lucide-vue-next'
import { NCard, NDataTable, NTag, type DataTableColumns } from 'naive-ui'
import { computed, h } from 'vue'

import type { RecentInquiry } from '../../api/types'
import KpiCard from '../../components/console/KpiCard.vue'
import { overview, recentInquiries } from '../../fixtures/demo'
import { fromNow } from '../../utils/time'

const LANGUAGE_COLORS = ['#0f766e', '#6366f1', '#f59e0b', '#ec4899']

const intentMax = computed(() => Math.max(1, ...overview.intents.map((item) => item.count)))
const languageTotal = computed(() => overview.languages.reduce((sum, item) => sum + item.count, 0) || 1)

const languages = computed(() =>
  overview.languages.map((item, index) => ({
    ...item,
    color: LANGUAGE_COLORS[index % LANGUAGE_COLORS.length] ?? '#94a3b8',
    share: Math.round((item.count / languageTotal.value) * 100),
  })),
)

const donutStyle = computed(() => {
  let start = 0
  const stops = languages.value.map((item) => {
    const end = start + (item.count / languageTotal.value) * 360
    const stop = `${item.color} ${start}deg ${end}deg`
    start = end
    return stop
  })
  return { background: `conic-gradient(${stops.join(', ')})` }
})

function statusTag(row: RecentInquiry) {
  if (!row.needs_human) return h(NTag, { size: 'small', bordered: false, type: 'success' }, { default: () => '自动完成' })
  if (row.human_acknowledged) return h(NTag, { size: 'small', bordered: false, type: 'info' }, { default: () => '人工处理中' })
  return h(NTag, { size: 'small', bordered: false, type: 'warning' }, { default: () => '待接管' })
}

const columns: DataTableColumns<RecentInquiry> = [
  { title: '时间', key: 'created_at', width: 96, render: (row) => fromNow(row.created_at) },
  { title: '语言', key: 'language_label', width: 92 },
  {
    title: '意图',
    key: 'intent_label',
    width: 104,
    render: (row) => h(NTag, { size: 'small', bordered: false }, { default: () => row.intent_label }),
  },
  { title: '客户消息', key: 'message', ellipsis: { tooltip: true } },
  { title: '状态', key: 'needs_human', width: 110, render: statusTag },
]
</script>

<template>
  <div class="dashboard">
    <section class="kpis">
      <KpiCard
        label="累计咨询"
        :value="overview.total_conversations"
        caption="每条客户消息记一次"
        :icon="MessagesSquare"
        tone="teal"
      />
      <KpiCard
        label="自动解决率"
        :value="`${overview.resolution_rate}%`"
        caption="不需要人工就完成的咨询"
        :icon="CircleCheck"
        tone="green"
      />
      <KpiCard
        label="待接管"
        :value="overview.pending_handoffs"
        caption="等待商家处理的工单"
        :icon="Hand"
        tone="amber"
      />
      <KpiCard label="热门意图" :value="overview.top_intent" caption="按咨询次数排名第一" :icon="Sparkles" tone="indigo" />
    </section>

    <section class="charts">
      <NCard :bordered="false" title="咨询意图分布" class="card">
        <div class="bars">
          <div v-for="item in overview.intents" :key="item.code" class="bar-row">
            <span class="bar-label">{{ item.label }}</span>
            <div class="bar-track">
              <i :style="{ width: `${Math.max(6, (item.count / intentMax) * 100)}%` }" />
            </div>
            <span class="bar-value">{{ item.count }}</span>
          </div>
        </div>
      </NCard>

      <NCard :bordered="false" title="客户语言" class="card">
        <div class="languages">
          <div class="donut" :style="donutStyle" role="img" aria-label="客户语言分布">
            <div class="donut-hole">
              <strong>{{ languageTotal }}</strong>
              <span>条咨询</span>
            </div>
          </div>
          <ul class="legend">
            <li v-for="item in languages" :key="item.code">
              <i :style="{ background: item.color }" aria-hidden="true" />
              <span class="legend-label">{{ item.label }}</span>
              <span class="legend-value">{{ item.count }}</span>
              <span class="legend-share">{{ item.share }}%</span>
            </li>
          </ul>
        </div>
      </NCard>
    </section>

    <NCard :bordered="false" title="最近咨询" class="card">
      <NDataTable :columns="columns" :data="recentInquiries" :bordered="false" size="small" :row-key="(row: RecentInquiry) => row.id" />
    </NCard>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.charts {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
  gap: 16px;
}

.card {
  box-shadow: var(--shadow-card);
}

.bars {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 4px;
}

.bar-row {
  display: grid;
  align-items: center;
  grid-template-columns: 72px minmax(0, 1fr) 36px;
  gap: 12px;
  font-size: 13px;
}

.bar-label {
  color: var(--text);
}

.bar-track {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--surface-sunken);
}

.bar-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0f766e 0%, #2dd4bf 100%);
}

.bar-value {
  color: var(--text-strong);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  text-align: right;
}

.languages {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 4px 4px 0;
}

.donut {
  display: grid;
  width: 148px;
  height: 148px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
}

.donut-hole {
  display: flex;
  width: 98px;
  height: 98px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: inset 0 0 0 1px var(--line);
}

.donut-hole strong {
  color: var(--text-strong);
  font-size: 22px;
  font-variant-numeric: tabular-nums;
}

.donut-hole span {
  color: var(--text-faint);
  font-size: 11.5px;
}

.legend {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.legend li {
  display: grid;
  align-items: center;
  grid-template-columns: 10px minmax(0, 1fr) auto 44px;
  gap: 10px;
  font-size: 13px;
}

.legend i {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}

.legend-label {
  color: var(--text);
}

.legend-value {
  color: var(--text-strong);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.legend-share {
  color: var(--text-faint);
  font-variant-numeric: tabular-nums;
  text-align: right;
}

@media (max-width: 1200px) {
  .kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .charts {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .kpis {
    grid-template-columns: 1fr;
  }

  .languages {
    flex-direction: column;
  }
}
</style>
