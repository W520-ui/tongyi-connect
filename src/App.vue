<script setup lang="ts">
import { computed, watchEffect } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useConsoleTheme } from '@/theme'

const route = useRoute()
const { isDark } = useConsoleTheme()

// Only the merchant console follows the dark-mode switch; the customer page stays light.
const isConsole = computed(() => route.path.startsWith('/console'))
const dark = computed(() => isConsole.value && isDark.value)

watchEffect(() => {
  document.documentElement.classList.toggle('dark', dark.value)
  document.documentElement.lang = isConsole.value ? 'zh-CN' : 'en'
})
</script>

<template>
  <TooltipProvider :delay-duration="250">
    <RouterView />
  </TooltipProvider>
  <Toaster position="top-center" :theme="dark ? 'dark' : 'light'" />
</template>
