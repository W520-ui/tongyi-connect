<script setup lang="ts">
import { Cpu, Database, Info, Server } from '@lucide/vue'
import type { Component } from 'vue'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { systemStatus } from '@/fixtures/demo'
import { TONE_CLASSES } from '@/labels'

interface StatusItem {
  title: string
  icon: Component
  ok: boolean
  value: string
  detail: string
}

const items: StatusItem[] = [
  {
    title: '后端 API',
    icon: Server,
    ok: true,
    value: `版本 ${systemStatus.version}`,
    detail: 'FastAPI 服务，接口契约 v0.1',
  },
  {
    title: '对话模型',
    icon: Cpu,
    ok: systemStatus.llm_configured,
    value: systemStatus.llm_configured ? (systemStatus.model ?? '已配置') : '未配置',
    detail: systemStatus.llm_configured ? 'OpenAI 兼容接口，密钥只保存在后端' : '后端还没有配置模型密钥',
  },
  {
    title: '数据库',
    icon: Database,
    ok: systemStatus.db_ok,
    value: systemStatus.db_ok ? '连接正常' : '无法连接',
    detail: '会话、消息、工单与运行轨迹',
  },
]
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
            <Badge :class="TONE_CLASSES[item.ok ? 'success' : 'warning']">{{ item.ok ? '正常' : '需要处理' }}</Badge>
          </div>
          <p class="mt-4 text-sm text-muted-foreground">{{ item.title }}</p>
          <p class="mt-1 text-lg font-semibold tracking-tight">{{ item.value }}</p>
          <p class="mt-1 text-xs text-muted-foreground">{{ item.detail }}</p>
        </CardContent>
      </Card>
    </section>

    <div class="flex items-start gap-3 rounded-xl border bg-card p-4 text-sm">
      <Info class="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <p class="leading-relaxed text-muted-foreground">
        当前是视觉原型，页面上的数据来自前端内置的演示数据。接上模拟后端（阶段 V2）以后，这里会显示
        <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">GET /api/v1/status</code>
        返回的真实状态。
      </p>
    </div>
  </div>
</template>
