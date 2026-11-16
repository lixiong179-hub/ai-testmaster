import { vi } from 'vitest'

/**
 * 安装/重置浏览器 API 桩
 *
 * happy-dom 对部分 API 支持不完整，或行为与真实浏览器不同。
 * 该函数由 `vitest.setup.ts` 全局调用；需要独立重置的 spec 也可以在
 * `beforeEach` 中再次调用，确保每个用例拿到全新的 mock。
 *
 * 注意：这里只重置实现，不清理调用记录——调用记录由 spec 中的
 * `vi.clearAllMocks()` 负责。
 */
export function installBrowserStubs(): void {
  // 对象 URL：Blob 下载、截图预览等
  Object.defineProperty(URL, 'createObjectURL', {
    value: vi.fn(() => 'blob:vitest-mock'),
    writable: true,
    configurable: true,
  })

  Object.defineProperty(URL, 'revokeObjectURL', {
    value: vi.fn(),
    writable: true,
    configurable: true,
  })

  // 剪贴板：默认写入成功
  Object.defineProperty(navigator, 'clipboard', {
    value: {
      writeText: vi.fn(() => Promise.resolve()),
      readText: vi.fn(() => Promise.resolve('')),
    },
    writable: true,
    configurable: true,
  })

  // 旧版复制回退方案
  Object.defineProperty(document, 'execCommand', {
    value: vi.fn(() => true),
    writable: true,
    configurable: true,
  })

  // 媒体查询：Element Plus 响应式组件依赖
  if (typeof window.matchMedia !== 'function') {
    Object.defineProperty(window, 'matchMedia', {
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
      writable: true,
      configurable: true,
    })
  }

  // 尺寸/可见性观察器
  class ObserverStub {
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
    takeRecords = vi.fn(() => [])
  }

  if (typeof globalThis.ResizeObserver !== 'function') {
    Object.defineProperty(globalThis, 'ResizeObserver', {
      value: ObserverStub,
      writable: true,
      configurable: true,
    })
  }

  if (typeof globalThis.IntersectionObserver !== 'function') {
    Object.defineProperty(globalThis, 'IntersectionObserver', {
      value: ObserverStub,
      writable: true,
      configurable: true,
    })
  }

  // 滚动相关方法
  if (typeof Element.prototype.scrollIntoView !== 'function') {
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      value: vi.fn(),
      writable: true,
      configurable: true,
    })
  }

  if (typeof window.scrollTo !== 'function') {
    Object.defineProperty(window, 'scrollTo', {
      value: vi.fn(),
      writable: true,
      configurable: true,
    })
  }
}
