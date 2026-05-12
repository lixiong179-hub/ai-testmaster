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
        <div class="save-controls">
          <template v-if="flowSortStore.saveStatus === 'unsaved'">
            <el-tooltip v-if="!flowSortStore.projectId" content="请先选择项目" placement="top">
              <el-button type="primary" size="small" disabled>
                <el-icon><Upload /></el-icon> 保存
              </el-button>
            </el-tooltip>
            <el-button v-else type="primary" size="small" @click="flowSortStore.manualSave()">
              <el-icon><Upload /></el-icon> 保存
            </el-button>
          </template>
          <template v-else-if="flowSortStore.saveStatus === 'saving'">
            <span class="save-status-inner">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span class="save-text">保存中...</span>
            </span>
          </template>
          <template v-else-if="flowSortStore.saveStatus === 'saved'">
            <span class="save-status-inner saved">
              <el-icon><CircleCheck /></el-icon>
              <span class="save-text">已保存</span>
            </span>
          </template>
          <template v-else-if="flowSortStore.saveStatus === 'error'">
            <span class="save-status-inner error" @click="flowSortStore.manualRetrySave()">
              <el-icon><CircleClose /></el-icon>
              <span class="save-text">保存失败</span>
              <el-button size="small" type="danger" text class="retry-btn">重试</el-button>
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
            :type="FLOW_TYPE_TAG_MAP[edgeTooltipData.data?.edge_type as string] || 'primary'"
            effect="dark"
          >
            {{ FLOW_TYPE_LABEL_MAP[edgeTooltipData.data?.edge_type as string] || '跳转' }}
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
import { ref, watch, computed, onMounted, nextTick, type Ref } from 'vue'
import {
  VueFlow,
  useVueFlow,
  type Node,
} from '@vue-flow/core'
import { Background, Controls, MiniMap } from '@vue-flow/additional-components'
import { ElMessage } from 'element-plus'
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
  CircleCheck,
  CircleClose,
  Upload,
} from '@element-plus/icons-vue'
import { useFlowSortStore } from '@/store/flowSort'
import { useGenerateStore } from '@/store/useGenerateStore'
import FlowNodeCard from './FlowNodeCard.vue'
import EdgeConditionDialog from './EdgeConditionDialog.vue'
import FlowTypeConfigDialog from './FlowTypeConfigDialog.vue'
import EdgeSuggestionDialog from './EdgeSuggestionDialog.vue'
import FlowPromptPreviewDialog from './FlowPromptPreviewDialog.vue'
import type { FlowNodeData, FlowEdgeData } from '@/store/flowSort'
import type { UIScreen } from '@/api/uiPrototype'
import {
  type EditorNodeData,
  type FlowEditorNode,
  type FlowGraphEdge,
  getNodeData,
  getMainNodesInOrder,
  normalizeMainNodeOrders,
  normalizeEdges,
  useFlowHistory,
  FLOW_TYPE_TAG_MAP,
  FLOW_TYPE_LABEL_MAP,
  generateAutoEdges,
  AUTO_CONNECT_DISTANCE,
} from '@/composables/useFlowEditor'
import useFlowSortData, { type EmitSortDataPayload } from '@/composables/useFlowSortData'
import { type LayoutMode, autoLayoutByMode, LAYOUT_MODE_LABELS } from '@/composables/useFlowLayout'
import { usePathPlayback } from '@/composables/usePathPlayback'
import { useTestPointLink } from '@/composables/useTestPointLink'
import { useFlowSearch } from '@/composables/useFlowSearch'
import { useFlowPathHighlight } from '@/composables/useFlowPathHighlight'
import { useFlowEdgeOps } from '@/composables/useFlowEdgeOps'
import { useFlowTypeOps } from '@/composables/useFlowTypeOps'
import { useFlowMainOrder } from '@/composables/useFlowMainOrder'
import { useFlowEdgeTooltip } from '@/composables/useFlowEdgeTooltip'
import { useFlowGroupBackground, groupPadding } from '@/composables/useFlowGroupBackground'

// ---------- 常量定义 ----------
const NODE_SPACING_X = 280
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

// ---------- 基础状态 ----------
const displayMode = ref<'overview' | 'edit'>('overview')
const vueFlowNodes = ref<FlowEditorNode[]>([])
const vueFlowEdges = ref<any[]>([])
const currentZoom = ref(1)
const showShortcutsTip = ref(true)
const editorRef = ref<HTMLElement | null>(null)
const collapsedParentNodeIds = ref<string[]>([])
const draggingNodeId = ref<string | null>(null)
const isRestoredFromBackend = ref(false)

// ---------- 数据序列化与提交 composable ----------
const {
  emitSortData,
  getFlowSortSubmitData,
  getFlowValidationIssues,
} = useFlowSortData({
  vueFlowNodes,
  vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
  emit: (event: 'update:sort-data', data: EmitSortDataPayload) => emit(event, data),
  flowSortStore,
  getNodeData,
  moduleInfo: computed(() => props.moduleInfo),
})

// ---------- 计算辅助 ----------
const isOverviewMode = computed(() => displayMode.value === 'overview')

// ---------- 历史管理 ----------
const { historyStack, canUndo, saveToHistory, undo } = useFlowHistory()

function saveSnapshot() {
  saveToHistory(vueFlowNodes.value, vueFlowEdges.value as any)
}

// ---------- 搜索定位 composable ----------
const {
  searchKeyword,
  searchResults,
  searchMatchIds,
  showSearchDropdown,
  debouncedSearch,
  clearSearch,
  locateNode,
  locateFirstMatch,
  handleSearchBlur,
} = useFlowSearch({
  vueFlowNodes,
  getNodeData,
  fitView: (options?: Record<string, unknown>) => { void fitView(options) },
})

// ---------- 节点选择与路径高亮 composable ----------
const {
  selectedNodes,
  focusedNodeId,
  upstreamNodeIds,
  downstreamNodeIds,
  allPathNodeIds,
  currentEdgeStyles,
  applyAllEdgeStyles,
  getEdgeStyle,
  defaultEdgeOptions,
  handleNodeClick,
  handlePaneClick,
} = useFlowPathHighlight({
  vueFlowNodes,
  vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
  getNodeData,
  isOverviewMode,
  collapsedParentNodeIds,
})

// ---------- Edge Tooltip composable ----------
const {
  edgeTooltipVisible,
  edgeTooltipData,
  edgeTooltipPosition,
  onEdgeMouseEnter,
  onEdgeMouseMove,
  onEdgeMouseLeave,
  onEdgeTooltipEnter,
  onEdgeTooltipLeave,
} = useFlowEdgeTooltip({})

// ---------- 模块分组背景 composable ----------
const {
  showGroupBackground,
  nodeGroups,
  svgViewBox,
  branchChildrenMap,
} = useFlowGroupBackground({
  vueFlowNodes,
  vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
  getNodeData,
})

// ---------- 共享的程序化边变更标志 ----------
const isProgrammaticEdgeChange = ref(false)

// ---------- 布局模式（需在 composable 调用前定义） ----------
const layoutMode = ref<LayoutMode>('standard')

// ---------- 边操作 composable ----------
const {
  conditionDialogVisible,
  currentEdgeForm,
  onConnect,
  handleEditEdge: _handleEditEdge,
  handleDeleteEdge: _handleDeleteEdge,
  onEdgeConditionConfirm,
  onEdgesChange,
  handleEdgeSuggestionsConfirmed,
} = useFlowEdgeOps({
  vueFlowNodes,
  vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
  emitSortData,
  saveSnapshot,
  historyStack,
  applyAllEdgeStyles,
  currentEdgeStyles,
  isOverviewMode,
  normalizeEdges,
  isProgrammaticEdgeChange,
})

// 包装 handleEditEdge / handleDeleteEdge：关闭 tooltip 后再调用 composable 逻辑
const handleEditEdge = (edge: any) => {
  _handleEditEdge(edge, () => {
    edgeTooltipVisible.value = false
    edgeTooltipData.value = null
  })
}

const handleDeleteEdge = (edge: any) => {
  _handleDeleteEdge(edge, () => {
    edgeTooltipVisible.value = false
    edgeTooltipData.value = null
  })
}

// ---------- 流程类型操作 composable ----------
const {
  pendingFlowTypeChange,
  pendingFlowMeta,
  flowTypeConfigVisible,
  handleFlowTypeChange,
  handleFlowTypeConfigConfirm,
  handleQuickCreateBranch,
  handleBatchFlowTypeChange,
} = useFlowTypeOps({
  vueFlowNodes,
  vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
  selectedNodes,
  emitSortData,
  saveSnapshot,
  applyAllEdgeStyles,
  currentEdgeStyles,
  isOverviewMode,
  getNodeData,
  getMainNodesInOrder,
  normalizeMainNodeOrders,
  normalizeEdges,
  autoLayoutByMode: autoLayoutByMode as (
    mode: string,
    nodes: FlowEditorNode[],
    edges: FlowGraphEdge[],
    focusedNodeId?: string | null,
  ) => FlowEditorNode[],
  layoutMode: layoutMode as Ref<string>,
  focusedNodeId,
  getEdgeStyle,
  isProgrammaticEdgeChange,
  fitView: async (opts: { duration: number; padding: number }) => { void await fitView(opts) },
})

// ---------- 主干排序与删除 composable ----------
const {
  handleDeleteSelected,
  canMoveMainBackward,
  canMoveMainForward,
  moveSelectedMainNode,
  getSelectedMainNodeId,
  getSelectedMainOrder,
} = useFlowMainOrder({
  vueFlowNodes,
  vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
  selectedNodes,
  focusedNodeId,
  collapsedParentNodeIds,
  emitSortData,
  saveSnapshot,
  getNodeData,
  getMainNodesInOrder,
  normalizeMainNodeOrders,
  isProgrammaticEdgeChange,
})

// ---------- 剩余状态 ----------
const showPromptPreview = ref(false)
const promptPreviewFlowData = computed(
  () => getFlowSortSubmitData().flow_sort_data as unknown as Record<string, unknown>
)

const showEdgeSuggestion = ref(false)

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

// ---------- 辅助方法 ----------
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

const mainNodeOptions = computed(() => {
  const mainNodes = getMainNodesInOrder(vueFlowNodes.value)
  const nonMainNodes = vueFlowNodes.value.filter((n) => getNodeData(n).flow_type !== 'main')
  const mainOptions = mainNodes.map((node) => ({
    id: node.id,
    screen_id: getNodeData(node).screen_id,
    screen_name: getNodeData(node).screen_name,
    main_order: getNodeData(node).main_order,
    flow_type: getNodeData(node).flow_type,
    depth: 0,
  }))
  const nonMainOptions = nonMainNodes.map((node) => {
    const d = getNodeData(node)
    const parentEdge = vueFlowEdges.value.find(
      (e: any) => e.target === node.id && ['branch', 'exception', 'bypass'].includes(e.data?.edge_type)
    )
    let depth = 1
    if (parentEdge) {
      const parentOption = mainOptions.find((o) => o.id === parentEdge.source)
      if (parentOption) {
        depth = parentOption.depth + 1
      }
    }
    return {
      id: node.id,
      screen_id: d.screen_id,
      screen_name: d.screen_name,
      flow_type: d.flow_type,
      depth,
    }
  })
  return [...mainOptions, ...nonMainOptions]
})

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

let lastScreens: UIScreen[] = []

watch(
  () => props.screens,
  (newScreens) => {
    if (isScreensEqual(newScreens, lastScreens)) return
    lastScreens = newScreens
    isRestoredFromBackend.value = false
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
    vueFlowEdges.value = applyAllEdgeStyles(autoEdges as FlowGraphEdge[])
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
  viewport,
  (nextViewport) => {
    currentZoom.value = nextViewport?.zoom ?? 1
  },
  { deep: true, immediate: true }
)

const onNodeDragStart = (event: { node?: Node }) => {
  draggingNodeId.value = event.node?.id || null
  if (event.node?.id && !selectedNodes.value.includes(event.node.id)) {
    selectedNodes.value = [event.node.id]
  }
}

const onNodeDragStop = () => {
  draggingNodeId.value = null
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

    const source =
      other.position.x < draggedNode.position.x ||
      (other.position.x === draggedNode.position.x && other.position.y < draggedNode.position.y)
        ? other
        : draggedNode
    const target = source === other ? draggedNode : other
    const key = `${source.id}->${target.id}`
    const reverseKey = `${target.id}->${source.id}`

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

const handleFitView = () => {
  void fitView({ duration: 220, padding: 0.15 })
}

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

const handleSelectionChange = (selected: { nodes: Node[] }) => {
  selectedNodes.value = selected.nodes.map((n) => n.id)
}

const handleToggleCollapse = (nodeId: string) => {
  const idx = collapsedParentNodeIds.value.indexOf(nodeId)
  if (idx >= 0) {
    collapsedParentNodeIds.value.splice(idx, 1)
  } else {
    collapsedParentNodeIds.value.push(nodeId)
  }
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

// 统一快捷键处理
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

function syncStoreToEditor() {
  const storeNodes = flowSortStore.nodes
  if (storeNodes.length === 0) return

  console.log('[FlowSort] 同步 store 数据到编辑器, nodes:', storeNodes.length, 'edges:', flowSortStore.edges.length)

  const screenById = new Map(props.screens.map((s) => [s.id, s]))

  vueFlowNodes.value = storeNodes.map((node) => ({
    id: node.id,
    type: 'custom',
    position: node.position || { x: 0, y: 0 },
    data: {
      screen_id: node.screen_id,
      screen_name: node.screen_name,
      summary: node.summary,
      ui_spec_elements: (node.ui_spec_elements || []) as EditorNodeData['ui_spec_elements'],
      flow_type: node.flow_type,
      main_order: node.main_order,
      image_url: props.screenImageUrls?.[node.screen_id] || node.image_url || '',
      element_count: screenById.get(node.screen_id)?.element_count,
      flow_meta: node.flow_meta,
    },
  }))

  const rawEdges = flowSortStore.edges.map((edge) => {
    const sourceNode = vueFlowNodes.value.find((n) => getNodeData(n).screen_id === Number(edge.source))
    const targetNode = vueFlowNodes.value.find((n) => getNodeData(n).screen_id === Number(edge.target))
    return {
      id: edge.id,
      source: sourceNode?.id || edge.source,
      target: targetNode?.id || edge.target,
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
  vueFlowEdges.value = applyAllEdgeStyles(rawEdges as FlowGraphEdge[])
  saveSnapshot()
  isRestoredFromBackend.value = true
  console.log('[FlowSort] 编辑器数据已从后端还原')
}

watch(
  () => flowSortStore.isBackendLoaded,
  (isLoaded, wasLoaded) => {
    if (isLoaded && !wasLoaded && flowSortStore.nodes.length > 0) {
      nextTick(() => {
        syncStoreToEditor()
      })
    }
  }
)

onMounted(() => {
  if (editorRef.value) editorRef.value.focus()
  if (flowSortStore.isBackendLoaded && flowSortStore.nodes.length > 0 && !isRestoredFromBackend.value) {
    nextTick(() => {
      syncStoreToEditor()
    })
  }
  setTimeout(() => {
    showShortcutsTip.value = false
  }, SHORTCUTS_TIP_DURATION)
})
</script>

<style scoped lang="scss">
@import './FlowSortEditor.scss';
</style>