import { uiPrototypeApi, type UIScreen } from '@/api/uiPrototype'
import { fileApi } from '@/api/file'
import { useFlowSortStore, type FlowEdgeData, type FlowNodeData } from '@/store/flowSort'
import { extractListItems } from './types'
import type { GenerateState } from './state'
import type { StoreActions } from './types'

export function createUiPrototypeActions(state: GenerateState, getActions: () => StoreActions) {
  const loadUIPrototypeProjects = async () => {
    if (!state.formData.project_id) return
    try {
      const response = await uiPrototypeApi.getUIPrototypeProjectList(
        state.formData.project_id as number
      )
      state.uiPrototypeProjects.value = extractListItems(
        response
      ) as import('@/api/uiPrototype').UIPrototypeProject[]
    } catch (error) {
      console.error('获取 UI 原型项目列表失败:', error)
    }
  }

  const cleanupScreenImages = () => {
    Object.values(state.screenImageUrls.value).forEach((url) => {
      if (url.startsWith('blob:')) {
        URL.revokeObjectURL(url)
      }
    })
    state.screenImageUrls.value = {}
  }

  const loadScreenImages = async () => {
    if (state.isLoadingScreenImages.value) return
    state.isLoadingScreenImages.value = true
    try {
      const screensToLoad = state.uiScreens.value.filter(
        (screen) =>
          screen.id && screen.original_file_path && !state.screenImageUrls.value[screen.id]
      )
      const BATCH_SIZE = 5
      for (let i = 0; i < screensToLoad.length; i += BATCH_SIZE) {
        const batch = screensToLoad.slice(i, i + BATCH_SIZE)
        await Promise.allSettled(
          batch.map(async (screen) => {
            try {
              const response = await fileApi.getPreviewScreen(screen.id)
              const blob =
                response.data instanceof Blob
                  ? response.data
                  : new Blob([response.data], { type: 'image/jpeg' })
              if (blob.size > 0) {
                const oldUrl = state.screenImageUrls.value[screen.id]
                if (oldUrl?.startsWith('blob:')) {
                  URL.revokeObjectURL(oldUrl)
                }
                state.screenImageUrls.value[screen.id] = URL.createObjectURL(blob)
              }
            } catch (e) {
              console.warn(`加载屏幕图片失败: ${screen.id}`, e)
            }
          })
        )
      }
    } finally {
      state.isLoadingScreenImages.value = false
    }
  }

  const loadUIScreens = async (uiPrototypeProjectId: number) => {
    if (!state.formData.project_id) return
    try {
      const response = await uiPrototypeApi.getUIScreenList(
        state.formData.project_id as number,
        uiPrototypeProjectId
      )
      state.uiScreens.value = (extractListItems(response) as UIScreen[]).sort(
        (a: UIScreen, b: UIScreen) => (a.screen_order || 0) - (b.screen_order || 0)
      )
      cleanupScreenImages()
      await loadScreenImages()
    } catch (error) {
      console.error('获取 UI 屏幕列表失败:', error)
      state.uiScreens.value = []
      cleanupScreenImages()
    }
  }

  const buildNodeElements = (screen: UIScreen): FlowNodeData['ui_spec_elements'] => {
    return (screen.ui_spec?.elements || []).map((el) => ({
      type: el.type,
      label: el.label,
      semantic: el.semantic_hint || el.description,
      position: typeof el.position === 'string' ? el.position : JSON.stringify(el.position),
      interactive: el.interactive,
      state: el.state,
      description: el.description,
    }))
  }

  const buildDefaultFlowNodes = (): FlowNodeData[] => {
    return state.uiScreens.value.map((screen, index) => ({
      id: `node_${screen.id}`,
      screen_id: screen.id,
      screen_name: screen.screen_name,
      summary: screen.summary || '',
      ui_spec_elements: buildNodeElements(screen),
      flow_type: 'main',
      main_order: index + 1,
      image_url: state.screenImageUrls.value[screen.id] || '',
      position: { x: index * 280, y: 0 },
    }))
  }

  const buildDefaultFlowEdges = (nodes: FlowNodeData[]): FlowEdgeData[] => {
    return nodes.slice(0, -1).map((node, index) => {
      const next = nodes[index + 1]
      return {
        id: `auto_${node.id}_${next.id}`,
        source: String(node.screen_id),
        target: String(next.screen_id),
        edge_type: 'normal',
        label: '连线',
      }
    })
  }

  const syncFlowSortStoreWithCurrentScreens = () => {
    const flowSortStore = useFlowSortStore()
    const screenById = new Map(state.uiScreens.value.map((screen) => [screen.id, screen]))
    if (screenById.size === 0) {
      flowSortStore.updateNodes([])
      flowSortStore.updateEdges([])
      return
    }

    const compatibleNodes = flowSortStore.nodes.filter((node) => screenById.has(node.screen_id))
    if (compatibleNodes.length === 0) {
      const nodes = buildDefaultFlowNodes()
      flowSortStore.updateNodes(nodes)
      flowSortStore.updateEdges(buildDefaultFlowEdges(nodes))
      return
    }

    const validScreenIds = new Set(compatibleNodes.map((node) => String(node.screen_id)))
    const validNodeIds = new Set(compatibleNodes.map((node) => node.id))
    const compatibleEdges = flowSortStore.edges.filter((edge) => {
      const source = String(edge.source)
      const target = String(edge.target)
      return (
        (validScreenIds.has(source) || validNodeIds.has(source)) &&
        (validScreenIds.has(target) || validNodeIds.has(target))
      )
    })
    const hydratedNodes = compatibleNodes.map((node, index) => {
      const screen = screenById.get(node.screen_id)
      return {
        ...node,
        screen_name: screen?.screen_name || node.screen_name,
        summary: screen?.summary || node.summary || '',
        ui_spec_elements: screen ? buildNodeElements(screen) : node.ui_spec_elements,
        image_url: state.screenImageUrls.value[node.screen_id] || node.image_url || '',
        main_order: node.flow_type === 'main' ? node.main_order || index + 1 : node.main_order,
      }
    })
    flowSortStore.updateNodes(hydratedNodes)
    flowSortStore.updateEdges(compatibleEdges)
  }

  const handleUIPrototypeProjectChange = async (projectId: number | string) => {
    state.showParseWarning.value = true
    state.lastContext.value = {}
    state.selectedUiPrototypeProjectId.value = projectId as number | ''
    const flowSortStore = useFlowSortStore()
    state.uiScreens.value = []
    state.formData.ui_screen_ids = []
    cleanupScreenImages()
    flowSortStore.reset()
    if (projectId) {
      if (state.formData.project_id) {
        flowSortStore.setProjectId(state.formData.project_id as number)
      }
      await getActions().loadUIScreens(projectId as number)
      if (state.formData.project_id) {
        await flowSortStore.loadFromBackend()
      }
      syncFlowSortStoreWithCurrentScreens()
      state.formData.ui_screen_ids = state.uiScreens.value.map((s) => s.id)
    } else {
      flowSortStore.reset()
    }
  }

  return {
    loadUIPrototypeProjects,
    loadUIScreens,
    loadScreenImages,
    handleUIPrototypeProjectChange,
    cleanupScreenImages,
  }
}
