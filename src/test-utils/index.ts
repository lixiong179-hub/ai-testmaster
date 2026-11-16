/**
 * 测试工具集合
 *
 * 约定：
 * - 浏览器 API 桩由 `vitest.setup.ts` 全局安装（`installBrowserStubs`），
 *   需要独立重置的 spec 可在 `beforeEach` 中再次调用。
 * - 消息提示 / console 静默、表单实例、Promise 控制等按需在 spec 中引入。
 */
export { installBrowserStubs } from './env'
export { createComposableHost, type ComposableHost } from './component'
export { silenceElMessage, mockConfirm, mockCancel, silenceConsole, type MessageType } from './ui'
export { deferred, createMockActions, type Deferred } from './async'
export { createFormInstanceMock, type FormInstanceMock, type FormInstanceMockOptions } from './form'
