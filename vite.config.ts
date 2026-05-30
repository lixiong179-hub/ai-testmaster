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
    host: '127.0.0.1',
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        timeout: 300000,
        configure: (proxy, _options) => {
          proxy.on('error', (_err, _req, _res) => {
            // 代理错误处理
          })
          // http-proxy 的 proxyTimeout 控制后端响应等待上限
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            if (req.url?.includes('/test-point/import-xmind')) {
              proxyReq.setHeader('Connection', 'keep-alive')
            }
          })
          // 修复 FastAPI 307 重定向绕过代理导致 Authorization 丢失的问题
          proxy.on('proxyRes', (proxyRes, _req, _res) => {
            if (proxyRes.statusCode === 307 || proxyRes.statusCode === 301) {
              const location = proxyRes.headers.location
              if (location && location.includes('127.0.0.1:8000')) {
                proxyRes.headers.location = location.replace(/http:\/\/127\.0\.0\.1:8000/, '')
              }
            }
          })
        },
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        api: 'modern-compiler',
      },
    },
  },
  build: {
    target: 'es2015',
    minify: 'esbuild',
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('echarts')) return 'echarts'
            if (id.includes('element-plus')) return 'element'
            if (id.includes('vue-flow') || id.includes('@vue-flow')) return 'vue-flow'
            if (id.includes('vue') || id.includes('pinia') || id.includes('vue-router')) return 'vendor'
            return 'vendor'
          }
        },
      },
    },
  },
})
