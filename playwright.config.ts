import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e-playwright',
  timeout: 30000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:3001',
    headless: true,
    channel: 'chrome',
    viewport: { width: 1440, height: 900 },
    actionTimeout: 10000,
    locale: 'zh-CN',
  },
})
