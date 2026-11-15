<script setup lang="ts">
import { Cpu, Database, Info, Server } from 'lucide-vue-next'
import { NCard, NIcon, NTag } from 'naive-ui'
import type { Component } from 'vue'

import { systemStatus } from '../../fixtures/demo'

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
  <div class="system">
    <section class="status-grid">
      <NCard v-for="item in items" :key="item.title" :bordered="false" class="status">
        <div class="status-top">
          <span class="status-icon" :class="{ 'status-icon--bad': !item.ok }" aria-hidden="true">
            <NIcon :size="20" :component="item.icon" />
          </span>
          <NTag size="small" :bordered="false" :type="item.ok ? 'success' : 'warning'">
            {{ item.ok ? '正常' : '需要处理' }}
          </NTag>
        </div>
        <h3>{{ item.title }}</h3>
        <strong>{{ item.value }}</strong>
        <p>{{ item.detail }}</p>
      </NCard>
    </section>

    <NCard :bordered="false" class="note">
      <div class="note-body">
        <NIcon :size="18" :component="Info" aria-hidden="true" />
        <p>
          当前是视觉原型，页面上的数据来自前端内置的演示数据。接上模拟后端（阶段 V2）以后，这里会显示
          <span class="mono">GET /api/v1/status</span> 返回的真实状态。
        </p>
      </div>
    </NCard>
  </div>
</template>

<style scoped>
.system {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.status,
.note {
  box-shadow: var(--shadow-card);
}

.status-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.status-icon {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 12px;
  color: var(--brand);
  background: var(--brand-soft);
}

.status-icon--bad {
  color: var(--warn);
  background: var(--warn-soft);
}

.status h3 {
  margin: 16px 0 4px;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
}

.status strong {
  color: var(--text-strong);
  font-size: 20px;
  letter-spacing: -0.01em;
}

.status p {
  margin: 6px 0 0;
  color: var(--text-faint);
  font-size: 12.5px;
}

.note-body {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: var(--info);
}

.note-body p {
  margin: 0;
  color: var(--text);
  font-size: 13px;
  line-height: 1.7;
}
</style>
