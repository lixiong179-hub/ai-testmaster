import { ref, computed, onUnmounted, type Ref, type ComputedRef } from 'vue'
import type { FlowEditorNode, EditorNodeData } from '@/composables/useFlowEditor'

/** 搜索结果项 */
export interface FlowSearchResultItem {
  id: string
  screen_name: string
  flow_type: string
}

/** useFlowSearch 入参 */
export interface UseFlowSearchOptions {
  vueFlowNodes: Ref<FlowEditorNode[]>
  getNodeData: (node: FlowEditorNode) => EditorNodeData
  fitView: (options?: Record<string, unknown>) => void
}

/** useFlowSearch 返回值 */
export interface UseFlowSearchReturn {
  searchKeyword: Ref<string>
  searchResults: ComputedRef<FlowSearchResultItem[]>
  searchMatchIds: Ref<string[]>
  showSearchDropdown: Ref<boolean>
  debouncedSearch: () => void
  clearSearch: () => void
  locateNode: (nodeId: string) => void
  locateFirstMatch: () => void
  handleSearchBlur: () => void
}

/**
 * 流程编辑器搜索定位 composable
 * 负责节点搜索、匹配高亮、视图定位等逻辑
 */
export function useFlowSearch(options: UseFlowSearchOptions): UseFlowSearchReturn {
  const { vueFlowNodes, getNodeData, fitView } = options

  // ---------- 状态 ----------
  const searchKeyword = ref('')
  const searchMatchIds = ref<string[]>([])
  const showSearchDropdown = ref(false)
  let searchTimer: ReturnType<typeof setTimeout> | null = null

  // ---------- 计算属性 ----------
  /** 根据关键词过滤节点，匹配 screen_name 或 summary */
  const searchResults = computed<FlowSearchResultItem[]>(() => {
    const keyword = searchKeyword.value.trim().toLowerCase()
    if (!keyword) return []
    return vueFlowNodes.value
      .filter((node) => {
        const name = getNodeData(node).screen_name?.toLowerCase() || ''
        const summary = getNodeData(node).summary?.toLowerCase() || ''
        return name.includes(keyword) || summary.includes(keyword)
      })
      .map((node) => ({
        id: node.id,
        screen_name: getNodeData(node).screen_name,
        flow_type: getNodeData(node).flow_type,
      }))
  })

  // ---------- 方法 ----------

  /** 定位到指定节点：高亮该节点并适配视图 */
  const locateNode = (nodeId: string): void => {
    searchMatchIds.value = [nodeId]
    showSearchDropdown.value = false
    void fitView({ nodes: [nodeId], duration: 300, padding: 0.3 })
  }

  /** 定位到第一个搜索结果 */
  const locateFirstMatch = (): void => {
    if (searchResults.value.length > 0) {
      locateNode(searchResults.value[0].id)
    }
  }

  /**
   * 处理搜索定位：更新匹配节点列表并定位到指定节点
   * @param nodeId - 需要定位的节点 ID
   */
  const handleSearchLocate = (nodeId: string): void => {
    const keyword = searchKeyword.value.trim().toLowerCase()
    if (!keyword) {
      searchMatchIds.value = []
      return
    }
    searchMatchIds.value = searchResults.value.map((r) => r.id)
    showSearchDropdown.value = true
    locateNode(nodeId)
  }

  /** 防抖搜索：300ms 后执行搜索定位 */
  const debouncedSearch = (): void => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      const keyword = searchKeyword.value.trim().toLowerCase()
      if (!keyword) {
        searchMatchIds.value = []
        return
      }
      searchMatchIds.value = searchResults.value.map((r) => r.id)
      showSearchDropdown.value = true
      if (searchResults.value.length > 0) {
        handleSearchLocate(searchResults.value[0].id)
      }
    }, 300)
  }

  /** 清除搜索状态 */
  const clearSearch = (): void => {
    searchMatchIds.value = []
    showSearchDropdown.value = false
    if (searchTimer) clearTimeout(searchTimer)
  }

  /** 搜索输入失焦处理：延迟关闭下拉列表 */
  const handleSearchBlur = (): void => {
    setTimeout(() => {
      showSearchDropdown.value = false
    }, 200)
  }

  // ---------- 生命周期 ----------
  onUnmounted(() => {
    if (searchTimer) clearTimeout(searchTimer)
  })

  return {
    searchKeyword,
    searchResults,
    searchMatchIds,
    showSearchDropdown,
    debouncedSearch,
    clearSearch,
    locateNode,
    locateFirstMatch,
    handleSearchBlur,
  }
}
