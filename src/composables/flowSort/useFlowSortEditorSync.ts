import { watch, onMounted, nextTick } from 'vue'
import { generateAutoEdges } from '@/composables/useFlowEditor'
import { normalizeMainNodeOrders } from '@/composables/useFlowEditor'
import type { FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'
import type { FlowNodeData, FlowEdgeData } from '@/store/flowSort'
import type { UIScreen, UIElement } from '@/api/uiPrototype'
import type { FlowSortEditorContext } from './useFlowSortEditor'

const NODE_SPACING_X = 280
const SHORTCUTS_TIP_DURATION = 5000
const GRID_COLS = 4
const GRID_GAP_X = 280
const GRID_GAP_Y = 260

export function useFlowSortEditorSync(ctx: FlowSortEditorContext) {
  const {
    props,
    displayMode,
    vueFlowNodes,
    vueFlowEdges,
    showShortcutsTip,
    editorRef,
    collapsedParentNodeIds,
    isRestoredFromBackend,
    searchKeyword,
    searchMatchIds,
    emitSortData,
    applyAllEdgeStyles,
    saveSnapshot,
    fitView,
    hydrateNodesWithImages,
    syncHistoryImages,
    focusedNodeId,
    selectedNodes,
    currentPlayNodeId,
    isPlaying,
    currentZoom,
    flowSortStore,
  } = ctx

  function isScreensEqual(a: UIScreen[], b: UIScreen[]): boolean {
    if (a.length !== b.length) return false
    return a.every((screen: UIScreen, index: number) => {
      const other = b[index]
      return (
        screen.id === other.id &&
        screen.screen_name === other.screen_name &&
        screen.summary === other.summary &&
        screen.element_count === other.element_count
      )
    })
  }

  let lastScreens: UIScreen[] = []

  watch(
    () => props.screens,
    (newScreens) => {
      if (isScreensEqual(newScreens, lastScreens)) return
      lastScreens = newScreens
      isRestoredFromBackend.value = false
      const newNodes = normalizeMainNodeOrders(
        newScreens.map((screen: UIScreen, index: number) => ({
          id: `node_${screen.id}`,
          type: 'custom',
          position:
            flowSortStore.quickMode === true
              ? {
                  x: (index % GRID_COLS) * GRID_GAP_X,
                  y: Math.floor(index / GRID_COLS) * GRID_GAP_Y,
                }
              : { x: index * NODE_SPACING_X, y: 0 },
          data: {
            screen_id: screen.id,
            screen_name: screen.screen_name,
            summary: screen.summary,
            ui_spec_elements: (screen.ui_spec?.elements || []).map((el: UIElement) => ({
              type: el.type,
              label: el.label,
              semantic: el.semantic_hint || el.description,
              position: typeof el.position === 'string' ? el.position : JSON.stringify(el.position),
              interactive: el.interactive,
              state: el.state,
              description: el.description,
            })),
            flow_type: 'main' as const,
            main_order: index + 1,
            image_url: !screen.id ? '' : props.screenImageUrls?.[screen.id] || '',
            element_count: screen.element_count,
          },
        }))
      )
      vueFlowNodes.value = newNodes
      if (flowSortStore.quickMode === true) {
        vueFlowEdges.value = []
      } else {
        const autoEdges = generateAutoEdges(newNodes)
        vueFlowEdges.value = applyAllEdgeStyles(autoEdges as unknown as FlowGraphEdge[])
      }
      saveSnapshot()
      emitSortData()
    },
    { immediate: true }
  )

  watch(displayMode, () => {
    searchKeyword.value = ''
    searchMatchIds.value = []
    vueFlowEdges.value = applyAllEdgeStyles(vueFlowEdges.value)
    nextTick(() => {
      void fitView({ duration: 300, padding: 0.15 })
    })
    emitSortData()
  })

  watch(
    () => props.screenImageUrls,
    (newImageUrls) => {
      if (!newImageUrls || vueFlowNodes.value.length === 0) return
      vueFlowNodes.value = hydrateNodesWithImages(vueFlowNodes.value)
      syncHistoryImages()
    },
    { deep: true }
  )

  watch(
    () => props.moduleInfo,
    () => emitSortData()
  )

  watch(
    ctx.viewport,
    (nextViewport) => {
      currentZoom.value = nextViewport?.zoom ?? 1
    },
    { deep: true, immediate: true }
  )

  watch(currentPlayNodeId, (nodeId) => {
    if (nodeId) {
      focusedNodeId.value = nodeId
      const node = vueFlowNodes.value.find((n) => n.id === nodeId)
      if (node)
        ctx.setCenter(node.position.x, node.position.y, { zoom: currentZoom.value, duration: 300 })
    }
  })

  watch(isPlaying, (playing) => {
    if (!playing) {
      focusedNodeId.value = null
      selectedNodes.value = []
    }
  })

  watch(collapsedParentNodeIds, () => ctx.applyCollapsedHidden(), { deep: true })

  function syncStoreToEditor() {
    const currentScreenIds = new Set(props.screens.map((screen: UIScreen) => Number(screen.id)))
    const storeNodes = flowSortStore.nodes.filter((node: FlowNodeData) =>
      currentScreenIds.has(Number(node.screen_id))
    )
    if (storeNodes.length === 0) return
    const screenById = new Map(props.screens.map((s: UIScreen) => [s.id, s]))
    vueFlowNodes.value = storeNodes.map((node: FlowNodeData) => ({
      id: node.id,
      type: 'custom',
      position: node.position || { x: 0, y: 0 },
      data: {
        screen_id: node.screen_id,
        screen_name: node.screen_name,
        summary: node.summary,
        ui_spec_elements: node.ui_spec_elements || [],
        flow_type: node.flow_type,
        main_order: node.main_order,
        image_url: props.screenImageUrls?.[node.screen_id] || node.image_url || '',
        element_count: screenById.get(node.screen_id)?.element_count,
        flow_meta: node.flow_meta,
      },
    }))
    const { inferEdgeType, getNodeData } = ctx
    const validNodeIds = new Set(storeNodes.map((node: FlowNodeData) => node.id))
    const validScreenIds = new Set(storeNodes.map((node: FlowNodeData) => String(node.screen_id)))
    const rawEdges = flowSortStore.edges
      .filter((edge: FlowEdgeData) => {
        const source = String(edge.source)
        const target = String(edge.target)
        return (
          (validNodeIds.has(source) || validScreenIds.has(source)) &&
          (validNodeIds.has(target) || validScreenIds.has(target))
        )
      })
      .map((edge: FlowEdgeData) => {
        const sourceNode = vueFlowNodes.value.find(
          (n: FlowEditorNode) => getNodeData(n).screen_id === Number(edge.source)
        )
        const targetNode = vueFlowNodes.value.find(
          (n: FlowEditorNode) => getNodeData(n).screen_id === Number(edge.target)
        )
        const sourceType = sourceNode ? getNodeData(sourceNode).flow_type : 'main'
        const targetType = targetNode ? getNodeData(targetNode).flow_type : 'main'
        const handles =
          edge.edge_type !== 'normal'
            ? inferEdgeType(sourceType, targetType)
            : { sourceHandle: 'source-right', targetHandle: 'target-left' }
        return {
          id: edge.id,
          source: sourceNode?.id || edge.source,
          target: targetNode?.id || edge.target,
          sourceHandle: handles.sourceHandle,
          targetHandle: handles.targetHandle,
          type: 'default',
          data: {
            edge_type: edge.edge_type,
            condition: edge.condition,
            trigger_action: edge.trigger_action,
            pre_action: edge.pre_action,
            note: edge.note,
          },
          label: edge.label || '连线',
        }
      })
    vueFlowEdges.value = applyAllEdgeStyles(rawEdges as unknown as FlowGraphEdge[])
    saveSnapshot()
    isRestoredFromBackend.value = true
    emitSortData()
  }

  watch(
    () => flowSortStore.isBackendLoaded,
    (isLoaded, wasLoaded) => {
      if (isLoaded && !wasLoaded && flowSortStore.nodes.length > 0) {
        nextTick(() => syncStoreToEditor())
      }
    }
  )

  onMounted(() => {
    if (editorRef.value) editorRef.value.focus()
    if (
      flowSortStore.isBackendLoaded &&
      flowSortStore.nodes.length > 0 &&
      !isRestoredFromBackend.value
    ) {
      nextTick(() => syncStoreToEditor())
    }
    setTimeout(() => {
      showShortcutsTip.value = false
    }, SHORTCUTS_TIP_DURATION)
  })
}
