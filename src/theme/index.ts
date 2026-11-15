import { darkTheme, useOsTheme, type GlobalThemeOverrides } from 'naive-ui'
import { computed, ref, watch } from 'vue'

const FONT_FAMILY =
  "'Inter Variable', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', system-ui, -apple-system, 'Segoe UI', sans-serif"
const FONT_FAMILY_MONO = "'JetBrains Mono', 'Cascadia Code', Consolas, 'SFMono-Regular', monospace"

export const lightOverrides: GlobalThemeOverrides = {
  common: {
    fontFamily: FONT_FAMILY,
    fontFamilyMono: FONT_FAMILY_MONO,
    primaryColor: '#0F766E',
    primaryColorHover: '#0D9488',
    primaryColorPressed: '#115E59',
    primaryColorSuppl: '#0D9488',
    infoColor: '#4F46E5',
    infoColorHover: '#6366F1',
    infoColorPressed: '#4338CA',
    infoColorSuppl: '#6366F1',
    successColor: '#16A34A',
    successColorHover: '#22C55E',
    successColorPressed: '#15803D',
    successColorSuppl: '#22C55E',
    warningColor: '#D97706',
    warningColorHover: '#F59E0B',
    warningColorPressed: '#B45309',
    warningColorSuppl: '#F59E0B',
    errorColor: '#DC2626',
    errorColorHover: '#EF4444',
    errorColorPressed: '#B91C1C',
    errorColorSuppl: '#EF4444',
    bodyColor: '#F4F6F8',
    borderColor: '#E3E8EE',
    dividerColor: '#EDF1F5',
    borderRadius: '10px',
    borderRadiusSmall: '6px',
    fontWeightStrong: '600',
  },
  Card: { borderRadius: '16px', borderColor: '#E7ECF1' },
  Button: { fontWeight: '600' },
  Tag: { borderRadius: '999px' },
  Layout: {
    color: '#F4F6F8',
    siderColor: '#FFFFFF',
    headerColor: '#FFFFFF',
    siderBorderColor: '#E7ECF1',
    headerBorderColor: '#E7ECF1',
  },
  Menu: {
    borderRadius: '10px',
    itemHeight: '42px',
    itemColorActive: 'rgba(15, 118, 110, 0.09)',
    itemColorActiveHover: 'rgba(15, 118, 110, 0.12)',
    itemTextColorActive: '#0F766E',
    itemTextColorActiveHover: '#0F766E',
    itemIconColorActive: '#0F766E',
    itemIconColorActiveHover: '#0F766E',
  },
  DataTable: { thColor: '#F8FAFC', thFontWeight: '600', borderRadius: '12px' },
}

export const darkOverrides: GlobalThemeOverrides = {
  common: {
    fontFamily: FONT_FAMILY,
    fontFamilyMono: FONT_FAMILY_MONO,
    primaryColor: '#2DD4BF',
    primaryColorHover: '#5EEAD4',
    primaryColorPressed: '#14B8A6',
    primaryColorSuppl: '#5EEAD4',
    infoColor: '#818CF8',
    infoColorHover: '#A5B4FC',
    infoColorPressed: '#6366F1',
    infoColorSuppl: '#A5B4FC',
    warningColor: '#FBBF24',
    warningColorHover: '#FCD34D',
    warningColorPressed: '#F59E0B',
    warningColorSuppl: '#FCD34D',
    bodyColor: '#0B1120',
    cardColor: '#111827',
    modalColor: '#111827',
    popoverColor: '#1F2937',
    borderColor: '#1F2A3A',
    dividerColor: '#1A2433',
    borderRadius: '10px',
    borderRadiusSmall: '6px',
    fontWeightStrong: '600',
  },
  Card: { borderRadius: '16px', borderColor: '#1F2A3A' },
  Button: { fontWeight: '600' },
  Tag: { borderRadius: '999px' },
  Layout: {
    color: '#0B1120',
    siderColor: '#0F172A',
    headerColor: '#0F172A',
    siderBorderColor: '#1E293B',
    headerBorderColor: '#1E293B',
  },
  Menu: {
    borderRadius: '10px',
    itemHeight: '42px',
    itemColorActive: 'rgba(45, 212, 191, 0.12)',
    itemColorActiveHover: 'rgba(45, 212, 191, 0.16)',
    itemTextColorActive: '#5EEAD4',
    itemTextColorActiveHover: '#5EEAD4',
    itemIconColorActive: '#5EEAD4',
    itemIconColorActiveHover: '#5EEAD4',
  },
  DataTable: { thColor: '#0F172A', thFontWeight: '600', borderRadius: '12px' },
}

export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'tongyi:console-theme'
const mode = ref<ThemeMode>('light')
let restored = false

function restoreMode() {
  if (restored || typeof localStorage === 'undefined') return
  restored = true
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'light' || saved === 'dark' || saved === 'system') mode.value = saved
  watch(mode, (value) => localStorage.setItem(STORAGE_KEY, value))
}

/** Console theme mode; must be called from a component setup. */
export function useThemeMode() {
  restoreMode()
  const osTheme = useOsTheme()
  const isDark = computed(
    () => mode.value === 'dark' || (mode.value === 'system' && osTheme.value === 'dark'),
  )
  function toggle() {
    mode.value = isDark.value ? 'light' : 'dark'
  }
  return { mode, isDark, toggle }
}

export function themeFor(isDark: boolean) {
  return isDark
    ? { theme: darkTheme, overrides: darkOverrides }
    : { theme: null, overrides: lightOverrides }
}
