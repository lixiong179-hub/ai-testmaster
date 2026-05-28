import { ref, computed } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import type { FlowEditorNode, FlowGraphEdge, EditorNodeData } from '@/composables/useFlowEditor'
import { getMainNodesInOrder } from '@/composables/useFlowEditor'
import type { Ref, ComputedRef } from 'vue'

/** 节点分组项 */
export interface NodeGroup {
  id: string
  label: string
  color: string
  strokeColor: string
  bounds: { x: number; y: number; width: number; height: number }
}

/** useFlowGroupBackground 配置项 */
export interface UseFlowGroupBackgroundOptions {
  vueFlowNodes: Ref<FlowEditorNode[]>
  vueFlowEdges: Ref<FlowGraphEdge[]>
  getNodeData: (node: FlowEditorNode) => EditorNodeData
}

/** useFlowGroupBackground 返回值 */
export interface UseFlowGroupBackgroundReturn {
  showGroupBackground: Ref<boolean>
  nodeGroups: ComputedRef<NodeGroup[]>
  svgViewBox: ComputedRef<{ x: number; y: number }>
  branchChildrenMap: ComputedRef<Map<string, Array<{ node: FlowEditorNode; edge: FlowGraphEdge }>>>
}

/** 节点卡片默认尺寸，用于计算分组边界 */
const NODE_CARD_WIDTH = 220
const NODE_CARD_HEIGHT = 200

/** 分组内边距 */
const GROUP_PADDING = 20

/** 分组颜色映射 */
const TYPE_COLORS: Record<string, { color: string; strokeColor: string }> = {
  main: { color: 'rgba(64, 158, 255, 0.08)', strokeColor: 'rgba(64, 158, 255, 0.4)' },
  branch: { color: 'rgba(103, 194, 58, 0.08)', strokeColor: 'rgba(103, 194, 58, 0.4)' },
  exception: { color: 'rgba(245, 108, 108, 0.08)', strokeColor: 'rgba(245, 108, 108, 0.4)' },
  bypass: { color: 'rgba(230, 162, 60, 0.08)', strokeColor: 'rgba(230, 162, 60, 0.4)' },
}

/**
 * 从 FlowSortEditor 抽取的模块分组背景逻辑。
 * 按主干节点分组，计算每组的边界矩形与颜色，供 SVG 背景渲染。
 */
export function useFlowGroupBackground(
  options: UseFlowGroupBackgroundOptions
): UseFlowGroupBackgroundReturn {
  const { vueFlowNodes, vueFlowEdges, getNodeData } = options
  const { viewport } = useVueFlow()

  const showGroupBackground = ref(true)

  /** 分支子节点映射：主干节点 ID → 其分支/异常/旁路子节点列表 */
  const branchChildrenMap = computed(() => {
    const map = new Map<string, Array<{ node: FlowEditorNode; edge: FlowGraphEdge }>>()
    const nodes = vueFlowNodes.value
    const nodeMap = new Map(nodes.map((n) => [n.id, n]))
    vueFlowEdges.value.forEach((edge) => {
      if (
        edge.data?.edge_type &&
        ['branch', 'exception', 'bypass'].includes(edge.data.edge_type as string) &&
        nodeMap.has(edge.target)
      ) {
        const child = nodeMap.get(edge.target)!
        if (!map.has(edge.source)) {
          map.set(edge.source, [])
        }
        map.get(edge.source)!.push({ node: child, edge })
      }
    })
    return map
  })

  /** 按模块分组的节点列表与边界 */
  const nodeGroups = computed<NodeGroup[]>(() => {
    if (!showGroupBackground.value) return []
    const visibleNodes = vueFlowNodes.value.filter((n) => !n.hidden)
    if (visibleNodes.length === 0) return []

    // Group by parent main node (for branch/exception/bypass children)
    const groups = new Map<string, FlowEditorNode[]>()
    const mainNodes = getMainNodesInOrder(vueFlowNodes.value, vueFlowEdges.value as any)

    mainNodes.forEach((mainNode) => {
      const children = branchChildrenMap.value.get(mainNode.id)
      if (children && children.length > 0) {
        groups.set(mainNode.id, [mainNode, ...children.map((c) => c.node)])
      }
    })

    // Also group standalone main nodes that have no children
    mainNodes.forEach((mainNode) => {
      if (!groups.has(mainNode.id)) {
        groups.set(mainNode.id, [mainNode])
      }
    })

    // Orphan non-main nodes
    const groupedNodeIds = new Set<string>()
    groups.forEach((nodes) => nodes.forEach((n) => groupedNodeIds.add(n.id)))
    const orphans = visibleNodes.filter((n) => !groupedNodeIds.has(n.id))
    if (orphans.length > 0) {
      groups.set('__orphans__', orphans)
    }

    const result: NodeGroup[] = []
    groups.forEach((nodes, groupId) => {
      if (nodes.length === 0) return
      const minX = Math.min(...nodes.map((n) => n.position.x))
      const minY = Math.min(...nodes.map((n) => n.position.y))
      const maxX = Math.max(...nodes.map((n) => n.position.x + NODE_CARD_WIDTH))
      const maxY = Math.max(...nodes.map((n) => n.position.y + NODE_CARD_HEIGHT))

      const mainNode = nodes.find((n) => getNodeData(n).flow_type === 'main')
      const flowType = mainNode ? getNodeData(mainNode).flow_type : 'branch'
      const colors = TYPE_COLORS[flowType] || TYPE_COLORS.main
      const label = mainNode
        ? `${getNodeData(mainNode).screen_name} 模块`
        : groupId === '__orphans__'
          ? '未分组'
          : '模块'

      result.push({
        id: groupId,
        label,
        color: colors.color,
        strokeColor: colors.strokeColor,
        bounds: {
          x: minX,
          y: minY,
          width: maxX - minX,
          height: maxY - minY,
        },
      })
    })

    return result
  })

  /** SVG 定位偏移，跟随画布视口 */
  const svgViewBox = computed(() => ({
    x: viewport.value?.x ?? 0,
    y: viewport.value?.y ?? 0,
  }))

  return {
    showGroupBackground,
    nodeGroups,
    svgViewBox,
    branchChildrenMap,
  }
}

/** 分组内边距常量，供模板使用 */
export const groupPadding = GROUP_PADDING
