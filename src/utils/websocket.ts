/**
 * WebSocket工具类
 * 用于测试执行过程实时更新
 */
import { ElMessage } from 'element-plus'

/** 最大自动重连次数（超过后提示用户刷新） */
const MAX_RECONNECT_ATTEMPTS = 3

export interface WebSocketOptions {
  onMessage?: (data: unknown) => void
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: unknown) => void
}

export interface WebSocketConnection {
  ws: WebSocket
  close: () => void
}

// 消息处理器类型
type MessageHandler = (data: unknown) => void

/**
 * WebSocket客户端类
 */
class WebSocketClient {
  private ws: WebSocket | null = null
  private currentTaskId: number | null = null
  private currentProjectId: number | null = null
  private reconnectTimer: NodeJS.Timeout | null = null
  private messageHandlers: Set<MessageHandler> = new Set()
  private isManualDisconnect = false
  private reconnectAttempts = 0
  private readonly MAX_RECONNECT_DELAY = 30000

  /**
   * 连接WebSocket
   * @param isReconnect 是否由自动重连触发（内部使用）：重连不重置重连计数
   */
  connect(taskId: number, projectId: number, token: string, isReconnect: boolean = false): void {
    this.teardown()

    this.currentTaskId = taskId
    this.currentProjectId = projectId
    this.isManualDisconnect = false
    if (!isReconnect) {
      this.reconnectAttempts = 0
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/task/${taskId}`

    try {
      const socket = new WebSocket(wsUrl, [token])
      this.ws = socket

      socket.onopen = () => {
        if (this.ws !== socket) return
        const wasReconnecting = this.reconnectAttempts > 0
        this.reconnectAttempts = 0
        if (wasReconnecting) {
          ElMessage.success('连接已恢复')
        }
        this.send({
          type: 'subscribe',
          task_id: taskId,
          project_id: projectId,
        })
      }

      socket.onmessage = (event) => {
        try {
          const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data

          // 触发所有注册的处理器
          this.messageHandlers.forEach((handler) => {
            try {
              handler(data)
            } catch (error) {
              // WebSocket消息处理器执行失败
            }
          })

          // 触发自定义事件供组件监听
          window.dispatchEvent(new CustomEvent('ws-message', { detail: data }))
        } catch (error) {
          // WebSocket消息解析失败
        }
      }

      socket.onclose = () => {
        // 旧连接（已被新连接替换）的回调直接忽略，避免误触发重连
        if (this.ws !== socket) return
        if (!this.isManualDisconnect) {
          this.scheduleReconnect()
        }
      }

      socket.onerror = (_error) => {
        // WebSocket错误
      }
    } catch (error) {
      // 创建WebSocket连接失败
    }
  }

  /** 关闭当前连接与重连定时器（不改变重连计数） */
  private teardown(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /**
   * 断开WebSocket连接
   * @param manual 是否手动断开（手动断开不自动重连）
   */
  disconnect(manual: boolean = false): void {
    this.isManualDisconnect = manual
    this.teardown()

    if (manual) {
      this.reconnectAttempts = 0
      this.currentTaskId = null
      this.currentProjectId = null
    }
  }

  /**
   * 发送消息
   */
  send(data: string | object): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = typeof data === 'string' ? data : JSON.stringify(data)
      this.ws.send(message)
    } else {
      console.warn('WebSocket未连接，无法发送消息')
    }
  }

  /**
   * 注册消息处理器
   */
  onMessage(handler: MessageHandler): void {
    this.messageHandlers.add(handler)
  }

  /**
   * 移除消息处理器
   */
  offMessage(handler: MessageHandler): void {
    this.messageHandlers.delete(handler)
  }

  /**
   * 清除所有消息处理器
   */
  clearMessageHandlers(): void {
    this.messageHandlers.clear()
  }

  /**
   * 定时重连（指数退避：1s → 2s → 4s，超过上限提示刷新）
   *
   * 提示规则：首次断线 warning 一次；重连成功 success；连续 3 次失败后 error 并停止。
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer || this.isManualDisconnect) return

    this.reconnectAttempts++
    if (this.reconnectAttempts === 1) {
      ElMessage.warning('连接已断开，正在重连...')
    }
    if (this.reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
      ElMessage.error('连接失败，请刷新页面重试')
      this.reconnectAttempts = 0
      return
    }

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), this.MAX_RECONNECT_DELAY)

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      if (this.currentTaskId && this.currentProjectId) {
        const token = localStorage.getItem('token')
        if (token) {
          this.connect(this.currentTaskId, this.currentProjectId, token, true)
        }
      }
    }, delay)
  }

  /**
   * 检查是否已连接
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  /**
   * 获取当前任务ID
   */
  getCurrentTaskId(): number | null {
    return this.currentTaskId
  }
}

// 导出单例
export const wsClient = new WebSocketClient()

/**
 * 连接WebSocket（函数式API）
 *
 * 鉴权方式：token 通过 URL Query 参数 ?token=xxx 传递，与后端
 * /ws/execution/{execution_id}、/ws/quick-test/{task_id} 等端点的
 * token: str = Query(...) 参数对齐。不再使用子协议传 token：
 * FastAPI WebSocket 端点不显式响应子协议，浏览器会触发 onerror。
 *
 * @param path WebSocket路径（不含 /ws 前缀，由本函数拼接）
 * @param options 回调选项
 * @returns WebSocket连接对象
 */
export function connectWebSocket(
  path: string,
  options: WebSocketOptions = {}
): WebSocketConnection {
  // 从localStorage获取token
  const token = localStorage.getItem('token')

  // 构建WebSocket URL：token 走 Query 参数（后端 Query 鉴权）
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : ''
  const wsUrl = `${protocol}//${host}/ws${path}${tokenQuery}`

  let current: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  let manualClosed = false

  const scheduleReconnect = (): void => {
    if (reconnectTimer || manualClosed) return

    reconnectAttempts += 1
    if (reconnectAttempts === 1) {
      ElMessage.warning('连接已断开，正在重连...')
    }
    if (reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
      ElMessage.error('连接失败，请刷新页面重试')
      reconnectAttempts = 0
      return
    }

    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 30000)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (!manualClosed) {
        open()
      }
    }, delay)
  }

  const open = (): void => {
    const socket = new WebSocket(wsUrl)
    current = socket

    socket.onopen = () => {
      if (current !== socket) return
      const wasReconnecting = reconnectAttempts > 0
      reconnectAttempts = 0
      if (wasReconnecting) {
        ElMessage.success('连接已恢复')
      }
      options.onOpen?.()
    }

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        options.onMessage?.(data)
      } catch (error) {
        options.onMessage?.(event.data)
      }
    }

    socket.onclose = () => {
      if (current !== socket) return
      options.onClose?.()
      if (!manualClosed) {
        scheduleReconnect()
      }
    }

    socket.onerror = (error) => {
      options.onError?.(error)
    }
  }

  open()

  return {
    get ws() {
      return current as WebSocket
    },
    close: () => {
      manualClosed = true
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      if (current && (current.readyState === WebSocket.OPEN || current.readyState === WebSocket.CONNECTING)) {
        current.close()
      }
    },
  }
}

/**
 * 断开WebSocket连接
 * @param connection WebSocket连接对象
 */
export function disconnectWebSocket(connection: WebSocketConnection): void {
  connection.close()
}

/**
 * 发送WebSocket消息
 * @param connection WebSocket连接对象
 * @param data 要发送的数据
 */
export function sendWebSocketMessage(connection: WebSocketConnection, data: string | object): void {
  if (connection.ws.readyState === WebSocket.OPEN) {
    const message = typeof data === 'string' ? data : JSON.stringify(data)
    connection.ws.send(message)
  } else {
    console.error('WebSocket未连接，无法发送消息')
  }
}
