/**
 * 认证事件总线
 *
 * 解耦 HTTP 工具层与业务 Store：request.ts 在 401 时只需 emit 事件，
 * 各业务 Store 自行监听并执行清理逻辑，避免工具层反向依赖业务层。
 */

export type AuthEventType = 'auth:unauthorized'

type AuthEventHandler = () => void

const handlers: Map<AuthEventType, Set<AuthEventHandler>> = new Map()

/** 订阅认证事件 */
export function onAuthEvent(event: AuthEventType, handler: AuthEventHandler): () => void {
  if (!handlers.has(event)) {
    handlers.set(event, new Set())
  }
  handlers.get(event)!.add(handler)
  // 返回取消订阅函数
  return () => {
    handlers.get(event)?.delete(handler)
  }
}

/** 触发认证事件，通知所有订阅者 */
export function emitAuthEvent(event: AuthEventType): void {
  const set = handlers.get(event)
  if (!set) return
  set.forEach((handler) => {
    try {
      handler()
    } catch {
      // 单个处理器失败不影响其他订阅者
    }
  })
}
