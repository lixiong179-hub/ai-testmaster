import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { uiPrototypeApi, type ProjectFlowData } from '@/api/uiPrototype'
import { ElMessage } from 'element-plus'

const STORAGE_KEY = 'flow-sort-data'
const DEBOUNCE_MS = 2000
const RETRY_DELAY_MS = 3000
const IDLE_DELAY_MS = 3000

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
        let h1 = 0xdeadbeef
        let h2 = 0x41c6ce57
        for (let i = 0; i < payload.length; i++) {
            const ch = payload.charCodeAt(i)
            h1 = Math.imul(h1 ^ ch, 2654435761)
            h2 = Math.imul(h2 ^ ch, 1597334677)
        }
        h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909)
        h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909)
        return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36)
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
    state?: string
    description?: string
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
  let initialProjectId: number | null = null
  let initial: FlowSortData | null = null
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      if (parsed._project_id != null) {
        initialProjectId = parsed._project_id
        delete (parsed as Record<string, unknown>)._project_id
      }
      initial = parsed as FlowSortData
    } catch {
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  const mode = ref<'linear' | 'graph'>(initial?.mode || 'graph')
  const nodes = ref<FlowNodeData[]>(initial?.nodes || [])
  const rawEdges = initial?.edges || []
  const edges = ref<FlowEdgeData[]>(rawEdges.map((e) => ({
    ...e,
    label: e.label || '连线',
  })))
  const moduleInfo = ref<{ name: string; description: string } | null>(initial?.module_info || null)
  const projectId = ref<number | null>(initialProjectId)
  const saveStatus = ref<'idle' | 'unsaved' | 'saving' | 'saved' | 'error'>('idle')
  const lastSavedHash = ref<string>('')
  const isBackendLoaded = ref(true)

  let autoSaveTimer: ReturnType<typeof setTimeout> | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let idleTimer: ReturnType<typeof setTimeout> | null = null

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
      const dataWithProjectId = {
        ...sortData.value,
        _project_id: projectId.value,
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(dataWithProjectId))
    } catch {
      // localStorage 写入失败（如配额超限）时静默降级
    }
  }

  function setModuleInfo(info: { name: string; description: string } | null) {
    moduleInfo.value = info
  }

  function setProjectId(id: number) {
    projectId.value = id
    if (saveStatus.value === 'unsaved') {
      triggerAutoSave()
    }
  }

  function triggerAutoSave() {
    const currentHash = computeHash(sortData.value)
    if (currentHash === lastSavedHash.value && projectId.value != null) return

    if (projectId.value == null) {
      console.warn('[FlowSort] triggerAutoSave: projectId 为空，标记为未保存')
      saveStatus.value = 'unsaved'
      return
    }

    if (autoSaveTimer) clearTimeout(autoSaveTimer)

    saveStatus.value = 'unsaved'
    autoSaveTimer = setTimeout(() => {
      void performSave()
    }, DEBOUNCE_MS)
  }

  async function performSave(retryOn5xx = true): Promise<void> {
    if (projectId.value == null) return

    if (retryOn5xx) {
      const currentHash = computeHash(sortData.value)
      if (currentHash === lastSavedHash.value) {
        console.log('[FlowSort] 数据未变更，跳过保存')
        saveStatus.value = 'saved'
        return
      }
    }
    saveStatus.value = 'saving'
    console.log('[FlowSort] 开始保存，projectId:', projectId.value, 'nodes:', nodes.value.length, 'edges:', edges.value.length)

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
      console.log('[FlowSort] 保存成功')
      if (idleTimer) clearTimeout(idleTimer)
      idleTimer = setTimeout(() => {
        saveStatus.value = 'idle'
      }, IDLE_DELAY_MS)
      lastSavedHash.value = computeHash(sortData.value)
    } catch (error: unknown) {
      const status = extractStatusFromError(error)
      console.error('[FlowSort] 保存失败, HTTP状态码:', status, '错误:', error)

      const isRetryable = (status != null && status >= 500 && status < 600) || status === null
      if (isRetryable && retryOn5xx) {
        ElMessage.warning(status === null ? '保存超时，3秒后自动重试...' : '服务器繁忙，3秒后自动重试保存...')
        if (retryTimer) clearTimeout(retryTimer)
        retryTimer = setTimeout(() => {
          void performSave(false)
        }, RETRY_DELAY_MS)
        return
      }

      const statusMsg = status === 404 ? '流程数据接口未注册，请检查后端路由' :
        status === 400 ? '保存数据校验失败，请检查节点和连线数据' :
        status === 422 ? '流程数据为空，请确保至少有一个节点' :
        status === null ? '保存超时，请检查网络或稍后重试' :
        `服务器错误 (${status})`
      ElMessage.error(`保存失败: ${statusMsg}`)
      saveStatus.value = 'error'
    }
  }

  async function loadFromBackend() {
    if (projectId.value == null) return
    isBackendLoaded.value = false
    console.log('[FlowSort] 开始从后端加载，projectId:', projectId.value)

    let backendLoaded = false
    try {
      const res = await uiPrototypeApi.getProjectFlowData(projectId.value)
      const data = res as unknown as { data?: { flow_data?: ProjectFlowData } }
      if (data?.data?.flow_data) {
        const backendData = data.data.flow_data
        console.log(
          '[FlowSort] 后端数据: nodes', backendData.nodes?.length,
          'edges', backendData.edges?.length,
          'module_info', backendData.module_info ? '存在' : '不存在'
        )
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
          label: e.label || '连线',
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

        if (autoSaveTimer) {
          clearTimeout(autoSaveTimer)
          autoSaveTimer = null
          saveStatus.value = 'idle'
          console.log('[FlowSort] 已清除待保存定时器，防止默认数据覆盖后端数据')
        }

        isBackendLoaded.value = true
        backendLoaded = true
        console.log('[FlowSort] 后端加载完成')
        return
      }
      console.log('[FlowSort] 后端无保存数据')
    } catch (e) {
      console.error('[FlowSort] 从后端加载流程数据失败:', e)
    }

    if (!backendLoaded) {
      const currentSaved = localStorage.getItem(STORAGE_KEY)
      if (currentSaved) {
        try {
          const localData = JSON.parse(currentSaved) as FlowSortData & { _project_id?: number }
          if (localData._project_id != null && localData._project_id !== projectId.value) {
            console.log('[FlowSort] localStorage 数据属于其他项目(%d)，跳过', localData._project_id)
          } else {
            localData.edges = (localData.edges || []).map((e) => ({
              ...e,
              label: e.label || '连线',
            }))
            nodes.value = localData.nodes || []
            edges.value = localData.edges
            moduleInfo.value = localData.module_info || null
            triggerAutoSave()
            console.log('[FlowSort] 已从 localStorage 降级恢复数据')
          }
        } catch {
          // localStorage 数据损坏时静默降级
        }
      }
    }
    isBackendLoaded.value = true
  }

  function manualSave() {
    console.log('[FlowSort] 手动保存触发')
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    void performSave(true)
  }

  function manualRetrySave() {
    console.log('[FlowSort] 手动重试保存触发')
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    void performSave(true)
  }

  function reset() {
    mode.value = 'graph'
    nodes.value = []
    edges.value = []
    moduleInfo.value = null
    projectId.value = null
    initialProjectId = null
    saveStatus.value = 'idle'
    lastSavedHash.value = ''
    isBackendLoaded.value = true
    localStorage.removeItem(STORAGE_KEY)
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    if (retryTimer) clearTimeout(retryTimer)
    if (idleTimer) clearTimeout(idleTimer)
  }

  function toJson(): string {
    return JSON.stringify(sortData.value)
  }

  function fromJson(json: string) {
    try {
      const data = JSON.parse(json) as FlowSortData
      mode.value = data.mode || 'graph'
      nodes.value = data.nodes || []
      edges.value = (data.edges || []).map((e) => ({
        ...e,
        label: e.label || '连线',
      }))
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
