<template>
  <div
    class="flow-sort-editor"
    :class="{ 'overview-mode': displayMode === 'overview' }"
    @keydown="handleKeyDown"
    tabindex="0"
    ref="editorRef"
  >
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <div class="editor-heading">
          <span class="editor-title">页面流程编辑</span>
          <span class="editor-subtitle">拖拽节点调整布局，主干顺序使用前移/后移显式控制</span>
        </div>
        <div class="flow-legend">
          <span class="legend-item legend-main">主干</span>
          <span class="legend-item legend-branch">分支</span>
          <span class="legend-item legend-exception">异常</span>
          <span class="legend-item legend-bypass">旁路</span>
        </div>
      </div>
      <div class="toolbar-actions">
        <el-button-group class="mode-toggle">
          <el-button
            size="default"
            :type="displayMode === 'overview' ? 'primary' : ''"
            @click="displayMode = 'overview'"
          >
            总览
          </el-button>
          <el-button
            size="default"
            :type="displayMode === 'edit' ? 'primary' : ''"
            @click="displayMode = 'edit'"
          >
            编辑
          </el-button>
        </el-button-group>
        <el-divider direction="vertical" />
        <el-button-group class="action-group">
          <el-dropdown trigger="click" @command="handleLayoutModeChange">
            <el-button size="default" title="自动布局 (Ctrl+L)">
              <el-icon><Grid /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="(label, mode) in LAYOUT_MODE_LABELS"
                  :key="mode"
                  :command="mode"
                  :class="{ 'is-active': layoutMode === mode }"
                >
                  {{ label }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-tooltip content="预览 Prompt (Ctrl+P)" placement="bottom">
            <el-button size="default" @click="handlePreviewPrompt">
              <el-icon><View /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="适配视图 (Ctrl+0)" placement="bottom">
            <el-button size="default" @click="handleFitView">
              <el-icon><FullScreen /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="撤销 (Ctrl+Z)" placement="bottom">
            <el-button size="default" @click="handleUndo" :disabled="!canUndo">
              <el-icon><RefreshLeft /></el-icon>
            </el-button>
          </el-tooltip>
        </el-button-group>
        <el-divider direction="vertical" />
        <div v-if="selectedNodes.length > 0" class="selection-info">
          <el-tag type="primary" size="small" effect="plain">
            已选 {{ selectedNodes.length }} 个节点
          </el-tag>
          <el-button size="small" type="danger" @click="handleDeleteSelected">
            <el-icon><Delete /></el-icon>
            删除
          </el-button>
          <el-dropdown
            v-if="selectedNodes.length > 1"
            trigger="click"
            @command="handleBatchFlowTypeChange"
          >
            <el-button size="small" type="warning">
              批量设置类型
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="main">主干流程</el-dropdown-item>
                <el-dropdown-item command="branch">分支流程</el-dropdown-item>
                <el-dropdown-item command="exception">异常流程</el-dropdown-item>
                <el-dropdown-item command="bypass">旁路流程</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div v-if="getSelectedMainNodeId(vueFlowNodes)" class="main-order-actions">
          <el-tag type="success" size="small" effect="plain">
            主干第 {{ getSelectedMainOrder(vueFlowNodes) }} 步
          </el-tag>
          <el-button
            size="small"
            @click="moveSelectedMainNode(-1)"
            :disabled="!canMoveMainBackward()"
          >
            主干前移
          </el-button>
          <el-button
            size="small"
            @click="moveSelectedMainNode(1)"
            :disabled="!canMoveMainForward()"
          >
            主干后移
          </el-button>
        </div>
        <div v-if="canQuickCreateBranch" class="quick-create-branch-action">
          <el-button size="small" type="success" @click="handleQuickCreateBranch">
            <el-icon><Plus /></el-icon>
            创建分支
          </el-button>
        </div>
        <div class="zoom-controls">
          <el-tooltip content="智能识别跳转关系" placement="bottom">
            <el-button size="default" @click="showEdgeSuggestion = true">
              <el-icon><MagicStick /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip :content="isPlaying ? '退出路径播放' : '路径播放'" placement="bottom">
            <el-button
              size="default"
              :type="isPlaying ? 'primary' : ''"
              @click="isPlaying ? stopPlayback() : startPlayback(vueFlowNodes, vueFlowEdges as any)"
            >
              <el-icon><VideoPlay v-if="!isPlaying" /><VideoPause v-else /></el-icon>
            </el-button>
          </el-tooltip>
          <div class="search-wrapper">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索页面..."
              size="small"
              class="search-input"
              clearable
              :prefix-icon="Search"
              @input="debouncedSearch"
              @clear="clearSearch"
              @keydown.enter="locateFirstMatch"
              @focus="showSearchDropdown = true"
              @blur="handleSearchBlur"
            />
            <div v-if="showSearchDropdown && searchResults.length > 0" class="search-dropdown">
              <div
                v-for="item in searchResults"
                :key="item.id"
                class="search-result-item"
                @click="locateNode(item.id)"
              >
                <span class="result-name">{{ item.screen_name }}</span>
                <el-tag
                  size="small"
                  :type="FLOW_TYPE_TAG_MAP[item.flow_type] || 'primary'"
                  effect="plain"
                  class="result-tag"
                >
                  {{ FLOW_TYPE_LABEL_MAP[item.flow_type] || '主干' }}
                </el-tag>
              </div>
            </div>
            <div
              v-if="showSearchDropdown && searchKeyword && searchResults.length === 0"
              class="search-dropdown"
            >
              <div class="search-empty">未找到匹配页面</div>
            </div>
          </div>
        </div>
        <div class="save-status-area">
          <template v-if="flowSortStore.saveStatus === 'saving'">
            <span class="save-status-inner">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span class="save-text">保存中...</span>
            </span>
          </template>
          <template v-else-if="flowSortStore.saveStatus === 'saved'">
            <span class="save-status-inner">
              <el-icon color="#67c23a"><CircleCheck /></el-icon>
              <span class="save-text">已保存</span>
            </span>
          </template>
          <template v-else-if="flowSortStore.saveStatus === 'error'">
            <span
              class="save-status-inner save-error-wrapper"
              @click="flowSortStore.manualRetrySave()"
            >
              <el-icon color="#f56c6c" class="save-error-icon"><CircleClose /></el-icon>
              <span class="save-text error-text save-error-text">保存失败</span>
            </span>
          </template>
          <template v-else>
            <span class="save-status-inner">
              <el-icon color="#909399"><Clock /></el-icon>
              <span class="save-text">未保存</span>
            </span>
          </template>
        </div>
      </div>
    </div>

    <div class="editor-container">
      <div class="graph-mode">
        <VueFlow
          v-model:nodes="vueFlowNodes"
          v-model:edges="vueFlowEdges"
          @edges-change="onEdgesChange"
          :default-viewport="{ x: 0, y: 0, zoom: 1 }"
          :default-edge-options="defaultEdgeOptions"
          :min-zoom="0.2"
          :max-zoom="4"
          :nodes-draggable="displayMode === 'edit'"
          :nodes-connectable="displayMode === 'edit'"
          :elements-selectable="displayMode === 'edit'"
          fit-view-on-init
          @connect="onConnect"
          @node-drag-start="onNodeDragStart"
          @node-drag-stop="onNodeDragStop"
          @pane-click="handlePaneClick"
          @edge-mouse-enter="onEdgeMouseEnter"
          @edge-mouse-move="onEdgeMouseMove"
          @edge-mouse-leave="onEdgeMouseLeave"
          @node-click="handleNodeClick"
          @selection-change="handleSelectionChange"
        >
          <Background pattern-color="#e4e7ed" :gap="20" />
          <Controls />
          <MiniMap :node-color="minimapNodeColor" :node-stroke-color="minimapNodeStroke" />
          <svg
            v-if="showGroupBackground && nodeGroups.length > 0"
            class="group-bg-svg"
            :style="{ transform: `translate(${svgViewBox.x}px, ${svgViewBox.y}px) scale(${currentZoom})`, transformOrigin: '0 0' }"
          >
            <rect
              v-for="group in nodeGroups"
              :key="group.id"
              :x="group.bounds.x - groupPadding"
              :y="group.bounds.y - groupPadding"
              :width="group.bounds.width + groupPadding * 2"
              :height="group.bounds.height + groupPadding * 2"
              :rx="12"
              :fill="group.color"
              :stroke="group.strokeColor"
              stroke-width="1.5"
              stroke-dasharray="6 3"
              :opacity="0.25"
            />
            <text
              v-for="group in nodeGroups"
              :key="'label-' + group.id"
              :x="group.bounds.x - groupPadding + 8"
              :y="group.bounds.y - groupPadding + 16"
              font-size="12"
              :fill="group.strokeColor"
              :opacity="0.6"
            >{{ group.label }}</text>
          </svg>
          <template #node-custom="nodeProps">
            <FlowNodeCard
              :data="nodeProps.data"
              :is-selected="selectedNodes.includes(nodeProps.id)"
              :is-dragging="draggingNodeId === nodeProps.id"
              :display-mode="displayMode"
              :is-search-match="searchMatchIds.includes(nodeProps.id)"
              :is-focused="focusedNodeId === nodeProps.id"
              :is-upstream="upstreamNodeIds.has(nodeProps.id)"
              :is-downstream="downstreamNodeIds.has(nodeProps.id)"
              :is-path-dimmed="focusedNodeId !== null && !allPathNodeIds.has(nodeProps.id)"
              :child-branch-count="getChildBranchCount(nodeProps.id)"
              :is-collapsed="collapsedParentNodeIds.includes(nodeProps.id)"
              :is-test-point-related="highlightedScreenIds.has(nodeProps.data.screen_id)"
              @update:flow-type="(type: string) => handleFlowTypeChange(nodeProps.id, type)"
              @preview="handleNodePreview(nodeProps.data)"
              @toggle-collapse="(nodeId: string) => handleToggleCollapse(nodeId)"
            />
          </template>
        </VueFlow>
      </div>
    </div>

    <transition name="tooltip-fade">
      <div
        v-if="edgeTooltipVisible && edgeTooltipData"
        class="edge-tooltip"
        :style="{ left: edgeTooltipPosition.x + 'px', top: edgeTooltipPosition.y + 'px' }"
        @mouseenter="onEdgeTooltipEnter"
        @mouseleave="onEdgeTooltipLeave"
      >
        <div class="tooltip-header">
          <el-tag
            size="small"
            :type="FLOW_TYPE_TAG_MAP[edgeTooltipData.data?.edge_type] || 'primary'"
            effect="dark"
          >
            {{ FLOW_TYPE_LABEL_MAP[edgeTooltipData.data?.edge_type] || '跳转' }}
          </el-tag>
          <el-button
            size="small"
            :icon="Edit"
            circle
            class="tooltip-edit-btn"
            @click="handleEditEdge(edgeTooltipData)"
          />
          <el-button
            size="small"
            :icon="Delete"
            circle
            class="tooltip-delete-btn"
            type="danger"
            @click="handleDeleteEdge(edgeTooltipData)"
          />
        </div>
        <div v-if="edgeTooltipData.data?.condition" class="tooltip-row">
          <span class="tooltip-label">触发条件：</span>
          <span class="tooltip-value">{{ edgeTooltipData.data.condition }}</span>
        </div>
        <div v-if="edgeTooltipData.data?.trigger_action" class="tooltip-row">
          <span class="tooltip-label">触发动作：</span>
          <span class="tooltip-value">{{ edgeTooltipData.data.trigger_action }}</span>
        </div>
        <div v-if="edgeTooltipData.data?.pre_action" class="tooltip-row">
          <span class="tooltip-label">前置操作：</span>
          <span class="tooltip-value">{{ edgeTooltipData.data.pre_action }}</span>
        </div>
        <div v-if="edgeTooltipData.data?.note" class="tooltip-row">
          <span class="tooltip-label">备注：</span>
          <span class="tooltip-value">{{ edgeTooltipData.data.note }}</span>
        </div>
        <div
          v-if="
            !edgeTooltipData.data?.condition &&
            !edgeTooltipData.data?.trigger_action &&
            !edgeTooltipData.data?.pre_action &&
            !edgeTooltipData.data?.note
          "
          class="tooltip-row"
        >
          <span class="tooltip-value">普通跳转</span>
        </div>
        <div class="tooltip-label-text">{{ edgeTooltipData.label }}</div>
      </div>
    </transition>
    <transition name="play-fade">
      <div v-if="isPlaying" class="play-controls">
        <el-button size="small" @click="prevStep" :disabled="!hasPrevStep">
          <el-icon><ArrowLeft /></el-icon>上一步
        </el-button>
        <span class="play-step-info">{{ getStepInfo() }}</span>
        <span class="play-current-name">
          {{ playPath[currentPlayIndex]?.screenName || '' }}
        </span>
        <el-button
          size="small"
          type="primary"
          @click="nextStep"
          :disabled="!hasNextStep && !playPath[currentPlayIndex]?.isBranchChoice"
        >
          下一步<el-icon><ArrowRight /></el-icon>
        </el-button>
        <el-button size="small" type="danger" @click="stopPlayback">
          <el-icon><Close /></el-icon>退出
        </el-button>
      </div>
    </transition>
    <el-dialog
      v-model="showBranchChoice"
      title="选择分支路径"
      width="360px"
      :close-on-click-modal="false"
    >
      <div class="branch-choices">
        <div
          v-for="branch in playPath[currentPlayIndex]?.branchOptions || []"
          :key="branch.edgeId"
          class="branch-option"
          @click="followBranch(branch.targetNodeId, vueFlowEdges, vueFlowNodes)"
        >
          <el-icon><Connection /></el-icon>
          <span>{{ branch.targetName }}</span>
          <el-icon><ArrowRight /></el-icon>
        </div>
        <div
          class="branch-option continue-main"
          @click="showBranchChoice = false; nextStep()"
        >
          <el-icon><Guide /></el-icon>
          <span>继续主干流程</span>
          <el-icon><ArrowRight /></el-icon>
        </div>
      </div>
    </el-dialog>

    <EdgeConditionDialog
      v-model:visible="conditionDialogVisible"
      :edge-data="currentEdgeForm"
      @confirm="onEdgeConditionConfirm"
    />

    <FlowTypeConfigDialog
      v-model:visible="flowTypeConfigVisible"
      :flow-type="(pendingFlowTypeChange?.type as Exclude<FlowNodeData['flow_type'], 'main'>) || 'branch'"
      :main-node-options="mainNodeOptions"
      :initial-data="pendingFlowMeta"
      @confirm="handleFlowTypeConfigConfirm"
    />

    <EdgeSuggestionDialog
      v-model:visible="showEdgeSuggestion"
      v-model:nodes="vueFlowNodes"
      v-model:edges="vueFlowEdges"
      @confirm="handleEdgeSuggestionsConfirmed"
    />

    <FlowPromptPreviewDialog
      v-model:visible="showPromptPreview"
      :flow-sort-data="promptPreviewFlowData"
    />

    <transition name="tip-fade">
      <div v-if="showShortcutsTip" class="shortcuts-tip">
        <kbd>Delete</kbd> 删除选中 | <kbd>Ctrl+Z</kbd> 撤销 | <kbd>Ctrl+S</kbd> 保存 |
        <kbd>Ctrl+P</kbd> 预览 Prompt | <kbd>Space</kbd> 预览图片 |
        <kbd>Ctrl+L</kbd> 自动布局 | <kbd>Ctrl+0</kbd> 适配视图 |
        <kbd>Esc</kbd> 取消选择
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted, nextTick } from 'vue'
import {
  VueFlow,
  useVueFlow,
  type Connection as FlowConnection,
  type Node,
  type EdgeMouseEvent,
  type EdgeChange,
} from '@vue-flow/core'
import { Background, Controls, MiniMap } from '@vue-flow/additional-components'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Grid,
  View,
  RefreshLeft,
  Delete,
  Edit,
  FullScreen,
  Search,
  Plus,
  ArrowDown,
  VideoPlay,
  VideoPause,
  ArrowLeft,
  ArrowRight,
  MagicStick,
  Guide,
  Connection,
  Close,
  Loading,
  Clock,
  CircleCheck,
  CircleClose,
} from '@element-plus/icons-vue'
import { useFlowSortStore } from '@/store/flowSort'
import { useGenerateStore } from '@/store/useGenerateStore'
import FlowNodeCard from './FlowNodeCard.vue'
import EdgeConditionDialog from './EdgeConditionDialog.vue'
import FlowTypeConfigDialog from './FlowTypeConfigDialog.vue'
import EdgeSuggestionDialog from './EdgeSuggestionDialog.vue'
import FlowPromptPreviewDialog from './FlowPromptPreviewDialog.vue'
import type { FlowNodeData, FlowEdgeData, FlowMetaData } from '@/store/flowSort'
import type { UIScreen } from '@/api/uiPrototype'
import {
  type EditorNodeData,
  type FlowEditorNode,
  type FlowGraphEdge,
  type FlowEdgeInput,
  computeUpstreamNodeIds,
  computeDownstreamNodeIds,
  computeRelatedEdgeIds,
  getNodeData,
  getMainNodesInOrder,
  normalizeMainNodeOrders,
  layoutMainNodesByOrder,
  getMainNodeCount,
  createEdgeMarker,
  normalizeEdges,
  validateFlowData,
  useFlowHistory,
  useFlowSelection,
  OVERVIEW_EDGE_STYLES,
  FLOW_TYPE_TAG_MAP,
  FLOW_TYPE_LABEL_MAP,
  EDGE_STYLES,
  generateAutoEdges,
  AUTO_CONNECT_DISTANCE,
} from '@/composables/useFlowEditor'
import { type LayoutMode, autoLayoutByMode, LAYOUT_MODE_LABELS } from '@/composables/useFlowLayout'
import { usePathPlayback } from '@/composables/usePathPlayback'
import { type EdgeSuggestion } from '@/composables/useEdgeSuggestion'
import { useTestPointLink } from '@/composables/useTestPointLink'

// ---------- 常量定义 ----------
const NODE_SPACING_X = 280
const NODE_SPACING_Y = 280
const VIRTUAL_SCREEN_ID_OFFSET = 1000
const SHORTCUTS_TIP_DURATION = 5000

// ---------- Props & Emits ----------
const props = defineProps<{
  screens: UIScreen[]
  screenImageUrls?: Record<number, string>
  moduleInfo?: { name: string; description: string }
  highlightedScreenIds?: number[]
}>()

const emit = defineEmits<{
  'update:sort-data': [data: { mode: string; nodes: FlowNodeData[]; edges: FlowEdgeData[] }]
  'preview-screen': [screen: { screen_id: number; screen_name: string; image_url?: string }]
}>()

const flowSortStore = useFlowSortStore()
const { fitView, viewport, setCenter } = useVueFlow()

// ---------- 状态定义 ----------
const displayMode = ref<'overview' | 'edit'>('overview')
const vueFlowNodes = ref<FlowEditorNode[]>([])
const vueFlowEdges = ref<any[]>([])
const currentZoom = ref(1)
const showShortcutsTip = ref(true)
const editorRef = ref<HTMLElement | null>(null)

const conditionDialogVisible = ref(false)
const currentConnection = ref<{ source: string; target: string } | null>(null)
const currentEdgeForm = ref<{
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition: string
  trigger_action: string
  pre_action: string
  note: string
} | null>(null)
const editingEdgeId = ref<string | null>(null)

watch(conditionDialogVisible, (val) => {
  if (!val) {
    editingEdgeId.value = null
    currentConnection.value = null
  }
})

const showPromptPreview = ref(false)
const promptPreviewFlowData = computed(
  () => getFlowSortSubmitData().flow_sort_data as unknown as Record<string, unknown>
)

const searchKeyword = ref('')
const searchMatchIds = ref<string[]>([])
const showSearchDropdown = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const searchResults = computed(() => {
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

const debouncedSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    handleSearchLocate()
  }, 300)
}

const clearSearch = () => {
  searchMatchIds.value = []
  showSearchDropdown.value = false
  if (searchTimer) clearTimeout(searchTimer)
}

const handleSearchBlur = () => {
  setTimeout(() => {
    showSearchDropdown.value = false
  }, 200)
}

const locateNode = (nodeId: string) => {
  searchMatchIds.value = [nodeId]
  showSearchDropdown.value = false
  void fitView({ nodes: [nodeId], duration: 300, padding: 0.3 })
}

const locateFirstMatch = () => {
  if (searchResults.value.length > 0) {
    locateNode(searchResults.value[0].id)
  }
}

const handleSearchLocate = () => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) {
    searchMatchIds.value = []
    return
  }
  searchMatchIds.value = searchResults.value.map((r) => r.id)
  showSearchDropdown.value = true
  if (searchResults.value.length > 0) {
    locateNode(searchResults.value[0].id)
  }
}

const { selectedNodes, draggingNodeId, getSelectedMainNodeId, getSelectedMainOrder } =
  useFlowSelection()
const focusedNodeId = ref<string | null>(null)
const collapsedParentNodeIds = ref<string[]>([])

const upstreamNodeIds = computed<Set<string>>(() => {
  if (!focusedNodeId.value) return new Set<string>()
  return computeUpstreamNodeIds(vueFlowEdges.value as any, focusedNodeId.value)
})

const downstreamNodeIds = computed<Set<string>>(() => {
  if (!focusedNodeId.value) return new Set<string>()
  return computeDownstreamNodeIds(vueFlowEdges.value as any, focusedNodeId.value)
})

const allPathNodeIds = computed<Set<string>>(() => {
  if (!focusedNodeId.value) return new Set<string>()
  const all = new Set<string>([focusedNodeId.value])
  upstreamNodeIds.value.forEach((id) => all.add(id))
  downstreamNodeIds.value.forEach((id) => all.add(id))
  return all
})

const pathHighlightedEdgeIds = computed<Set<string>>(() => {
  if (!focusedNodeId.value) return new Set<string>()
  return computeRelatedEdgeIds(vueFlowEdges.value as any, allPathNodeIds.value)
})

const currentEdgeStyles = computed(() =>
  displayMode.value === 'overview' ? OVERVIEW_EDGE_STYLES : EDGE_STYLES
)

const isOverviewMode = computed(() => displayMode.value === 'overview')

function getEdgeStyle(edgeType: string) {
  return currentEdgeStyles.value[edgeType] || currentEdgeStyles.value.normal
}

function applyEdgeStyles(edges: any[]): any[] {
  return normalizeEdges(edges as any, currentEdgeStyles.value, isOverviewMode.value) as any
}

function applyAllEdgeStyles(edges: any[]): any[] {
  const styled = applyEdgeStyles(edges)
  if (!focusedNodeId.value) return styled
  return styled.map((edge: any) => {
    const isHighlighted = pathHighlightedEdgeIds.value.has(edge.id)
    return {
      ...edge,
      class: isHighlighted ? 'edge-path-highlighted' : 'edge-path-dimmed',
      style: {
        ...(edge.style || {}),
        strokeWidth: isHighlighted ? 3 : 1,
      },
    }
  })
}

const defaultEdgeOptions = computed(() => ({
  markerEnd: createEdgeMarker(getEdgeStyle('normal').stroke),
  style: getEdgeStyle('normal'),
}))

const { historyStack, canUndo, saveToHistory, undo } = useFlowHistory()

const branchChildrenMap = computed(() => {
  const map = new Map<string, Array<{ node: FlowEditorNode; edge: any }>>()
  const nodes = vueFlowNodes.value
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  vueFlowEdges.value.forEach((edge: any) => {
    if (
      edge.data?.edge_type &&
      ['branch', 'exception', 'bypass'].includes(edge.data.edge_type) &&
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

const getChildBranchCount = (nodeId: string): number =>
  branchChildrenMap.value.get(nodeId)?.length ?? 0

const canQuickCreateBranch = computed(() => {
  if (selectedNodes.value.length !== 1) return false
  const node = vueFlowNodes.value.find((n) => n.id === selectedNodes.value[0])
  return node !== undefined && getNodeData(node).flow_type === 'main'
})

function applyCollapsedHidden() {
  const hiddenNodeIds = new Set<string>()
  collapsedParentNodeIds.value.forEach((parentId) => {
    const children = branchChildrenMap.value.get(parentId) ?? []
    children.forEach((child) => hiddenNodeIds.add(child.node.id))
  })
  const hasChange =
    vueFlowNodes.value.some((n) => n.hidden !== hiddenNodeIds.has(n.id)) ||
    vueFlowEdges.value.some(
      (e: any) => e.hidden !== (hiddenNodeIds.has(e.source) || hiddenNodeIds.has(e.target))
    )
  if (!hasChange) return
  vueFlowNodes.value = vueFlowNodes.value.map((node) => ({
    ...node,
    hidden: hiddenNodeIds.has(node.id),
  }))
  vueFlowEdges.value = vueFlowEdges.value.map((edge: any) => ({
    ...edge,
    hidden: hiddenNodeIds.has(edge.source) || hiddenNodeIds.has(edge.target),
  }))
}

watch(collapsedParentNodeIds, () => applyCollapsedHidden(), { deep: true })

const flowTypeConfigVisible = ref(false)
const pendingFlowTypeChange = ref<{ nodeId: string; type: string } | null>(null)
const pendingFlowMeta = ref<FlowMetaData | null>(null)

const mainNodeOptions = computed(() =>
  getMainNodesInOrder(vueFlowNodes.value).map((node) => ({
    id: node.id,
    screen_id: getNodeData(node).screen_id,
    screen_name: getNodeData(node).screen_name,
    main_order: getNodeData(node).main_order,
    flow_type: getNodeData(node).flow_type,
    depth: 0,
  }))
)

const handleFlowTypeConfigConfirm = (meta: FlowMetaData) => {
  if (!pendingFlowTypeChange.value) return
  const { nodeId, type } = pendingFlowTypeChange.value
  const parentNodeId = meta.parent_main_node_id

  saveSnapshot()

  vueFlowNodes.value = normalizeMainNodeOrders(
    vueFlowNodes.value.map((node) => {
      if (node.id !== nodeId) return node
      const nodeData = getNodeData(node)
      return {
        ...node,
        data: {
          ...nodeData,
          flow_type: type as EditorNodeData['flow_type'],
          main_order: undefined,
          flow_meta: meta,
        },
      }
    })
  )

  if (parentNodeId) {
    const existingEdgeIndex = vueFlowEdges.value.findIndex(
      (e: any) => e.target === nodeId && e.data?.edge_type === type
    )
    const style = getEdgeStyle(type)
    const newEdge: FlowGraphEdge = {
      id: existingEdgeIndex >= 0 ? vueFlowEdges.value[existingEdgeIndex].id : `edge_${Date.now()}`,
      source: parentNodeId,
      target: nodeId,
      type: 'default',
      animated: true,
      style,
      label: `${type === 'branch' ? '分支' : type === 'exception' ? '异常' : '旁路'}：${meta.trigger_condition || ''}`,
      data: {
        edge_type: type,
        pre_action: meta.pre_action,
        note: meta.note,
      },
    }

    if (existingEdgeIndex >= 0) {
      vueFlowEdges.value = normalizeEdges([
        ...vueFlowEdges.value.slice(0, existingEdgeIndex),
        newEdge,
        ...vueFlowEdges.value.slice(existingEdgeIndex + 1),
      ] as any, currentEdgeStyles.value, isOverviewMode.value) as any
    } else {
      vueFlowEdges.value = normalizeEdges([...vueFlowEdges.value, newEdge] as any, currentEdgeStyles.value, isOverviewMode.value) as any
    }
  }

  flowTypeConfigVisible.value = false
  pendingFlowTypeChange.value = null
  pendingFlowMeta.value = null
  vueFlowNodes.value = autoLayoutByMode(layoutMode.value, vueFlowNodes.value, vueFlowEdges.value as any, focusedNodeId.value)
  emitSortData()
  nextTick(() => {
    void fitView({ duration: 300, padding: 0.15 })
  })
}

const {
  isPlaying,
  playPath,
  currentPlayIndex,
  currentPlayNodeId,
  showBranchChoice,
  hasPrevStep,
  hasNextStep,
  startPlayback,
  stopPlayback,
  nextStep,
  prevStep,
  followBranch,
  getStepInfo,
} = usePathPlayback()

watch(currentPlayNodeId, (nodeId) => {
  if (nodeId) {
    focusedNodeId.value = nodeId
    const node = vueFlowNodes.value.find((n) => n.id === nodeId)
    if (node) {
      setCenter(node.position.x, node.position.y, { zoom: currentZoom.value, duration: 300 })
    }
  }
})

watch(isPlaying, (playing) => {
  if (!playing) {
    focusedNodeId.value = null
    selectedNodes.value = []
  }
})

// 将 store 调用移至顶层，避免 computed 内调用
const genStore = useGenerateStore()
const { getRelatedScreenIds } = useTestPointLink()

const highlightedScreenIds = computed(() => {
  if (props.highlightedScreenIds) {
    return new Set(props.highlightedScreenIds)
  }
  try {
    return getRelatedScreenIds(
      genStore.formData.test_point_ids,
      genStore.testPoints,
      vueFlowNodes.value
    )
  } catch (error) {
    console.warn('Failed to get related screen IDs from test points:', error)
    return new Set<number>()
  }
})

const getScreenImageUrl = (screen: UIScreen) => {
  if (!screen.id) return ''
  return props.screenImageUrls?.[screen.id] || ''
}

const hydrateNodesWithImages = (nodes: any[]): any[] =>
  nodes.map((node: any) => ({
    ...node,
    data: {
      ...getNodeData(node),
      image_url:
        props.screenImageUrls?.[getNodeData(node).screen_id] || getNodeData(node).image_url || '',
    },
  }))

const syncHistoryImages = () => {
  historyStack.value = historyStack.value.map((snapshot) => ({
    nodes: hydrateNodesWithImages(snapshot.nodes),
    edges: normalizeEdges(snapshot.edges as any) as any,
  }))
}

const minimapNodeColor = (node: Node) => {
  const flowType = node.data?.flow_type as string
  const colors: Record<string, string> = {
    main: '#409eff',
    branch: '#67c23a',
    exception: '#f56c6c',
    bypass: '#e6a23c',
  }
  return colors[flowType] || '#409eff'
}

const minimapNodeStroke = () => '#fff'

// ---------- 模块分组背景 ----------
const showGroupBackground = ref(true)
const groupPadding = 20

const NODE_CARD_WIDTH = 220
const NODE_CARD_HEIGHT = 200

interface NodeGroup {
  id: string
  label: string
  color: string
  strokeColor: string
  bounds: { x: number; y: number; width: number; height: number }
}

const nodeGroups = computed<NodeGroup[]>(() => {
  if (!showGroupBackground.value) return []
  const visibleNodes = vueFlowNodes.value.filter((n) => !n.hidden)
  if (visibleNodes.length === 0) return []

  // Group by parent main node (for branch/exception/bypass children)
  const groups = new Map<string, FlowEditorNode[]>()
  const mainNodes = getMainNodesInOrder(vueFlowNodes.value)

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

  const typeColors: Record<string, { color: string; strokeColor: string }> = {
    main: { color: 'rgba(64, 158, 255, 0.08)', strokeColor: 'rgba(64, 158, 255, 0.4)' },
    branch: { color: 'rgba(103, 194, 58, 0.08)', strokeColor: 'rgba(103, 194, 58, 0.4)' },
    exception: { color: 'rgba(245, 108, 108, 0.08)', strokeColor: 'rgba(245, 108, 108, 0.4)' },
    bypass: { color: 'rgba(230, 162, 60, 0.08)', strokeColor: 'rgba(230, 162, 60, 0.4)' },
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
    const colors = typeColors[flowType] || typeColors.main
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

const svgViewBox = computed(() => ({
  x: viewport.value?.x ?? 0,
  y: viewport.value?.y ?? 0,
}))

// 公共序列化函数，去除重复逻辑
function serializeEdge(edge: any): FlowEdgeData | null {
  const sourceNode = vueFlowNodes.value.find((n) => n.id === edge.source)
  const targetNode = vueFlowNodes.value.find((n) => n.id === edge.target)
  const sourceScreenId = sourceNode ? getNodeData(sourceNode).screen_id : undefined
  const targetScreenId = targetNode ? getNodeData(targetNode).screen_id : undefined
  if (!sourceScreenId || !targetScreenId) return null
  return {
    id: edge.id,
    source: String(sourceScreenId),
    target: String(targetScreenId),
    edge_type: (edge.data?.edge_type || 'normal') as FlowEdgeData['edge_type'],
    condition: edge.data?.condition || undefined,
    trigger_action: edge.data?.trigger_action || undefined,
    label: typeof edge.label === 'string' ? edge.label : String(edge.label || ''),
    pre_action: edge.data?.pre_action || undefined,
    note: edge.data?.note || undefined,
  }
}

const emitSortData = () => {
  const flowNodes: FlowNodeData[] = vueFlowNodes.value.map((node) => ({
    id: node.id,
    screen_id: getNodeData(node).screen_id,
    screen_name: getNodeData(node).screen_name,
    summary: getNodeData(node).summary,
    ui_spec_elements: getNodeData(node).ui_spec_elements,
    flow_type: getNodeData(node).flow_type,
    main_order: getNodeData(node).main_order,
    image_url: getNodeData(node).image_url,
    position: node.position,
    flow_meta: getNodeData(node).flow_meta,
  }))
  const flowEdges: FlowEdgeData[] = vueFlowEdges.value
    .map(serializeEdge)
    .filter((e): e is FlowEdgeData => e !== null)
  emit('update:sort-data', { mode: 'graph', nodes: flowNodes, edges: flowEdges })
}

const getFlowSortSubmitData = () => {
  const sortedNodes = [...vueFlowNodes.value]
  return {
    flow_sort_data: {
      nodes: sortedNodes.map((node, index) => ({
        screen_id: getNodeData(node).screen_id,
        screen_order: index + 1,
        flow_type: getNodeData(node).flow_type,
        main_order: getNodeData(node).main_order,
        screen_name: getNodeData(node).screen_name,
        ui_spec_elements: getNodeData(node).ui_spec_elements || [],
        summary: getNodeData(node).summary || '',
        flow_meta: getNodeData(node).flow_meta || undefined,
      })),
      edges: vueFlowEdges.value
        .map(serializeEdge)
        .filter((e): e is FlowEdgeData => e !== null),
      module_info: props.moduleInfo || { name: '', description: '' },
    },
  }
}

const getFlowValidationIssues = (): { errors: string[]; warnings: string[] } => {
  const flowData = getFlowSortSubmitData().flow_sort_data
  const edges: FlowEdgeInput[] = flowData.edges.map((edge): FlowEdgeInput => ({
    source: edge.source,
    target: edge.target,
    edge_type: edge.edge_type as FlowEdgeInput['edge_type'],
    condition: edge.condition || '',
    label: edge.label,
  }))
  return validateFlowData(flowData.nodes, edges)
}

defineExpose({ getFlowSortSubmitData, getFlowValidationIssues })

// 深度比较 screens 数组，避免不必要的重建
function isScreensEqual(a: UIScreen[], b: UIScreen[]): boolean {
  if (a.length !== b.length) return false
  return a.every((screen, index) => {
    const other = b[index]
    return (
      screen.id === other.id &&
      screen.screen_name === other.screen_name &&
      screen.summary === other.summary &&
      screen.element_count === other.element_count
    )
  })
}

let lastScreens: UIScreen[] = [] // 暂存上一次的 screens 快照，用于初始化后比较

watch(
  () => props.screens,
  (newScreens) => {
    if (isScreensEqual(newScreens, lastScreens)) return
    lastScreens = newScreens
    const newNodes = normalizeMainNodeOrders(
      newScreens.map((screen, index) => ({
        id: `node_${screen.id}`,
        type: 'custom',
        position: { x: index * NODE_SPACING_X, y: 0 },
        data: {
          screen_id: screen.id,
          screen_name: screen.screen_name,
          summary: screen.summary,
          ui_spec_elements: (screen.ui_spec?.elements || []).map((el) => ({
            type: el.type,
            label: el.label,
            semantic: el.semantic_hint || el.description,
            position: typeof el.position === 'string' ? el.position : JSON.stringify(el.position),
            interactive: el.interactive,
          })),
          flow_type: 'main' as const,
          main_order: index + 1,
          image_url: getScreenImageUrl(screen),
          element_count: screen.element_count,
        },
      }))
    )
    vueFlowNodes.value = newNodes
    const autoEdges = generateAutoEdges(newNodes)
    vueFlowEdges.value = applyAllEdgeStyles(autoEdges)
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
  viewport,
  (nextViewport) => {
    currentZoom.value = nextViewport?.zoom ?? 1
  },
  { deep: true, immediate: true }
)

const onConnect = (connection: FlowConnection) => {
  currentConnection.value = { source: connection.source, target: connection.target }
  currentEdgeForm.value = null
  editingEdgeId.value = null
  conditionDialogVisible.value = true
}

const handleEditEdge = (edge: any) => {
  edgeTooltipVisible.value = false
  edgeTooltipData.value = null
  editingEdgeId.value = edge.id
  currentConnection.value = null
  currentEdgeForm.value = {
    edge_type: (edge.data?.edge_type as 'normal' | 'branch' | 'exception' | 'bypass') || 'normal',
    condition: (edge.data?.condition as string) || '',
    trigger_action: (edge.data?.trigger_action as string) || '',
    pre_action: (edge.data?.pre_action as string) || '',
    note: (edge.data?.note as string) || '',
  }
  conditionDialogVisible.value = true
}

const handleDeleteEdge = (edge: any) => {
  edgeTooltipVisible.value = false
  edgeTooltipData.value = null
  saveSnapshot()
  vueFlowEdges.value = vueFlowEdges.value.filter((e: any) => e.id !== edge.id)
  emitSortData()
  ElMessage.success('已删除连线')
}

const onEdgeConditionConfirm = (edgeData: {
  edge_type: string
  condition: string | null
  trigger_action: string
  pre_action: string
  note: string
  label: string
}) => {
  saveSnapshot()

  if (editingEdgeId.value) {
    vueFlowEdges.value = applyAllEdgeStyles(
      vueFlowEdges.value.map((e: any) => {
        if (e.id !== editingEdgeId.value) return e
        return {
          ...e,
          label: edgeData.label,
          data: {
            edge_type: edgeData.edge_type,
            condition: edgeData.condition,
            trigger_action: edgeData.trigger_action,
            pre_action: edgeData.pre_action,
            note: edgeData.note,
          },
        }
      })
    )
    editingEdgeId.value = null
    ElMessage.success('连线属性已更新')
  } else if (currentConnection.value) {
    // 连接验证
    if (currentConnection.value.source === currentConnection.value.target) {
      ElMessage.warning('不能连接到自身')
      conditionDialogVisible.value = false
      currentConnection.value = null
      return
    }
    const alreadyExists = vueFlowEdges.value.some(
      (e: any) => e.source === currentConnection.value!.source && e.target === currentConnection.value!.target
    )
    if (alreadyExists) {
      ElMessage.warning('已存在相同连线')
      conditionDialogVisible.value = false
      currentConnection.value = null
      return
    }
    const style = getEdgeStyle(edgeData.edge_type)
    const newEdge: FlowGraphEdge = {
      id: `edge_${Date.now()}`,
      source: currentConnection.value.source,
      target: currentConnection.value.target,
      type: 'default',
      animated: true,
      style,
      label: edgeData.label,
      data: {
        edge_type: edgeData.edge_type,
        pre_action: edgeData.pre_action,
        note: edgeData.note,
      },
    }

    vueFlowEdges.value = normalizeEdges([...vueFlowEdges.value, newEdge] as any, currentEdgeStyles.value, isOverviewMode.value) as any
  }

  conditionDialogVisible.value = false
  emitSortData()
}
const onNodeDragStart = (event: { node?: Node }) => {
  draggingNodeId.value = event.node?.id || null
}

const onNodeDragStop = () => {
  draggingNodeId.value = null
  // 拖拽结束后检测邻近节点自动连线
  tryAutoConnectOnDrag()
  saveSnapshot()
  emitSortData()
}

/** 拖拽结束后，对被拖拽节点检测邻近节点，若距离在阈值内且不存在已有连线，则自动建立连线 */
const tryAutoConnectOnDrag = () => {
  const draggedId = selectedNodes.value.length === 1 ? selectedNodes.value[0] : null
  if (!draggedId) return

  const draggedNode = vueFlowNodes.value.find((n) => n.id === draggedId)
  if (!draggedNode) return

  const existingEdges = new Set(
    vueFlowEdges.value
      .filter((e: any) => !e.hidden)
      .map((e: any) => `${e.source}->${e.target}`)
  )

  const newEdges: any[] = []
  vueFlowNodes.value.forEach((other) => {
    if (other.id === draggedId || other.hidden) return
    const dx = draggedNode.position.x - other.position.x
    const dy = draggedNode.position.y - other.position.y
    const distance = Math.sqrt(dx * dx + dy * dy)
    if (distance >= AUTO_CONNECT_DISTANCE) return

    // 方向：从左/上 → 右/下
    const source =
      other.position.x < draggedNode.position.x ||
      (other.position.x === draggedNode.position.x && other.position.y < draggedNode.position.y)
        ? other
        : draggedNode
    const target = source === other ? draggedNode : other
    const key = `${source.id}->${target.id}`
    const reverseKey = `${target.id}->${source.id}`

    // 仅在两个方向都没有连线时才自动创建
    if (existingEdges.has(key) || existingEdges.has(reverseKey)) return

    const sourceType = getNodeData(source).flow_type
    const targetType = getNodeData(target).flow_type
    let edgeType: 'normal' | 'branch' | 'exception' | 'bypass' = 'normal'
    if (sourceType === 'main' && targetType === 'main') edgeType = 'normal'
    else if (targetType === 'branch') edgeType = 'branch'
    else if (targetType === 'exception') edgeType = 'exception'
    else if (targetType === 'bypass') edgeType = 'bypass'
    else if (sourceType !== 'main' && targetType === 'main') edgeType = 'normal'
    else edgeType = 'branch'

    const absDx = Math.abs(dx)
    const absDy = Math.abs(dy)
    const isVertical = absDy > absDx
    const sourceHandle = isVertical ? 'source-bottom' : 'source-right'
    const targetHandle = isVertical ? 'target-top' : 'target-left'

    newEdges.push({
      id: `edge_${source.id}_${target.id}_${Date.now()}`,
      source: source.id,
      target: target.id,
      sourceHandle,
      targetHandle,
      type: 'default',
      data: { edge_type: edgeType },
    })
  })

  if (newEdges.length > 0) {
    vueFlowEdges.value = applyAllEdgeStyles([...vueFlowEdges.value, ...newEdges])
    ElMessage.success(`已自动连接 ${newEdges.length} 条邻近连线`)
  }
}

const onEdgesChange = (changes: EdgeChange[]) => {
  const removedIds = new Set(
    changes.filter((c) => c.type === 'remove').map((c) => c.id)
  )
  if (removedIds.size > 0) {
    saveSnapshot()
    // v-model:edges 已自动处理删除，只需副作用
    nextTick(() => emitSortData())
  }
}

const handleFlowTypeChange = (nodeId: string, type: string) => {
  if (type === 'main') {
    saveSnapshot()
    const nextMainOrder = getMainNodesInOrder(vueFlowNodes.value).length + 1
    vueFlowNodes.value = normalizeMainNodeOrders(
      vueFlowNodes.value.map((node) => {
        if (node.id !== nodeId) return node
        const nodeData = getNodeData(node)
        return {
          ...node,
          data: {
            ...nodeData,
            flow_type: type as EditorNodeData['flow_type'],
            main_order: nodeData.main_order ?? nextMainOrder,
            flow_meta: undefined,
          },
        }
      })
    )
    emitSortData()
    return
  }

  const node = vueFlowNodes.value.find((n) => n.id === nodeId)
  if (!node) return

  pendingFlowTypeChange.value = { nodeId, type }
  pendingFlowMeta.value = getNodeData(node).flow_meta || null
  flowTypeConfigVisible.value = true
}

// 按钮计数器改为组件内 ref
const branchCounter = ref(1)

const handleQuickCreateBranch = async () => {
  const mainNodeId = getSelectedMainNodeId(vueFlowNodes.value)
  if (!mainNodeId) return

  try {
    const { value: branchName } = await ElMessageBox.prompt('请输入分支页面名称', '快速创建分支', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputValue: `新分支页面${branchCounter.value}`,
      inputValidator: (val: string) => {
        if (!val || !val.trim()) return '页面名称不能为空'
        return true
      },
    })

    saveSnapshot()

    const mainNode = vueFlowNodes.value.find((n) => n.id === mainNodeId)!
    const branchId = `node_branch_${Date.now()}`
    const branchScreenId = -(VIRTUAL_SCREEN_ID_OFFSET + branchCounter.value)

    const branchNode: FlowEditorNode = {
      id: branchId,
      type: 'custom',
      position: {
        x: mainNode.position.x,
        y: mainNode.position.y + NODE_SPACING_Y,
      },
      data: {
        screen_id: branchScreenId,
        screen_name: branchName.trim(),
        summary: '',
        ui_spec_elements: [],
        flow_type: 'branch',
        image_url: '',
      },
    }

    const style = getEdgeStyle('branch')
    const branchEdge: FlowGraphEdge = {
      id: `edge_${mainNodeId}_${branchId}`,
      source: mainNodeId,
      target: branchId,
      type: 'default',
      data: {
        edge_type: 'branch',
        condition: '',
        pre_action: '',
        note: '',
      },
      label: branchName.trim(),
      style,
      markerEnd: createEdgeMarker(style.stroke),
    }

    vueFlowNodes.value = [...vueFlowNodes.value, branchNode]
    vueFlowEdges.value = [...vueFlowEdges.value, branchEdge]

    selectedNodes.value = [branchId]
    branchCounter.value++
    emitSortData()
    ElMessage.success(`已创建分支节点：${branchName.trim()}`)
  } catch {
    // 用户取消
  }
}

const handleBatchFlowTypeChange = (type: string) => {
  if (selectedNodes.value.length < 2) return
  saveSnapshot()

  vueFlowNodes.value = normalizeMainNodeOrders(
    vueFlowNodes.value.map((node) => {
      if (!selectedNodes.value.includes(node.id)) return node
      const nodeData = getNodeData(node)
      if (nodeData.flow_type === type) return node
      return {
        ...node,
        data: {
          ...nodeData,
          flow_type: type as EditorNodeData['flow_type'],
          main_order: type === 'main' ? (nodeData.main_order ?? 0) : undefined,
          flow_meta: undefined,
        },
      }
    })
  )

  vueFlowEdges.value = vueFlowEdges.value.map((edge: any) => {
    const targetNode = vueFlowNodes.value.find((n) => n.id === edge.target)
    if (!targetNode) return edge
    const targetType = getNodeData(targetNode).flow_type
    return {
      ...edge,
      data: { ...edge.data, edge_type: targetType === 'main' ? 'normal' : targetType },
    }
  })

  emitSortData()
  ElMessage.success(
    `已将 ${selectedNodes.value.length} 个节点设为${FLOW_TYPE_LABEL_MAP[type] || type}`
  )
}

const handleDeleteSelected = () => {
  if (selectedNodes.value.length === 0) return
  const deletedCount = selectedNodes.value.length
  saveSnapshot()
  vueFlowEdges.value = vueFlowEdges.value.filter(
    (e: any) => !selectedNodes.value.includes(e.source) && !selectedNodes.value.includes(e.target)
  )
  vueFlowNodes.value = normalizeMainNodeOrders(
    vueFlowNodes.value.filter((n) => !selectedNodes.value.includes(n.id))
  )
  selectedNodes.value = []
  emitSortData()
  ElMessage.success(`已删除 ${deletedCount} 个节点`)
}

const canMoveMainBackward = () => (getSelectedMainOrder(vueFlowNodes.value) ?? 0) > 1

const canMoveMainForward = () => {
  const selectedMainOrder = getSelectedMainOrder(vueFlowNodes.value)
  if (selectedMainOrder == null) return false
  return selectedMainOrder < getMainNodeCount(vueFlowNodes.value)
}

const moveSelectedMainNode = (direction: -1 | 1) => {
  const selectedNodeId = getSelectedMainNodeId(vueFlowNodes.value)
  if (!selectedNodeId) return
  const selectedNode = vueFlowNodes.value.find((n) => n.id === selectedNodeId)
  if (!selectedNode) return

  const orderedMainNodes = getMainNodesInOrder(vueFlowNodes.value)
  const currentIndex = orderedMainNodes.findIndex((node) => node.id === selectedNode.id)
  const targetIndex = currentIndex + direction
  if (currentIndex < 0 || targetIndex < 0 || targetIndex >= orderedMainNodes.length) return

  saveSnapshot()
  const reorderedMainNodes = [...orderedMainNodes]
  ;[reorderedMainNodes[currentIndex], reorderedMainNodes[targetIndex]] = [
    reorderedMainNodes[targetIndex],
    reorderedMainNodes[currentIndex],
  ]
  const mainOrderMap = new Map(reorderedMainNodes.map((node, index) => [node.id, index + 1]))
  vueFlowNodes.value = layoutMainNodesByOrder(
    normalizeMainNodeOrders(
      vueFlowNodes.value.map((node) => {
        if (!mainOrderMap.has(node.id)) return node
        return {
          ...node,
          data: {
            ...getNodeData(node),
            main_order: mainOrderMap.get(node.id),
          },
        }
      })
    )
  )
  emitSortData()
}

const handlePaneClick = () => {
  selectedNodes.value = []
}

const handleNodeClick = (event: { node: Node }) => {
  selectedNodes.value = [event.node.id]
  if (focusedNodeId.value && selectedNodes.value.includes(focusedNodeId.value)) {
    focusedNodeId.value = null
  }
  collapsedParentNodeIds.value = collapsedParentNodeIds.value.filter(
    (id) => !selectedNodes.value.includes(id)
  )
}

const handleSelectionChange = (selected: { nodes: Node[] }) => {
  selectedNodes.value = selected.nodes.map((n) => n.id)
}

const edgeTooltipVisible = ref(false)
const edgeTooltipData = ref<any>(null)
const edgeTooltipPosition = ref({ x: 0, y: 0 })
let edgeTooltipRafId: number | null = null

const onEdgeMouseEnter = (event: EdgeMouseEvent) => {
  const mouseEvent = event.event as MouseEvent
  edgeTooltipData.value = event.edge
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

let edgeTooltipHideTimer: ReturnType<typeof setTimeout> | null = null
let edgeTooltipHovered = false

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

const handleFitView = () => {
  void fitView({ duration: 220, padding: 0.15 })
}

const layoutMode = ref<LayoutMode>('standard')

const handleLayoutModeChange = (mode: string | number | boolean) => {
  layoutMode.value = mode as LayoutMode
  handleAutoLayout()
}

const handleAutoLayout = () => {
  saveSnapshot()
  vueFlowNodes.value = autoLayoutByMode(
    layoutMode.value,
    vueFlowNodes.value,
    vueFlowEdges.value as any,
    focusedNodeId.value
  )
  emitSortData()
  ElMessage.success(`${LAYOUT_MODE_LABELS[layoutMode.value]}完成`)
}

const handleUndo = () => {
  const prev = undo()
  if (!prev) return
  vueFlowNodes.value = prev.nodes
  vueFlowEdges.value = applyAllEdgeStyles(prev.edges as any)
  emitSortData()
  ElMessage.success('已撤销')
}

// 统一快捷键处理，增加 metaKey 支持和 preventDefault 一致性
const isModifierPressed = (e: KeyboardEvent) => e.ctrlKey || e.metaKey

const handleKeyDown = (e: KeyboardEvent) => {
  const target = e.target as HTMLElement
  const isInputFocused = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA'
  if (isInputFocused) return

  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedNodes.value.length > 0) {
      e.preventDefault()
      handleDeleteSelected()
    }
  }
  if (isModifierPressed(e) && e.key === 'z') {
    e.preventDefault()
    handleUndo()
  }
  if (isModifierPressed(e) && e.key === 'l') {
    e.preventDefault()
    handleAutoLayout()
  }
  if (isModifierPressed(e) && e.key === 'p') {
    e.preventDefault()
    handlePreviewPrompt()
  }
  if (e.key === 'Escape') {
    selectedNodes.value = []
  }
  if (isModifierPressed(e) && e.key === 's') {
    e.preventDefault()
    flowSortStore.manualSave()
  }
  if (isModifierPressed(e) && e.key === '0') {
    e.preventDefault()
    handleFitView()
  }
  if (e.code === 'Space') {
    e.preventDefault()
    if (selectedNodes.value.length === 1) {
      const node = vueFlowNodes.value.find((item) => item.id === selectedNodes.value[0])
      if (node) handleNodePreview(getNodeData(node))
    }
  }
}

const handleToggleCollapse = (nodeId: string) => {
  const idx = collapsedParentNodeIds.value.indexOf(nodeId)
  if (idx >= 0) {
    collapsedParentNodeIds.value.splice(idx, 1)
  } else {
    collapsedParentNodeIds.value.push(nodeId)
  }
}

const showEdgeSuggestion = ref(false)
const handleEdgeSuggestionsConfirmed = (accepted: EdgeSuggestion[]) => {
  if (accepted.length === 0) return
  saveSnapshot()
  const style = getEdgeStyle('branch')
  const newEdges: FlowGraphEdge[] = accepted.map((s) => ({
    id: `edge_${s.sourceNodeId}_${s.targetNodeId}_${Date.now()}`,
    source: s.sourceNodeId,
    target: s.targetNodeId,
    type: 'default',
    animated: true,
    style,
    data: { edge_type: 'branch', condition: '' },
    markerEnd: createEdgeMarker(style.stroke),
  }))
  vueFlowEdges.value = applyAllEdgeStyles([...vueFlowEdges.value, ...newEdges])
  emitSortData()
  ElMessage.success(`已应用 ${accepted.length} 条建议连线`)
}

const handlePreviewPrompt = () => {
  showPromptPreview.value = true
}

const handleNodePreview = (data: EditorNodeData) => {
  if (data?.screen_id) {
    emit('preview-screen', {
      screen_id: data.screen_id,
      screen_name: data.screen_name,
      image_url: data.image_url,
    })
  }
}

// 统一历史保存方法
function saveSnapshot() {
  saveToHistory(vueFlowNodes.value, vueFlowEdges.value as any)
}

onMounted(() => {
  if (editorRef.value) editorRef.value.focus()
  setTimeout(() => {
    showShortcutsTip.value = false
  }, SHORTCUTS_TIP_DURATION)
})

onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
  if (edgeTooltipRafId !== null) {
    cancelAnimationFrame(edgeTooltipRafId)
    edgeTooltipRafId = null
  }
  if (edgeTooltipHideTimer) {
    clearTimeout(edgeTooltipHideTimer)
    edgeTooltipHideTimer = null
  }
})

</script>

<style scoped lang="scss">
.flow-sort-editor {
  width: 100%;
  flex: 1;
  min-height: 0;
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  outline: none;

  &:focus {
    outline: 2px solid rgba(64, 158, 255, 0.3);
    outline-offset: 2px;
  }

  .editor-toolbar {
    flex-shrink: 0;
    padding: 14px 16px;
    background: linear-gradient(135deg, #ffffff 0%, #fafbfc 100%);
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: nowrap;
    overflow: hidden;

    .toolbar-left {
      display: flex;
      align-items: center;
      min-width: 0;
      gap: 16px;

      .editor-heading {
        display: flex;
        flex-direction: column;
        gap: 4px;

        .editor-title {
          font-size: 14px;
          font-weight: 600;
          color: #303133;
        }

        .editor-subtitle {
          font-size: 12px;
          color: #909399;
        }
      }

      .flow-legend {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;

        .legend-item {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          height: 24px;
          padding: 0 9px;
          border-radius: 999px;
          font-size: 12px;
          font-weight: 500;
          border: 1px solid transparent;

          &::before {
            content: '';
            width: 7px;
            height: 7px;
            border-radius: 999px;
          }
        }

        .legend-main {
          color: #2563eb;
          background: #eff6ff;
          border-color: #bfdbfe;

          &::before {
            background: #409eff;
          }
        }

        .legend-branch {
          color: #3f8f1f;
          background: #f0f9eb;
          border-color: #c2e7b0;

          &::before {
            background: #67c23a;
          }
        }

        .legend-exception {
          color: #c45656;
          background: #fef0f0;
          border-color: #fbc4c4;

          &::before {
            background: #f56c6c;
          }
        }

        .legend-bypass {
          color: #b88230;
          background: #fdf6ec;
          border-color: #f5dab1;

          &::before {
            background: #e6a23c;
          }
        }
      }
    }

    .toolbar-actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: nowrap;
      justify-content: flex-end;
      margin-left: auto;
      overflow-x: auto;

      .action-group {
        :deep(.el-button) {
          border-radius: 8px;
          transition: all 0.2s ease;

          &:hover {
            transform: translateY(-1px);
          }
        }
      }

      .selection-info {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .main-order-actions {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .zoom-controls {
        display: flex;
        align-items: center;

        .search-input {
          width: 160px;

          :deep(.el-input__wrapper) {
            border-radius: 8px;
          }
        }

        .search-wrapper {
          position: relative;

          .search-dropdown {
            position: absolute;
            top: 100%;
            right: 0;
            z-index: 100;
            min-width: 220px;
            max-height: 240px;
            overflow-y: auto;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
            border: 1px solid rgba(0, 0, 0, 0.06);
            margin-top: 4px;

            .search-result-item {
              display: flex;
              align-items: center;
              justify-content: space-between;
              padding: 8px 12px;
              cursor: pointer;
              transition: background 0.15s;
              color: #606266;

              &:hover {
                background: #f5f7fa;
              }

              .result-name {
                font-size: 13px;
                color: #303133;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                flex: 1;
                margin-right: 8px;
              }

              .result-tag {
                flex-shrink: 0;
              }
            }

            .search-empty {
              padding: 12px;
              text-align: center;
              font-size: 13px;
              color: #909399;
            }
          }
        }
      }

      .mode-toggle {
        :deep(.el-button) {
          border-radius: 8px;
          font-size: 13px;
          font-weight: 500;
        }
      }

      .save-status-area {
        flex-shrink: 0;
        white-space: nowrap;

        .save-error-wrapper {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          cursor: pointer;
        }

        .save-error-icon,
        .save-error-text {
          cursor: pointer;
        }
      }
    }
  }

  .editor-container {
    flex: 1;
    position: relative;
    overflow: hidden;
    min-height: 0;
  }

  .graph-mode {
    position: absolute;
    inset: 0;
    overflow: hidden;
  }

  .shortcuts-tip {
    position: absolute;
    bottom: 16px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.75);
    color: #fff;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 12px;
    pointer-events: none;
    backdrop-filter: blur(4px);

    kbd {
      background: rgba(255, 255, 255, 0.15);
      padding: 2px 6px;
      border-radius: 4px;
      margin: 0 2px;
    }
  }
}

.graph-mode :deep(.vue-flow__controls) {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  overflow: hidden;
}

.graph-mode :deep(.vue-flow__minimap) {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
}

.graph-mode :deep(.vue-flow__edge) {
  z-index: 1;
}

.graph-mode :deep(.vue-flow__edge-path) {
  stroke-width: 2;
}

.graph-mode :deep(.vue-flow__edge-marker) {
  stroke-width: 2;
}

.group-bg-panel {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;

  .group-bg-svg {
    position: absolute;
    top: 0;
    left: 0;
    pointer-events: none;
  }
}

.tip-fade-enter-active,
.tip-fade-leave-active {
  transition: opacity 0.5s ease;
}
.tip-fade-enter-from,
.tip-fade-leave-to {
  opacity: 0;
}

@media (max-width: 960px) {
  .flow-sort-editor {
    .editor-toolbar {
      align-items: flex-start;
      padding: 12px;

      .toolbar-actions {
        width: 100%;
        margin-left: 0;
        justify-content: flex-start;
      }
    }
  }
}

@media (max-width: 640px) {
  .flow-sort-editor {
    .editor-toolbar {
      .toolbar-left,
      .toolbar-actions,
      .selection-info,
      .zoom-controls {
        width: 100%;
      }
    }
  }
}

.edge-tooltip {
  position: fixed;
  z-index: 9999;
  max-width: 280px;
  padding: 10px 14px;
  background: rgba(30, 33, 40, 0.92);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
  pointer-events: auto;
  font-size: 12px;
  color: #e8eaed;
  line-height: 1.5;

  .tooltip-header {
    margin-bottom: 6px;
  }

  .tooltip-edit-btn,
  .tooltip-delete-btn {
    width: 22px;
    height: 22px;
    padding: 0;
    flex-shrink: 0;
    margin-left: 8px;
  }

  .tooltip-row {
    display: flex;
    gap: 4px;
    margin-bottom: 3px;

    .tooltip-label {
      color: #9aa0a6;
      flex-shrink: 0;
    }

    .tooltip-value {
      color: #e8eaed;
      word-break: break-word;
    }
  }

  .tooltip-label-text {
    margin-top: 4px;
    padding-top: 4px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    font-size: 11px;
    color: #9aa0a6;
    word-break: break-word;
  }
}

.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
  transition: opacity 0.15s ease;
}

.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
  opacity: 0;
}

.graph-mode :deep(.edge-path-highlighted .vue-flow__edge-path) {
  stroke-width: 3 !important;
  filter: drop-shadow(0 0 6px rgba(64, 158, 255, 0.5));
}

.graph-mode :deep(.edge-path-dimmed .vue-flow__edge-path) {
  opacity: 0.18;
  stroke-width: 1 !important;
}

.graph-mode :deep(.edge-path-highlighted .vue-flow__edge-label) {
  font-weight: 600;
  font-size: 11px;
}

.play-controls {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  background: rgba(30, 33, 40, 0.92);
  backdrop-filter: blur(12px);
  border-radius: 12px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);

  .play-step-info {
    color: #9aa0a6;
    font-size: 13px;
    white-space: nowrap;
  }

  .play-current-name {
    color: #e8eaed;
    font-size: 13px;
    font-weight: 500;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.play-fade-enter-active,
.play-fade-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.play-fade-enter-from,
.play-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

.branch-choices {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.branch-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 8px;
  background: #f5f7fa;
  cursor: pointer;
  transition:
    background 0.2s,
    transform 0.15s;

  &:hover {
    background: #ecf5ff;
    transform: translateX(4px);
  }

  &.continue-main {
    border: 1px dashed #c0c4cc;
    background: transparent;

    &:hover {
      border-color: #409eff;
      background: rgba(64, 158, 255, 0.04);
    }
  }

  span {
    flex: 1;
    font-size: 14px;
    color: #303133;
  }

  .el-icon {
    color: #909399;
  }
}
</style>