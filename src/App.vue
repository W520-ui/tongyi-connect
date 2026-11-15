<script setup lang="ts">
import { NConfigProvider, NGlobalStyle, NMessageProvider, dateEnUS, dateZhCN, enUS, zhCN } from 'naive-ui'
import { computed, watchEffect } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import { themeFor, useThemeMode } from './theme'

const route = useRoute()
const { isDark } = useThemeMode()

// Only the merchant console follows the dark-mode switch; the customer page stays light.
const isConsole = computed(() => route.path.startsWith('/console'))
const dark = computed(() => isConsole.value && isDark.value)
const themeConfig = computed(() => themeFor(dark.value))
const locale = computed(() => (isConsole.value ? zhCN : enUS))
const dateLocale = computed(() => (isConsole.value ? dateZhCN : dateEnUS))

watchEffect(() => {
  document.documentElement.dataset.theme = dark.value ? 'dark' : 'light'
})
</script>

<template>
  <NConfigProvider
    :theme="themeConfig.theme"
    :theme-overrides="themeConfig.overrides"
    :locale="locale"
    :date-locale="dateLocale"
  >
    <NGlobalStyle />
    <NMessageProvider>
      <RouterView />
    </NMessageProvider>
  </NConfigProvider>
</template>
