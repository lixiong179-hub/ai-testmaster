/**
 * 执行控制 Composable
 * 职责：开始/暂停/恢复/停止测试执行
 */
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  startTestExecution,
  pauseTestExecution,
  resumeTestExecution,
  stopTestExecution,
  type ExecutionMode,
} from '@/api/testExecution'
import { unwrapApiResponse } from '@/utils/api'

export interface UseExecutionControlOptions {
  /** 当前任务ID */
  taskId: () => number
  /** 执行状态 */
  executionStatus: import('vue').Ref<Record<string, unknown> | null>
  /** 可见模式配置 */
  visibilityConfig: import('vue').Ref<{
    headless: boolean
    recordVideo: boolean
    videoFps: number
  }>
  /** 目标环境 */
  targetEnv: import('vue').Ref<string>
  /** 自动初始化开关 */
  autoInitEnabled: import('vue').Ref<boolean>
  /** 执行模式 */
  executionMode: import('vue').Ref<ExecutionMode>
  /** 移动端设备ID */
  mobileDeviceId: import('vue').Ref<string>
  /** MCP模式开关 */
  useMcpMode: import('vue').Ref<boolean>
  /** 同步taskInfo状态 */
  syncTaskInfoStatus: (status: number) => void
  /** 加载任务信息 */
  loadTaskInfo: () => Promise<unknown>
  /** 加载执行状态 */
  loadExecutionStatus: () => Promise<void>
  /** 连接WebSocket实时更新 */
  connectWebSocketForRealtimeUpdate: () => void
}

export function useExecutionControl(options: UseExecutionControlOptions) {
  const controlLoading = ref(false)

  const startExecution = async () => {
    if (options.executionMode.value.startsWith('mobile_') && !options.mobileDeviceId.value) {
      ElMessage.warning('移动端模式请先选择目标设备')
      return
    }
    controlLoading.value = true
    try {
      const res = await startTestExecution(options.taskId(), {
        headless: options.visibilityConfig.value.headless,
        recordVideo: options.visibilityConfig.value.recordVideo,
        targetEnv: options.targetEnv.value,
        skipInit: !options.autoInitEnabled.value,
        executionMode: options.executionMode.value,
        mobileDeviceId: options.executionMode.value.startsWith('mobile_')
          ? options.mobileDeviceId.value
          : undefined,
        use_mcp: options.useMcpMode.value,
      })
      const body = unwrapApiResponse<Record<string, unknown>>(res)
      if (body.code === 200) {
        options.syncTaskInfoStatus(1)
        options.executionStatus.value = {
          ...options.executionStatus.value,
          status: (body.data as Record<string, unknown>)?.status || 'running',
          current_step: Number(options.executionStatus.value?.current_step || 0),
          total_steps: Number(options.executionStatus.value?.total_steps || 0),
        }
        ElMessage.success('开始执行')
        await options.loadTaskInfo()
        await options.loadExecutionStatus()
        options.connectWebSocketForRealtimeUpdate()
      } else {
        ElMessage.error(body.message || '开始执行失败')
      }
    } catch (error) {
      console.error('开始执行失败:', error)
      ElMessage.error('开始执行失败')
    } finally {
      controlLoading.value = false
    }
  }

  const pauseExecution = async () => {
    controlLoading.value = true
    try {
      const res = await pauseTestExecution(options.taskId())
      const body = unwrapApiResponse<Record<string, unknown>>(res)
      if (body.code === 200) {
        ElMessage.success('已暂停')
        await options.loadExecutionStatus()
      }
    } catch (error) {
      console.error('暂停失败:', error)
      ElMessage.error('暂停失败')
    } finally {
      controlLoading.value = false
    }
  }

  const resumeExecution = async () => {
    controlLoading.value = true
    try {
      const res = await resumeTestExecution(options.taskId())
      const body = unwrapApiResponse<Record<string, unknown>>(res)
      if (body.code === 200) {
        ElMessage.success('已恢复')
        await options.loadExecutionStatus()
      }
    } catch (error) {
      console.error('恢复失败:', error)
      ElMessage.error('恢复失败')
    } finally {
      controlLoading.value = false
    }
  }

  const stopExecution = async () => {
    try {
      await ElMessageBox.confirm('确定要停止执行吗？', '确认', {
        type: 'warning',
      })
      controlLoading.value = true
      const res = await stopTestExecution(options.taskId())
      const body = unwrapApiResponse<Record<string, unknown>>(res)
      if (body.code === 200) {
        ElMessage.success('已停止')
        await options.loadExecutionStatus()
      }
    } catch (error: unknown) {
      if (error !== 'cancel') {
        console.error('停止失败:', error)
        ElMessage.error('停止失败')
      }
    } finally {
      controlLoading.value = false
    }
  }

  return {
    controlLoading,
    startExecution,
    pauseExecution,
    resumeExecution,
    stopExecution,
  }
}
