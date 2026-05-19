import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { uiPrototypeApi, type ProjectFlowData } from '@/api/uiPrototype'
import { ElMessage } from 'element-plus'
import { STORAGE_KEY, computeHash, extractStatusFromError, mapNodesToFlowData, mapEdgesToFlowData } from './flowSortTypes'
import type { FlowSortData, FlowNodeData, FlowEdgeData, FlowMetaData } from './flowSortTypes'

export type { FlowMetaData, FlowNodeData, FlowEdgeData, FlowSortData } from './flowSortTypes'

const DEBOUNCE_MS = 2000
const RETRY_DELAY_MS = 3000
const IDLE_DELAY_MS = 3000

export const useFlowSortStore = defineStore('flowSort', () => {
  const saved = localStorage.getItem(STORAGE_KEY)
  let initialProjectId: number | null = null
  let initial: FlowSortData | null = null
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      if (parsed._project_id != null) { initialProjectId = parsed._project_id; delete (parsed as Record<string, unknown>)._project_id }
      initial = parsed as FlowSortData
    } catch { localStorage.removeItem(STORAGE_KEY) }
  }

  const mode = ref<'linear' | 'graph'>(initial?.mode || 'graph')
  const nodes = ref<FlowNodeData[]>(initial?.nodes || [])
  const rawEdges = initial?.edges || []
  const edges = ref<FlowEdgeData[]>(rawEdges.map((e) => ({ ...e, label: e.label || '连线' })))
  const moduleInfo = ref<{ name: string; description: string } | null>(initial?.module_info || null)
  const projectId = ref<number | null>(initialProjectId)
  const saveStatus = ref<'idle' | 'unsaved' | 'saving' | 'saved' | 'error'>('idle')
  const lastSavedHash = ref<string>('')
  const isBackendLoaded = ref(true)

  let autoSaveTimer: ReturnType<typeof setTimeout> | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let idleTimer: ReturnType<typeof setTimeout> | null = null

  const sortData = computed<FlowSortData>(() => ({ mode: mode.value, nodes: nodes.value, edges: edges.value, module_info: moduleInfo.value || undefined }))

  function setMode(newMode: 'linear' | 'graph') { mode.value = newMode }
  function updateNodes(newNodes: FlowNodeData[]) { nodes.value = newNodes; persistToStorage() }
  function updateEdges(newEdges: FlowEdgeData[]) { edges.value = newEdges; persistToStorage() }

  function persistToStorage() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...sortData.value, _project_id: projectId.value })) } catch { /* silent */ }
  }

  function setModuleInfo(info: { name: string; description: string } | null) { moduleInfo.value = info }
  function setProjectId(id: number) { projectId.value = id; if (saveStatus.value === 'unsaved') triggerAutoSave() }

  function triggerAutoSave() {
    const currentHash = computeHash(sortData.value)
    if (currentHash === lastSavedHash.value && projectId.value != null) return
    if (projectId.value == null) { saveStatus.value = 'unsaved'; return }
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    saveStatus.value = 'unsaved'
    autoSaveTimer = setTimeout(() => { void performSave() }, DEBOUNCE_MS)
  }

  async function performSave(retryOn5xx = true): Promise<void> {
    if (projectId.value == null) return
    if (retryOn5xx) {
      const currentHash = computeHash(sortData.value)
      if (currentHash === lastSavedHash.value) { saveStatus.value = 'saved'; return }
    }
    saveStatus.value = 'saving'
    try {
      const flowData: ProjectFlowData = {
        nodes: mapNodesToFlowData(nodes.value), edges: mapEdgesToFlowData(edges.value),
        module_info: moduleInfo.value ? { name: moduleInfo.value.name, description: moduleInfo.value.description } : undefined,
      }
      await uiPrototypeApi.saveProjectFlowData(projectId.value, flowData)
      saveStatus.value = 'saved'
      if (idleTimer) clearTimeout(idleTimer)
      idleTimer = setTimeout(() => { saveStatus.value = 'idle' }, IDLE_DELAY_MS)
      lastSavedHash.value = computeHash(sortData.value)
    } catch (error: unknown) {
      const status = extractStatusFromError(error)
      const isRetryable = (status != null && status >= 500 && status < 600) || status === null
      if (isRetryable && retryOn5xx) {
        ElMessage.warning(status === null ? '保存超时，3秒后自动重试...' : '服务器繁忙，3秒后自动重试保存...')
        if (retryTimer) clearTimeout(retryTimer)
        retryTimer = setTimeout(() => { void performSave(false) }, RETRY_DELAY_MS)
        return
      }
      const statusMsg = status === 404 ? '流程数据接口未注册，请检查后端路由' : status === 400 ? '保存数据校验失败，请检查节点和连线数据' : status === 422 ? '流程数据为空，请确保至少有一个节点' : status === null ? '保存超时，请检查网络或稍后重试' : `服务器错误 (${status})`
      ElMessage.error(`保存失败: ${statusMsg}`)
      saveStatus.value = 'error'
    }
  }

  async function loadFromBackend() {
    if (projectId.value == null) return
    isBackendLoaded.value = false
    let backendLoaded = false
    try {
      const res = await uiPrototypeApi.getProjectFlowData(projectId.value)
      const data = res as unknown as { data?: { flow_data?: ProjectFlowData } }
      if (data?.data?.flow_data) {
        const backendData = data.data.flow_data
        nodes.value = backendData.nodes.map((n) => ({
          id: n.id, screen_id: n.screen_id, screen_name: n.screen_name, summary: n.summary,
          ui_spec_elements: n.ui_spec_elements as FlowNodeData['ui_spec_elements'], flow_type: n.flow_type,
          main_order: n.main_order, image_url: n.image_url || '', position: n.position || { x: 0, y: 0 },
          flow_meta: n.flow_meta as FlowMetaData,
        }))
        edges.value = backendData.edges.map((e) => ({
          id: e.id, source: e.source, target: e.target, edge_type: e.edge_type,
          condition: e.condition, label: e.label || '连线', trigger_action: e.trigger_action,
          pre_action: e.pre_action, note: e.note,
        }))
        if (backendData.module_info) moduleInfo.value = { name: backendData.module_info.name, description: backendData.module_info.description }
        lastSavedHash.value = computeHash(sortData.value)
        persistToStorage()
        if (autoSaveTimer) { clearTimeout(autoSaveTimer); autoSaveTimer = null; saveStatus.value = 'idle' }
        isBackendLoaded.value = true; backendLoaded = true
        return
      }
    } catch (e) { console.error('[FlowSort] 从后端加载流程数据失败:', e) }
    if (!backendLoaded) {
      const currentSaved = localStorage.getItem(STORAGE_KEY)
      if (currentSaved) {
        try {
          const localData = JSON.parse(currentSaved) as FlowSortData & { _project_id?: number }
          if (localData._project_id != null && localData._project_id !== projectId.value) { /* skip */ }
          else {
            localData.edges = (localData.edges || []).map((e) => ({ ...e, label: e.label || '连线' }))
            nodes.value = localData.nodes || []; edges.value = localData.edges
            moduleInfo.value = localData.module_info || null; triggerAutoSave()
          }
        } catch { /* silent */ }
      }
    }
    isBackendLoaded.value = true
  }

  function manualSave() { if (autoSaveTimer) clearTimeout(autoSaveTimer); void performSave(true) }
  function manualRetrySave() { if (autoSaveTimer) clearTimeout(autoSaveTimer); void performSave(true) }

  function reset() {
    mode.value = 'graph'; nodes.value = []; edges.value = []; moduleInfo.value = null
    projectId.value = null; initialProjectId = null; saveStatus.value = 'idle'
    lastSavedHash.value = ''; isBackendLoaded.value = true; localStorage.removeItem(STORAGE_KEY)
    if (autoSaveTimer) clearTimeout(autoSaveTimer); if (retryTimer) clearTimeout(retryTimer); if (idleTimer) clearTimeout(idleTimer)
  }

  function toJson(): string { return JSON.stringify(sortData.value) }
  function fromJson(json: string) {
    try {
      const data = JSON.parse(json) as FlowSortData
      mode.value = data.mode || 'graph'; nodes.value = data.nodes || []
      edges.value = (data.edges || []).map((e) => ({ ...e, label: e.label || '连线' }))
      moduleInfo.value = data.module_info || null
    } catch { reset() }
  }

  return { mode, nodes, edges, moduleInfo, sortData, projectId, saveStatus, isBackendLoaded, setMode, updateNodes, updateEdges, setModuleInfo, setProjectId, triggerAutoSave, loadFromBackend, manualSave, manualRetrySave, reset, toJson, fromJson }
})
