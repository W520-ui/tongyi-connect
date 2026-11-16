import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

import { merchantApi } from '@/api/endpoints'
import { type ApiError, toApiError } from '@/api/errors'
import type { DashboardOverview, RecentInquiry } from '@/api/types'

export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref<DashboardOverview | null>(null)
  const recent = ref<RecentInquiry[]>([])
  const error = shallowRef<ApiError | null>(null)
  const updatedAt = ref<string | null>(null)

  async function refresh(): Promise<void> {
    try {
      const [summary, latest] = await Promise.all([merchantApi.overview(), merchantApi.recent(8)])
      overview.value = summary
      recent.value = latest
      error.value = null
      updatedAt.value = new Date().toISOString()
    } catch (failure) {
      error.value = toApiError(failure)
    }
  }

  return { overview, recent, error, updatedAt, refresh }
})
