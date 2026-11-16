import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./vitest.setup.ts'],
    // 默认 5s 在全量并行（150+ 文件、Element Plus 组件挂载）时会被争抢 CPU 拖爆，
    // 表现为随机 "Test timed out in 5000ms"；放宽到 15s 只兜底慢挂载，不放宽断言标准。
    testTimeout: 15000,
    hookTimeout: 15000,
    // 12 核机器默认按核数开线程，配合 --coverage 的 v8 插桩会把 esbuild 挤到
    // "fatal error: out of memory"；限制到 4 线程可稳定跑完，也顺带降低超时抖动。
    maxThreads: 4,
    minThreads: 1,
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    include: ['src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    coverage: {
      provider: 'v8',
      // json-summary 供 scripts/check-coverage.mjs 做门槛校验
      reporter: ['text-summary', 'text', 'html', 'lcov', 'json-summary'],
      reportsDirectory: './coverage',
      // 统计未被任何测试导入的文件，避免“只测了热门模块”造成的覆盖率虚高
      all: true,
      // 仅统计 .ts 逻辑代码：v8 对 .vue 单文件组件的行号映射不准，
      // 会把模板/样式计入未覆盖行，导致数字严重失真
      include: ['src/**/*.ts'],
      exclude: [
        'src/**/*.d.ts',
        'src/**/__tests__/**',
        'src/**/*.{spec,test}.ts',
        'src/main.ts',
        'src/types/**',
        'src/**/types.ts',
        'src/test-utils/**',
      ],
      // 门槛不在这里配置：vitest 0.34 的 coverage.thresholds 不会生效，
      // 改由 scripts/check-coverage.mjs 读取 json-summary 报告后校验并阻断
      // （初始门槛 lines 55 / statements 55 / functions 60 / branches 80）
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        api: 'modern-compiler',
      },
    },
  },
})
