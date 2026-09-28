import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // built to live under /slicktrace/ - the backend accepts it with or without that prefix
  base: '/slicktrace/',
  server: {
    proxy: {
      '/slicktrace/api': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
    },
  },
})
