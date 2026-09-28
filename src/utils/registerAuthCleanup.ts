/**
 * 业务 Store 认证清理注册
 *
 * 各业务 Store 在此注册自身的 reset 逻辑，监听 auth:unauthorized 事件。
 * 由 main.ts 在应用启动时调用，将业务层的依赖方向修正为：业务 → 工具（而非工具 → 业务）。
 */
import { onAuthEvent } from './authEventBus'
import { useProjectStore } from '@/store/project'
import { useCaseStore } from '@/store/case'
import { useTaskStore } from '@/store/task'
import { useReportStore } from '@/store/report'
import { useQuickTestStore } from '@/store/quickTest'
import { useSmartGenerationStore } from '@/store/smartGeneration'
import { useFlowSortStore } from '@/store/flowSort'

/**
 * 注册所有业务 Store 的 401 清理回调。
 * 应在 Pinia 初始化后、路由守卫生效前调用（main.ts）。
 */
export function registerAuthCleanup(): void {
  onAuthEvent('auth:unauthorized', () => {
    const resets: Array<() => void> = [
      () => useProjectStore().$reset(),
      () => useCaseStore().$reset(),
      () => useTaskStore().$reset(),
      () => useReportStore().$reset(),
      () => useQuickTestStore().reset(),
      () => useSmartGenerationStore().reset(),
      () => useFlowSortStore().reset(),
    ]
    for (const reset of resets) {
      try {
        reset()
      } catch {
        // Pinia 可能尚未初始化（启动早期），忽略
      }
    }
  })
}
