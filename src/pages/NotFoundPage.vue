<script setup lang="ts">
import { NButton, NResult } from 'naive-ui'
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="not-found">
    <NResult status="404" title="页面不存在" description="这个地址没有对应的页面。">
      <template #footer>
        <div class="links">
          <RouterLink to="/console/inbox" custom v-slot="{ navigate }">
            <NButton type="primary" @click="navigate">商家控制台</NButton>
          </RouterLink>
          <RouterLink to="/chat" custom v-slot="{ navigate }">
            <NButton secondary @click="navigate">客户窗口</NButton>
          </RouterLink>
        </div>
      </template>
    </NResult>
  </div>
</template>

<style scoped>
.not-found {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
}

.links {
  display: flex;
  justify-content: center;
  gap: 10px;
}
</style>
