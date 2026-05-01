import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Inside Docker: frontend-dev → backend:8000
// Outside Docker (local dev): fallback to localhost:8000
const BACKEND = process.env.BACKEND_URL || 'http://backend:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/ws': {
        target: BACKEND.replace('http', 'ws'),
        ws: true,
        changeOrigin: true,
      },
      '/auth': {
        target: BACKEND,
        changeOrigin: true,
      },
      '/sessions': {
        target: BACKEND,
        changeOrigin: true,
      },
      '/voice': {
        target: BACKEND,
        changeOrigin: true,
      },
      '/warmup': {
        target: BACKEND,
        changeOrigin: true,
      },
      '/health': {
        target: BACKEND,
        changeOrigin: true,
      },
      '/admin': {
        target: BACKEND,
        changeOrigin: true,
      },
    },
  },
})
