import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Morphix 控制台（根级 morphix-console）开发服务器配置。
// 前端运行于 5173，所有 /api 请求代理到 canonical 后端（project/backend，端口 2181）。
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5183,
    strictPort: true,
    open: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:2181',
        changeOrigin: true,
      },
    },
  },
})
