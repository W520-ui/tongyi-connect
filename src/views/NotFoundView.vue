<script setup lang="ts">
import { RouterLink } from 'vue-router'

import AppShell from '../layouts/AppShell.vue'
</script>

<template>
  <AppShell>
    <section class="not-found" aria-labelledby="not-found-title">
      <span>404</span>
      <h2 id="not-found-title">页面不存在</h2>
      <RouterLink to="/workspace">返回工作台</RouterLink>
    </section>
  </AppShell>
</template>

<style scoped>
.not-found {
  max-width: 560px;
  margin: 14vh auto 0;
  padding: 56px 32px;
  border: 1px solid var(--color-border);
  border-radius: 20px;
  background: var(--color-surface);
  text-align: center;
}

.not-found > span {
  color: var(--color-primary);
  font-size: 56px;
  font-weight: 700;
}

h2 {
  margin: 12px 0 24px;
  color: var(--color-text);
}

a {
  color: var(--color-primary);
  text-decoration: none;
}
</style>
