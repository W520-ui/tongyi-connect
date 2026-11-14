<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import { useAppStore } from '../stores/app'

const appStore = useAppStore()

onMounted(() => {
  appStore.markInitialized()
})
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--collapsed': appStore.sidebarCollapsed }">
    <aside class="app-sidebar" aria-label="主导航">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">通</div>
        <div v-if="!appStore.sidebarCollapsed" class="brand-copy">
          <strong>通译智联</strong>
          <span>跨境服务工作台</span>
        </div>
      </div>

      <nav class="nav-list">
        <RouterLink class="nav-item" to="/workspace">
          <span class="nav-icon" aria-hidden="true">⌂</span>
          <span v-if="!appStore.sidebarCollapsed">工作台</span>
        </RouterLink>
        <RouterLink class="nav-item" to="/settings">
          <span class="nav-icon" aria-hidden="true">⚙</span>
          <span v-if="!appStore.sidebarCollapsed">设置</span>
        </RouterLink>
      </nav>

      <button
        class="collapse-button"
        type="button"
        :aria-label="appStore.sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
        @click="appStore.toggleSidebar"
      >
        <span aria-hidden="true">{{ appStore.sidebarCollapsed ? '→' : '←' }}</span>
        <span v-if="!appStore.sidebarCollapsed">收起菜单</span>
      </button>
    </aside>

    <div class="app-main">
      <header class="app-header">
        <div>
          <span class="header-eyebrow">AI 跨境服务平台</span>
          <h1 class="header-title">通译智联</h1>
        </div>
        <div class="header-status">
          <span class="status-dot" aria-hidden="true"></span>
          <span>系统框架已就绪</span>
        </div>
      </header>

      <main class="app-content">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
}

.app-sidebar {
  display: flex;
  width: 248px;
  flex: 0 0 248px;
  flex-direction: column;
  padding: 24px 16px 18px;
  color: #d0d5dd;
  background: #101828;
  transition: width 180ms ease, flex-basis 180ms ease;
}

.app-shell--collapsed .app-sidebar {
  width: 76px;
  flex-basis: 76px;
}

.brand {
  display: flex;
  align-items: center;
  min-height: 44px;
  gap: 12px;
  padding: 0 8px;
}

.brand-mark {
  display: grid;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  place-items: center;
  border-radius: 10px;
  color: #fff;
  font-weight: 700;
  background: #2563eb;
}

.brand-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.brand-copy strong {
  color: #f9fafb;
  font-size: 16px;
}

.brand-copy span,
.header-eyebrow {
  color: #98a2b3;
  font-size: 12px;
}

.nav-list {
  display: grid;
  gap: 6px;
  margin-top: 44px;
}

.nav-item {
  display: flex;
  align-items: center;
  min-height: 42px;
  gap: 12px;
  padding: 0 12px;
  border-radius: 8px;
  color: #98a2b3;
  font-size: 14px;
  text-decoration: none;
  transition: color 160ms ease, background 160ms ease;
}

.nav-item:hover,
.nav-item.router-link-active {
  color: #fff;
  background: rgb(37 99 235 / 24%);
}

.nav-icon {
  width: 18px;
  flex: 0 0 18px;
  text-align: center;
  font-size: 17px;
}

.collapse-button {
  display: flex;
  align-items: center;
  margin-top: auto;
  gap: 12px;
  padding: 10px 12px;
  border: 0;
  border-radius: 8px;
  color: #98a2b3;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  text-align: left;
}

.collapse-button:hover {
  color: #fff;
  background: rgb(255 255 255 / 8%);
}

.app-main {
  min-width: 0;
  flex: 1;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 84px;
  padding: 18px clamp(20px, 4vw, 48px);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.header-eyebrow {
  display: block;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.header-title {
  margin: 4px 0 0;
  color: var(--color-text);
  font-size: 20px;
  line-height: 1.2;
}

.header-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #12b76a;
  box-shadow: 0 0 0 4px #ecfdf3;
}

.app-content {
  max-width: 1440px;
  margin: 0 auto;
  padding: clamp(24px, 4vw, 48px);
}

@media (max-width: 700px) {
  .app-sidebar {
    width: 68px;
    flex-basis: 68px;
    padding-inline: 10px;
  }

  .app-shell--collapsed .app-sidebar {
    width: 68px;
    flex-basis: 68px;
  }

  .brand {
    justify-content: center;
    padding-inline: 0;
  }

  .nav-item,
  .collapse-button {
    justify-content: center;
    padding-inline: 0;
  }

  .header-status {
    display: none;
  }
}
</style>
