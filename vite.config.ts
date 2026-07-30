import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Morphix 控制台（根级 morphix-console）开发服务器配置。
// 前端运行于 5183，所有 /api 请求代理到 canonical 后端（project/backend，端口 2183）。
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5183,
    strictPort: true,
    open: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:2183',
        changeOrigin: true,
      },
    },
    allowedHosts: ['localhost', '127.0.0.1', '192.168.2.111'],
  },
})
