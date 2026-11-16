import { vi } from 'vitest'

export interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason?: unknown) => void
}

/**
 * 手动控制的 Promise，用于验证「等待中」的中间态。
 *
 * @example
 * const d = deferred<{ items: never[] }>()
 * mocks.extract.mockReturnValue(d.promise)
 * const pending = ctx.extractTestPoints()
 * vi.advanceTimersByTime(600)   // 断言中间态
 * d.resolve({ items: [] })
 * await pending
 */
export function deferred<T>(): Deferred<T> {
  let resolve: (value: T) => void = () => {}
  let reject: (reason?: unknown) => void = () => {}
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

/**
 * 把一组方法名转换为 vi.fn()，用于快速构造 API/Store 的模块级 mock。
 *
 * @example
 * const api = createMockActions(['getTask', 'startTask'] as const)
 * vi.mock('@/api/task', () => ({ default: api }))
 */
export function createMockActions<K extends string>(
  names: readonly K[]
): Record<K, ReturnType<typeof vi.fn>> {
  return Object.fromEntries(names.map((name) => [name, vi.fn()])) as Record<
    K,
    ReturnType<typeof vi.fn>
  >
}
