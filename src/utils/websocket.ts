/**
 * WebSocket工具类
 * 用于测试执行过程实时更新
 */

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
type MessageHandler = (data: unknown) => void;

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
   */
  connect(taskId: number, projectId: number, token: string): void {
    this.disconnect(true)

    this.currentTaskId = taskId
    this.currentProjectId = projectId
    this.isManualDisconnect = false

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/task/${taskId}`

    try {
      this.ws = new WebSocket(wsUrl, [token])

      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.send({
          type: 'subscribe',
          task_id: taskId,
          project_id: projectId
        })
      }

      this.ws.onmessage = (event) => {
        try {
          const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data

          // 触发所有注册的处理器
          this.messageHandlers.forEach(handler => {
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

      this.ws.onclose = () => {
        if (!this.isManualDisconnect) {
          this.scheduleReconnect()
        }
      }

      this.ws.onerror = (_error) => {
        // WebSocket错误
      }
    } catch (error) {
      // 创建WebSocket连接失败
    }
  }

  /**
   * 断开WebSocket连接
   * @param manual 是否手动断开（手动断开不自动重连）
   */
  disconnect(manual: boolean = false): void {
    this.isManualDisconnect = manual

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }

    if (manual) {
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
   * 定时重连
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer || this.isManualDisconnect) return

    this.reconnectAttempts++
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), this.MAX_RECONNECT_DELAY)

    this.reconnectTimer = setTimeout(() => {
      if (this.currentTaskId && this.currentProjectId) {
        const token = localStorage.getItem('token')
        if (token) {
          this.connect(this.currentTaskId, this.currentProjectId, token)
        }
      }
      this.reconnectTimer = null
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
 * @param path WebSocket路径
 * @param options 回调选项
 * @returns WebSocket连接对象
 */
export function connectWebSocket(
  path: string,
  options: WebSocketOptions = {}
): WebSocketConnection {
  // 从localStorage获取token
  const token = localStorage.getItem('token')
  
  // 构建WebSocket URL
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const wsUrl = `${protocol}//${host}/ws${path}`
  
  const ws = token ? new WebSocket(wsUrl, [token]) : new WebSocket(wsUrl)
  
  ws.onopen = () => {
    options.onOpen?.()
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      options.onMessage?.(data)
    } catch (error) {
      options.onMessage?.(event.data)
    }
  }

  ws.onclose = () => {
    options.onClose?.()
  }

  ws.onerror = (error) => {
    options.onError?.(error)
  }
  
  return {
    ws,
    close: () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close()
      }
    }
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
export function sendWebSocketMessage(
  connection: WebSocketConnection,
  data: string | object
): void {
  if (connection.ws.readyState === WebSocket.OPEN) {
    const message = typeof data === 'string' ? data : JSON.stringify(data)
    connection.ws.send(message)
  } else {
    console.error('WebSocket未连接，无法发送消息')
  }
}
