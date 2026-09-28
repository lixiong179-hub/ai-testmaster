/**
 * 全局错误处理
 *
 * 1. app.config.errorHandler 捕获组件内未处理异常，避免白屏崩溃
 * 2. window error/unhandledrejection 捕获脚本级与 Promise 级异常
 * 3. 通过 ElMessage 统一展示，同时在开发环境输出 console
 */
import type { App } from 'vue'

type VueError = Error & { info?: string }

/** 已展示过的错误消息去重（避免同一错误弹多次） */
const shownMessages = new Set<string>()
const DEDUP_WINDOW_MS = 3000

function shouldShow(message: string): boolean {
  const key = message.substring(0, 100)
  if (shownMessages.has(key)) return false
  shownMessages.add(key)
  setTimeout(() => shownMessages.delete(key), DEDUP_WINDOW_MS)
  return true
}

function notifyUser(message: string): void {
  if (!shouldShow(message)) return
  // 延迟 import 避免循环依赖（ElMessage 依赖 auto-import 注入的样式）
  import('element-plus')
    .then(({ ElMessage }) => {
      ElMessage.error(message)
    })
    .catch(() => {
      // ElMessage 加载失败时降级到 console
      console.error('[UI Error]', message)
    })
}

/**
 * 注册全局错误处理器到 Vue 应用实例
 */
export function setupGlobalErrorHandler(app: App): void {
  // Vue 组件渲染/生命周期/事件回调中的未捕获错误
  app.config.errorHandler = (err: unknown, _instance, info) => {
    const error = err as VueError
    const message = error?.message || '页面渲染异常，请刷新页面重试'
    if (import.meta.env.DEV) {
      console.error('[Vue Error]', err, '\nInfo:', info)
    }
    notifyUser(message)
  }

  // 脚本级未捕获错误（资源加载失败、语法错误等）
  window.addEventListener('error', (event) => {
    // 忽略资源加载错误（由元素自身的 onerror 处理）
    if (event.target && event.target !== window) return
    const message = event.message || '未知脚本错误'
    if (import.meta.env.DEV) {
      console.error('[Window Error]', event.error || message)
    }
    notifyUser(message)
  })

  // Promise 未捕获的 reject
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason
    const message =
      (reason as Error)?.message ||
      (typeof reason === 'string' ? reason : '异步操作异常')
    if (import.meta.env.DEV) {
      console.error('[Unhandled Rejection]', reason)
    }
    notifyUser(message)
  })
}
