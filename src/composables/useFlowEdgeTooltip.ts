import { ref, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import type { EdgeMouseEvent } from '@vue-flow/core'

/** useFlowEdgeTooltip 配置项 */
// eslint-disable-next-line @typescript-eslint/no-empty-interface
export interface UseFlowEdgeTooltipOptions {}

/** 边 tooltip 数据结构 */
export interface EdgeTooltipData {
  id: string
  source: string
  target: string
  label?: string
  data?: Record<string, unknown>
  [key: string]: unknown
}

/** useFlowEdgeTooltip 返回值 */
export interface UseFlowEdgeTooltipReturn {
  edgeTooltipVisible: Ref<boolean>
  edgeTooltipData: Ref<EdgeTooltipData | null>
  edgeTooltipPosition: Ref<{ x: number; y: number }>
  onEdgeMouseEnter: (event: EdgeMouseEvent) => void
  onEdgeMouseLeave: () => void
  onEdgeMouseMove: (event: EdgeMouseEvent) => void
  onEdgeTooltipEnter: () => void
  onEdgeTooltipLeave: () => void
}

/**
 * 从 FlowSortEditor 抽取的边 tooltip 交互逻辑。
 * 管理鼠标悬停边时显示/隐藏 tooltip，以及 tooltip 自身的悬停保持。
 */
export function useFlowEdgeTooltip(_options: UseFlowEdgeTooltipOptions): UseFlowEdgeTooltipReturn {
  const edgeTooltipVisible = ref(false)
  const edgeTooltipData = ref<EdgeTooltipData | null>(null)
  const edgeTooltipPosition = ref({ x: 0, y: 0 })

  let edgeTooltipRafId: number | null = null
  let edgeTooltipHideTimer: ReturnType<typeof setTimeout> | null = null
  let edgeTooltipHovered = false

  const onEdgeMouseEnter = (event: EdgeMouseEvent) => {
    const mouseEvent = event.event as MouseEvent
    edgeTooltipData.value = event.edge as unknown as EdgeTooltipData
    edgeTooltipPosition.value = { x: mouseEvent.clientX + 12, y: mouseEvent.clientY + 12 }
    edgeTooltipVisible.value = true
  }

  const onEdgeMouseMove = (event: EdgeMouseEvent) => {
    // 只在 tooltip 未显示时更新位置，避免 tooltip 跟随鼠标移动导致无法点击
    if (edgeTooltipVisible.value) return
    if (edgeTooltipRafId !== null) return
    edgeTooltipRafId = requestAnimationFrame(() => {
      const mouseEvent = event.event as MouseEvent
      edgeTooltipPosition.value = { x: mouseEvent.clientX + 12, y: mouseEvent.clientY + 12 }
      edgeTooltipRafId = null
    })
  }

  const onEdgeMouseLeave = () => {
    if (edgeTooltipRafId !== null) {
      cancelAnimationFrame(edgeTooltipRafId)
      edgeTooltipRafId = null
    }
    // 延迟隐藏，给用户时间移入 tooltip 点击按钮
    edgeTooltipHideTimer = setTimeout(() => {
      if (!edgeTooltipHovered) {
        edgeTooltipVisible.value = false
        edgeTooltipData.value = null
      }
    }, 200)
  }

  const onEdgeTooltipEnter = () => {
    edgeTooltipHovered = true
    if (edgeTooltipHideTimer) {
      clearTimeout(edgeTooltipHideTimer)
      edgeTooltipHideTimer = null
    }
  }

  const onEdgeTooltipLeave = () => {
    edgeTooltipHovered = false
    edgeTooltipVisible.value = false
    edgeTooltipData.value = null
  }

  onUnmounted(() => {
    if (edgeTooltipRafId !== null) {
      cancelAnimationFrame(edgeTooltipRafId)
      edgeTooltipRafId = null
    }
    if (edgeTooltipHideTimer) {
      clearTimeout(edgeTooltipHideTimer)
      edgeTooltipHideTimer = null
    }
  })

  return {
    edgeTooltipVisible,
    edgeTooltipData,
    edgeTooltipPosition,
    onEdgeMouseEnter,
    onEdgeMouseLeave,
    onEdgeMouseMove,
    onEdgeTooltipEnter,
    onEdgeTooltipLeave,
  }
}
