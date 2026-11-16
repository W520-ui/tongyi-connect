import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

import { publicApi } from '@/api/endpoints'
import { type ApiError, toApiError } from '@/api/errors'
import type { Product } from '@/api/types'

export const useCatalogStore = defineStore('catalog', () => {
  const products = ref<Product[]>([])
  const loaded = ref(false)
  const error = shallowRef<ApiError | null>(null)

  async function refresh(): Promise<void> {
    try {
      products.value = await publicApi.products()
      error.value = null
      loaded.value = true
    } catch (failure) {
      error.value = toApiError(failure)
    }
  }

  return { products, loaded, error, refresh }
})
