import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: 'ws://backend:8000',
        ws: true,
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/session': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/sessions': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/reset': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})
