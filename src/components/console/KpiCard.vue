<script setup lang="ts">
import { NCard, NIcon } from 'naive-ui'
import type { Component } from 'vue'

defineProps<{
  label: string
  value: string | number
  caption: string
  icon: Component
  tone: 'teal' | 'green' | 'amber' | 'indigo'
}>()
</script>

<template>
  <NCard :bordered="false" class="kpi" :class="`kpi--${tone}`">
    <div class="kpi-top">
      <span class="kpi-label">{{ label }}</span>
      <span class="kpi-icon" aria-hidden="true"><NIcon :size="18" :component="icon" /></span>
    </div>
    <div class="kpi-value">{{ value }}</div>
    <div class="kpi-caption">{{ caption }}</div>
  </NCard>
</template>

<style scoped>
.kpi {
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-card);
}

.kpi::after {
  position: absolute;
  top: -40px;
  right: -40px;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: var(--tone-soft);
  content: '';
  filter: blur(2px);
  opacity: 0.6;
}

.kpi--teal {
  --tone: #0f766e;
  --tone-soft: rgba(20, 184, 166, 0.14);
}

.kpi--green {
  --tone: #16a34a;
  --tone-soft: rgba(34, 197, 94, 0.14);
}

.kpi--amber {
  --tone: #d97706;
  --tone-soft: rgba(245, 158, 11, 0.16);
}

.kpi--indigo {
  --tone: #4f46e5;
  --tone-soft: rgba(99, 102, 241, 0.14);
}

.kpi-top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kpi-label {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
}

.kpi-icon {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 10px;
  color: var(--tone);
  background: var(--tone-soft);
}

.kpi-value {
  position: relative;
  z-index: 1;
  margin-top: 14px;
  color: var(--text-strong);
  font-size: 30px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
}

.kpi-caption {
  position: relative;
  z-index: 1;
  margin-top: 6px;
  color: var(--text-faint);
  font-size: 12px;
}
</style>
