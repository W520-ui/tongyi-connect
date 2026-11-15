<script setup lang="ts">
import { Activity, ChartColumn, ExternalLink, Inbox, Moon, Package, Sun } from 'lucide-vue-next'
import {
  NBadge,
  NButton,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NTag,
  NTooltip,
  type MenuOption,
} from 'naive-ui'
import { computed, h, ref, type Component } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { systemStatus } from '../fixtures/demo'
import { useInboxStore } from '../stores/inbox'
import { useThemeMode } from '../theme'

const route = useRoute()
const router = useRouter()
const inbox = useInboxStore()
const { isDark, toggle } = useThemeMode()
const collapsed = ref(false)
const status = systemStatus

function icon(component: Component) {
  return () => h(NIcon, null, { default: () => h(component) })
}

const menuOptions = computed<MenuOption[]>(() => [
  {
    key: 'inbox',
    label: '收件箱',
    icon: icon(Inbox),
    extra: () =>
      inbox.counts.open ? h(NBadge, { value: inbox.counts.open, type: 'warning', max: 99 }) : null,
  },
  { key: 'dashboard', label: '数据看板', icon: icon(ChartColumn) },
  { key: 'catalog', label: '商品资料', icon: icon(Package) },
  { key: 'system', label: '系统状态', icon: icon(Activity) },
])

const activeKey = computed(() => String(route.name ?? ''))
const title = computed(() => route.meta.title ?? '')
const subtitle = computed(() => route.meta.subtitle ?? '')

function navigate(key: string) {
  void router.push({ name: key })
}
</script>

<template>
  <NLayout has-sider class="console">
    <NLayoutSider
      bordered
      collapse-mode="width"
      :collapsed-width="72"
      :width="236"
      :collapsed="collapsed"
      show-trigger="bar"
      :native-scrollbar="false"
      @collapse="collapsed = true"
      @expand="collapsed = false"
    >
      <div class="brand" :class="{ 'brand--collapsed': collapsed }">
        <div class="brand-mark" aria-hidden="true">通</div>
        <div v-if="!collapsed" class="brand-copy">
          <strong>通译智联</strong>
          <span>商家控制台</span>
        </div>
      </div>
      <NMenu
        :value="activeKey"
        :options="menuOptions"
        :collapsed="collapsed"
        :collapsed-width="72"
        :collapsed-icon-size="20"
        :icon-size="18"
        @update:value="navigate"
      />
    </NLayoutSider>

    <NLayout class="main">
      <NLayoutHeader bordered class="header">
        <div class="heading">
          <h1>{{ title }}</h1>
          <p>{{ subtitle }}</p>
        </div>
        <div class="header-actions">
          <NTag size="small" :bordered="false" round class="proto-tag">原型 · 演示数据</NTag>
          <span class="model-pill" :class="status.llm_configured ? 'model-pill--ok' : 'model-pill--warn'">
            <i aria-hidden="true" />
            {{ status.llm_configured ? `模型已连接 · ${status.model}` : '模型未配置' }}
          </span>
          <NButton tag="a" href="/chat" target="_blank" size="small" secondary>
            <template #icon><NIcon :component="ExternalLink" /></template>
            客户窗口
          </NButton>
          <NTooltip>
            <template #trigger>
              <NButton quaternary circle :aria-label="isDark ? '切换到浅色' : '切换到深色'" @click="toggle">
                <template #icon><NIcon :component="isDark ? Sun : Moon" /></template>
              </NButton>
            </template>
            {{ isDark ? '切换到浅色' : '切换到深色' }}
          </NTooltip>
        </div>
      </NLayoutHeader>

      <NLayoutContent class="content" :native-scrollbar="false" content-class="content-inner">
        <RouterView />
      </NLayoutContent>
    </NLayout>
  </NLayout>
</template>

<style scoped>
.console {
  height: 100vh;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 64px;
  padding: 0 20px;
}

.brand--collapsed {
  justify-content: center;
  padding: 0;
}

.brand-mark {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 11px;
  color: #fff;
  background: var(--mark-gradient);
  box-shadow: 0 8px 18px -8px rgba(15, 118, 110, 0.65);
  font-size: 16px;
  font-weight: 700;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 1px;
  white-space: nowrap;
}

.brand-copy strong {
  color: var(--text-strong);
  font-size: 15px;
  letter-spacing: 0.02em;
}

.brand-copy span {
  color: var(--text-muted);
  font-size: 12px;
}

.main {
  height: 100vh;
}

.header {
  display: flex;
  height: 64px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 24px;
}

.heading h1 {
  margin: 0;
  color: var(--text-strong);
  font-size: 17px;
  letter-spacing: -0.01em;
}

.heading p {
  margin: 2px 0 0;
  color: var(--text-muted);
  font-size: 12.5px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.proto-tag {
  color: var(--info);
  background: var(--info-soft);
}

.model-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 11px;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--text);
  font-size: 12px;
  white-space: nowrap;
}

.model-pill i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.model-pill--ok i {
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}

.model-pill--warn i {
  background: #f59e0b;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2);
}

.content {
  height: calc(100vh - 64px);
}

.content :deep(.content-inner) {
  min-height: 100%;
  padding: 22px 24px 28px;
}

@media (max-width: 900px) {
  .proto-tag,
  .model-pill {
    display: none;
  }
}
</style>
