import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        timeout: 300000,
        configure: (proxy, options) => {
          proxy.on('error', (err, req, res) => {
            // 代理错误处理
          })
          // http-proxy 的 proxyTimeout 控制后端响应等待上限
          proxy.on('proxyReq', (proxyReq, req, res) => {
            if (req.url?.includes('/test-point/import-xmind')) {
              proxyReq.setHeader('Connection', 'keep-alive')
            }
          })
        },
      },
    },
  },
  build: {
    target: 'es2015',
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          element: ['element-plus'],
          echarts: ['echarts'],
        },
      },
    },
  },
})
