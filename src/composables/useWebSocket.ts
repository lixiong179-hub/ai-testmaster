import { ref, onUnmounted } from 'vue'

export interface UseWebSocketReturn {
  connect: (url: string, protocols?: string | string[]) => void
  disconnect: (code?: number, reason?: string) => void
  send: (data: string | ArrayBuffer | Blob | ArrayBufferView) => void
  onMessage: (callback: (event: MessageEvent) => void) => () => void
  onError: (callback: (event: Event) => void) => () => void
  isConnected: import('vue').Ref<boolean>
}

export function useWebSocket(): UseWebSocketReturn {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const messageHandlers = new Set<(event: MessageEvent) => void>()
  const errorHandlers = new Set<(event: Event) => void>()

  const connect = (url: string, protocols?: string | string[]) => {
    disconnect()

    const socket = protocols ? new WebSocket(url, protocols) : new WebSocket(url)

    socket.onopen = () => {
      isConnected.value = true
    }

    socket.onmessage = (event: MessageEvent) => {
      messageHandlers.forEach(handler => {
        try {
          handler(event)
        } catch (e) {
          console.error('WebSocket message handler error:', e)
        }
      })
    }

    socket.onerror = (event: Event) => {
      errorHandlers.forEach(handler => {
        try {
          handler(event)
        } catch (e) {
          console.error('WebSocket error handler error:', e)
        }
      })
    }

    socket.onclose = () => {
      isConnected.value = false
    }

    ws.value = socket
  }

  const disconnect = (code?: number, reason?: string) => {
    if (ws.value) {
      ws.value.close(code, reason)
      ws.value = null
    }
    isConnected.value = false
  }

  const send = (data: string | ArrayBuffer | Blob | ArrayBufferView) => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(data)
    }
  }

  const onMessage = (callback: (event: MessageEvent) => void): (() => void) => {
    messageHandlers.add(callback)
    return () => {
      messageHandlers.delete(callback)
    }
  }

  const onError = (callback: (event: Event) => void): (() => void) => {
    errorHandlers.add(callback)
    return () => {
      errorHandlers.delete(callback)
    }
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    connect,
    disconnect,
    send,
    onMessage,
    onError,
    isConnected
  }
}
