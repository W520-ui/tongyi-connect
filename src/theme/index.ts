import { ref, watch } from 'vue'

const STORAGE_KEY = 'tongyi:console-theme'
const isDark = ref(false)
let restored = false

function restore() {
  if (restored || typeof localStorage === 'undefined') return
  restored = true
  isDark.value = localStorage.getItem(STORAGE_KEY) === 'dark'
  watch(isDark, (value) => localStorage.setItem(STORAGE_KEY, value ? 'dark' : 'light'))
}

/** Dark mode switch for the merchant console; the customer page always stays light. */
export function useConsoleTheme() {
  restore()
  function toggle() {
    isDark.value = !isDark.value
  }
  return { isDark, toggle }
}
