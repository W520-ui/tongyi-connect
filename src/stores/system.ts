import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

import { publicApi } from '@/api/endpoints'
import { type ApiError, toApiError } from '@/api/errors'
import type { SystemStatus } from '@/api/types'

export const useSystemStore = defineStore('system', () => {
  const status = ref<SystemStatus | null>(null)
  const error = shallowRef<ApiError | null>(null)
  const checkedAt = ref<string | null>(null)

  async function refresh(): Promise<void> {
    try {
      status.value = await publicApi.status()
      error.value = null
    } catch (failure) {
      error.value = toApiError(failure)
    } finally {
      checkedAt.value = new Date().toISOString()
    }
  }

  return { status, error, checkedAt, refresh }
})
