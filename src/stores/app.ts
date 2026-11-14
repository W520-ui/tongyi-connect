import { defineStore } from 'pinia'

interface AppState {
  sidebarCollapsed: boolean
  initialized: boolean
}

export const useAppStore = defineStore('app', {
  state: (): AppState => ({
    sidebarCollapsed: false,
    initialized: false,
  }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
    },
    markInitialized() {
      this.initialized = true
    },
  },
})
