import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { uiPrototypeApi, type ProjectFlowData } from '@/api/uiPrototype'

const STORAGE_KEY = 'flow-sort-data'
const DEBOUNCE_MS = 2000
const RETRY_DELAY_MS = 3000
const STATUS_HIDE_MS = 3000

function extractStatusFromError(error: unknown): number | null {
    const e = error as Record<string, unknown> | null
    if (!e) return null

    const response = e.response as Record<string, unknown> | undefined
    if (response && typeof response.status === 'number') return response.status

    if (typeof e.status === 'number') return e.status

    return null
}

function computeHash(data: FlowSortData): string {
    try {
        const payload = JSON.stringify(data)
        let hash = 0
        for (let i = 0; i < payload.length; i++) {
            const char = payload.charCodeAt(i)
            hash = ((hash << 5) - hash) + char
            hash |= 0
        }
        return String(hash)
    } catch {
        return ''
    }
}

export interface FlowMetaData {
  /** 挂靠父节点 ID，支持主干/分支/异常/旁路任意节点 */
  parent_node_id?: string
  /** @deprecated 使用 parent_node_id 代替，仅兼容旧数据 */
  parent_main_node_id?: string
  trigger_condition?: string
  pre_action?: string
  expected_result?: string
  bypass_reason?: string
  note?: string
}

export interface FlowNodeData {
  id: string
  screen_id: number
  screen_name: string
  summary?: string
  ui_spec_elements?: Array<{
    type: string
    label: string
    semantic?: string
    position?: string
    interactive?: boolean
  }>
  flow_type: 'main' | 'branch' | 'exception' | 'bypass'
  main_order?: number
  image_url?: string
  position: { x: number; y: number }
  flow_meta?: FlowMetaData
}

export interface FlowEdgeData {
  id: string
  source: string
  target: string
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition?: string
  label: string
  trigger_action?: string
  pre_action?: string
  note?: string
}

export interface FlowSortData {
  mode: 'linear' | 'graph'
  nodes: FlowNodeData[]
  edges: FlowEdgeData[]
  module_info?: {
    name: string
    description: string
  }
}

export const useFlowSortStore = defineStore('flowSort', () => {
  const saved = localStorage.getItem(STORAGE_KEY)
  let initial: FlowSortData | null = null
  if (saved) {
    try {
      initial = JSON.parse(saved) as FlowSortData
    } catch {
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  const mode = ref<'linear' | 'graph'>(initial?.mode || 'graph')
  const nodes = ref<FlowNodeData[]>(initial?.nodes || [])
  const edges = ref<FlowEdgeData[]>(initial?.edges || [])
  const moduleInfo = ref<{ name: string; description: string } | null>(initial?.module_info || null)
  const projectId = ref<number | null>(null)
  const saveStatus = ref<'idle' | 'unsaved' | 'saving' | 'saved' | 'error'>('idle')
  const lastSavedHash = ref<string>('')
  const isBackendLoaded = ref(true)

  let autoSaveTimer: ReturnType<typeof setTimeout> | null = null
  let statusTimer: ReturnType<typeof setTimeout> | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null

  const sortData = computed<FlowSortData>(() => ({
    mode: mode.value,
    nodes: nodes.value,
    edges: edges.value,
    module_info: moduleInfo.value || undefined,
  }))

  function setMode(newMode: 'linear' | 'graph') {
    mode.value = newMode
  }

  function updateNodes(newNodes: FlowNodeData[]) {
    nodes.value = newNodes
    persistToStorage()
  }

  function updateEdges(newEdges: FlowEdgeData[]) {
    edges.value = newEdges
    persistToStorage()
  }

  function persistToStorage() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sortData.value))
    } catch {
    }
  }

  function setModuleInfo(info: { name: string; description: string } | null) {
    moduleInfo.value = info
  }

  function setProjectId(id: number) {
    projectId.value = id
  }

  function triggerAutoSave() {
    if (projectId.value == null) return
    const currentHash = computeHash(sortData.value)
    if (currentHash === lastSavedHash.value) return

    if (autoSaveTimer) clearTimeout(autoSaveTimer)

    saveStatus.value = 'unsaved'
    autoSaveTimer = setTimeout(() => {
      void performSave()
    }, DEBOUNCE_MS)
  }

  async function performSave(retryOn5xx = true) {
    if (projectId.value == null) return
    saveStatus.value = 'saving'

    try {
      const flowData: ProjectFlowData = {
        nodes: nodes.value.map((n) => ({
          id: n.id,
          screen_id: n.screen_id,
          screen_name: n.screen_name,
          summary: n.summary,
          ui_spec_elements: n.ui_spec_elements as ProjectFlowData['nodes'][0]['ui_spec_elements'],
          flow_type: n.flow_type,
          main_order: n.main_order,
          image_url: n.image_url,
          position: n.position,
          flow_meta: n.flow_meta as ProjectFlowData['nodes'][0]['flow_meta'],
        })),
        edges: edges.value.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          edge_type: e.edge_type,
          condition: e.condition,
          label: e.label,
          trigger_action: e.trigger_action,
          pre_action: e.pre_action,
          note: e.note,
        })),
        module_info: moduleInfo.value
          ? { name: moduleInfo.value.name, description: moduleInfo.value.description }
          : undefined,
      }
      await uiPrototypeApi.saveProjectFlowData(projectId.value, flowData)
      saveStatus.value = 'saved'
      lastSavedHash.value = computeHash(sortData.value)

      if (statusTimer) clearTimeout(statusTimer)
      statusTimer = setTimeout(() => {
        saveStatus.value = 'idle'
      }, STATUS_HIDE_MS)
    } catch (error: unknown) {
      const status = extractStatusFromError(error)

      if (status != null && status >= 500 && status < 600 && retryOn5xx) {
        if (retryTimer) clearTimeout(retryTimer)
        retryTimer = setTimeout(() => {
          void performSave(false)
        }, RETRY_DELAY_MS)
        return
      }

      saveStatus.value = 'error'
    }
  }

  async function loadFromBackend() {
    if (projectId.value == null) return

    isBackendLoaded.value = false

    try {
      const res = await uiPrototypeApi.getProjectFlowData(projectId.value)
      const data = res as unknown as { data?: { flow_data?: ProjectFlowData } }
      if (data?.data?.flow_data) {
        const backendData = data.data.flow_data
        nodes.value = backendData.nodes.map((n) => ({
          id: n.id,
          screen_id: n.screen_id,
          screen_name: n.screen_name,
          summary: n.summary,
          ui_spec_elements: n.ui_spec_elements as FlowNodeData['ui_spec_elements'],
          flow_type: n.flow_type,
          main_order: n.main_order,
          image_url: n.image_url || '',
          position: n.position || { x: 0, y: 0 },
          flow_meta: n.flow_meta as FlowMetaData,
        }))
        edges.value = backendData.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          edge_type: e.edge_type,
          condition: e.condition,
          label: e.label || '',
          trigger_action: e.trigger_action,
          pre_action: e.pre_action,
          note: e.note,
        }))
        if (backendData.module_info) {
          moduleInfo.value = {
            name: backendData.module_info.name,
            description: backendData.module_info.description,
          }
        }
        lastSavedHash.value = computeHash(sortData.value)
        persistToStorage()
        isBackendLoaded.value = true
        return
      }
    } catch (e) {
      console.error('从后端加载流程数据失败:', e)
    }

    if (nodes.value.length === 0 && saved) {
      try {
        const localData = JSON.parse(saved) as FlowSortData
        nodes.value = localData.nodes || []
        edges.value = localData.edges || []
        moduleInfo.value = localData.module_info || null
        triggerAutoSave()
      } catch {
      }
    }
    isBackendLoaded.value = true
  }

  function manualSave() {
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    void performSave(true)
  }

  function manualRetrySave() {
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    void performSave(true)
  }

  function reset() {
    mode.value = 'graph'
    nodes.value = []
    edges.value = []
    moduleInfo.value = null
    projectId.value = null
    saveStatus.value = 'idle'
    lastSavedHash.value = ''
    isBackendLoaded.value = true
    localStorage.removeItem(STORAGE_KEY)
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    if (statusTimer) clearTimeout(statusTimer)
    if (retryTimer) clearTimeout(retryTimer)
  }

  function toJson(): string {
    return JSON.stringify(sortData.value)
  }

  function fromJson(json: string) {
    try {
      const data = JSON.parse(json) as FlowSortData
      mode.value = data.mode || 'graph'
      nodes.value = data.nodes || []
      edges.value = data.edges || []
      moduleInfo.value = data.module_info || null
    } catch {
      reset()
    }
  }

  return {
    mode,
    nodes,
    edges,
    moduleInfo,
    sortData,
    projectId,
    saveStatus,
    isBackendLoaded,
    setMode,
    updateNodes,
    updateEdges,
    setModuleInfo,
    setProjectId,
    triggerAutoSave,
    loadFromBackend,
    manualSave,
    manualRetrySave,
    reset,
    toJson,
    fromJson,
  }
})
