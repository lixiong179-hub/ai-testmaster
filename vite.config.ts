import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { visualizer } from 'rollup-plugin-visualizer'
import legacy from '@vitejs/plugin-legacy'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需引入：
    // - AutoImport 负责自动注入 ElMessage / ElMessageBox / ElNotification / ElLoading 等样式化 API
    // - Components 负责自动注册 <el-*> 模板组件
    // - importStyle: 'css' 按需加载组件对应 CSS，避免整包引入 element-plus/dist/index.css
    AutoImport({
      resolvers: [ElementPlusResolver({ importStyle: 'css' })],
      dts: 'auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver({ importStyle: 'css' })],
      dts: 'components.d.ts',
    }),
    // P2-2: bundle 体积可视化分析（仅 build 时生成）
    visualizer({
      filename: 'dist/stats.html',
      template: 'treemap',
      gzipSize: true,
      brotliSize: true,
    }),
    // P2-1: 旧版浏览器 polyfill（为不支持 ES2020 的浏览器生成兼容 bundle）
    legacy({
      targets: ['defaults', 'not ie 11'],
      modernPolyfills: true,
    }),
  ],
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
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
        // 后端 websocket router 注册在 /api/v1 前缀下，实际路径 /api/v1/ws/...
        // 前端 connectWebSocket 拼接 /ws{path}，需 rewrite 补全 /api/v1 前缀
        rewrite: (path) => path.replace(/^\/ws/, '/api/v1/ws'),
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
    target: 'es2020',
    minify: 'esbuild',
    chunkSizeWarningLimit: 1000,
    // 安全：生产环境禁用 source map，防止源码泄露
    sourcemap: false,
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
