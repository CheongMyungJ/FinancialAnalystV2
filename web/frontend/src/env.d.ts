/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DATA_MODE?: 'api' | 'static'
  readonly VITE_GITHUB_REPO?: string
  readonly VITE_ROUTER_MODE?: 'browser' | 'hash'
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

