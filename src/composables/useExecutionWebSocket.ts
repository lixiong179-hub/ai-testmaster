/**
 * 执行WebSocket实时更新 Composable
 * 职责：WebSocket连接管理、实时数据更新处理
 */
import { onUnmounted, nextTick } from 'vue'
import { connectWebSocket, disconnectWebSocket, type WebSocketConnection } from '@/utils/websocket'

export interface UseExecutionWebSocketOptions {
  /** 当前任务ID */
  taskId: () => number
  /** 执行步骤列表 */
  executionSteps: import('vue').Ref<Record<string, unknown>[]>
  /** 当前步骤索引 */
  currentStepIndex: import('vue').Ref<number>
  /** 执行日志列表 */
  executionLogs: import('vue').Ref<Record<string, unknown>[]>
  /** 执行状态 */
  executionStatus: import('vue').Ref<Record<string, unknown> | null>
  /** 加载步骤截图 */
  loadStepScreenshot: () => Promise<void>
  /** 滚动到底部 */
  scrollToBottom: () => void
}

export function useExecutionWebSocket(options: UseExecutionWebSocketOptions) {
  let wsConnection: WebSocketConnection | null = null

  const connectWebSocketForRealtimeUpdate = () => {
    wsConnection = connectWebSocket(`/ws/execution/${options.taskId()}`, {
      onMessage: (data: unknown) => {
        const msg = data as Record<string, unknown>
        if (msg.type === 'step_update') {
          options.executionSteps.value = msg.steps as Record<string, unknown>[]
          if (msg.current_step) {
            options.currentStepIndex.value = Number(msg.current_step) - 1
            options.loadStepScreenshot()
          }
        } else if (msg.type === 'log') {
          options.executionLogs.value.push(msg.log as Record<string, unknown>)
          nextTick(() => options.scrollToBottom())
        } else if (msg.type === 'status_update') {
          options.executionStatus.value = msg.status as Record<string, unknown>
        }
      },
      onError: (error: unknown) => {
        console.error('WebSocket错误:', error)
      },
    })
  }

  const disconnect = () => {
    if (wsConnection) {
      disconnectWebSocket(wsConnection)
      wsConnection = null
    }
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    connectWebSocketForRealtimeUpdate,
    disconnect,
  }
}
