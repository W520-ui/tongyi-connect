import { useDocumentVisibility, useIntervalFn } from '@vueuse/core'
import { type MaybeRefOrGetter, toValue, watch } from 'vue'

/**
 * Runs `task` right away and then every `intervalMs` while `enabled`, pausing
 * while the browser tab is hidden (A.7: lists refresh every 10 s, not in the
 * background). Overlapping runs are skipped. Stops with the calling component.
 */
export function usePolling(
  task: () => unknown,
  intervalMs: number,
  enabled: MaybeRefOrGetter<boolean> = true,
): { refresh: () => Promise<void> } {
  const visibility = useDocumentVisibility()
  let running = false

  async function refresh(): Promise<void> {
    if (running) return
    running = true
    try {
      await task()
    } finally {
      running = false
    }
  }

  const { pause, resume } = useIntervalFn(refresh, intervalMs, { immediate: false })
  watch(
    () => toValue(enabled) && visibility.value === 'visible',
    (active) => {
      if (active) {
        void refresh()
        resume()
      } else {
        pause()
      }
    },
    { immediate: true },
  )

  return { refresh }
}
