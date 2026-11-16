/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base path; defaults to same-origin `/api` (the dev server proxies it to FastAPI). */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
