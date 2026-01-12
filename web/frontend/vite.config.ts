import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // For GitHub Pages project sites, set VITE_BASE="/<repo>/" in CI.
  // Default "/" keeps local dev working.
  base: process.env.VITE_BASE ?? '/',
  server: {
    proxy: {
      '/api': {
        // NOTE: Some Windows environments can have port 8000 stuck in LISTENING state.
        // We default to 8001 for local dev; override via VITE_PROXY_TARGET if needed.
        target: process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
})
