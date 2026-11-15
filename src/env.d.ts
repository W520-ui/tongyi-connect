/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base path; defaults to same-origin `/api`. */
  readonly VITE_API_BASE_URL?: string
  /** Demo-only merchant key placeholder (see API contract A.0). */
  readonly VITE_MERCHANT_API_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
