import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendPort = Number(process.env.SHIPYARD_BACKEND_PORT || 8100)
const frontendPort = Number(process.env.SHIPYARD_FRONTEND_PORT || 5273)

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: frontendPort,
    strictPort: true,
    proxy: {
      '/api': { target: `http://127.0.0.1:${backendPort}`, changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.js', 'src/**/*.test.js'],
  },
})
