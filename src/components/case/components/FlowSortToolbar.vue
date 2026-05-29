<template>
  <div class="editor-toolbar">
    <div class="toolbar-left">
      <div class="editor-heading">
        <span class="editor-title">{{
          ctx.flowSortStore.quickMode ? '快速生成' : '流程编排'
        }}</span>
        <span class="editor-subtitle">{{
          ctx.flowSortStore.quickMode
            ? '按已选 UI 页面生成测试用例'
            : '总览查看流程全貌，调整模式下编辑连线与顺序'
        }}</span>
      </div>
      <div class="mode-switch generation-mode">
        <span class="mode-label">生成策略</span>
        <el-button-group>
          <el-button
            size="small"
            :type="ctx.flowSortStore.quickMode === true ? 'primary' : ''"
            @click="ctx.flowSortStore.setQuickMode(true)"
            >快速生成</el-button
          >
          <el-button
            size="small"
            :type="ctx.flowSortStore.quickMode === false ? 'primary' : ''"
            @click="ctx.flowSortStore.setQuickMode(false)"
            >流程编排</el-button
          >
        </el-button-group>
        <transition name="tip-fade">
          <span v-if="ctx.flowSortStore.quickMode === true" class="mode-hint"
            >按需求文档和 UI 元素生成，忽略画布连线</span
          >
        </transition>
        <transition name="tip-fade">
          <span
            v-if="ctx.flowSortStore.quickMode === true && ctx.vueFlowEdges.value.length > 0"
            class="mode-hint mode-hint-warning"
          >
            已手动添加连线，<el-link
              type="primary"
              underline="never"
              @click="ctx.flowSortStore.setQuickMode(false)"
              >切换到流程编排</el-link
            >可在 AI 生成中生效
          </span>
        </transition>
        <transition name="tip-fade">
          <span v-if="showExistingEdgeHint" class="mode-hint mode-hint-warning">
            检测到已配置的流程连线，<el-link
              type="primary"
              underline="never"
              @click="ctx.flowSortStore.setQuickMode(false)"
              >切换到流程编排</el-link
            >可使用连线信息生成更精准的测试用例
            <el-link
              type="info"
              underline="never"
              class="dismiss-link"
              @click="dismissExistingEdgeHint"
              >不再提示</el-link
            >
          </span>
        </transition>
      </div>
      <div v-if="ctx.flowSortStore.quickMode === false" class="flow-legend">
        <span class="legend-item legend-main">主干</span>
        <span class="legend-item legend-branch">分支</span>
        <span class="legend-item legend-exception">异常</span>
        <span class="legend-item legend-bypass">弹窗</span>
      </div>
    </div>
    <div class="toolbar-actions" :class="{ 'is-overview': ctx.displayMode.value === 'overview' }">
      <template v-if="ctx.flowSortStore.quickMode === false">
        <div class="toolbar-mode-group">
          <span class="mode-label">编排视图</span>
          <el-button-group class="mode-toggle">
            <el-button
              size="default"
              :type="ctx.displayMode.value === 'overview' ? 'primary' : ''"
              @click="ctx.displayMode.value = 'overview'"
              >总览</el-button
            >
            <el-button
              size="default"
              :type="ctx.displayMode.value === 'edit' ? 'primary' : ''"
              @click="ctx.displayMode.value = 'edit'"
              >调整</el-button
            >
          </el-button-group>
        </div>
        <template v-if="ctx.displayMode.value === 'overview'">
          <el-divider direction="vertical" />
          <el-tooltip content="适配视图" placement="bottom">
            <el-button size="default" @click="ctx.handleFitView"
              ><el-icon><FullScreen /></el-icon
            ></el-button>
          </el-tooltip>
          <div class="overview-stats">
            <el-tag size="small" type="info" effect="plain"
              >{{ ctx.vueFlowNodes.value.length }} 个页面</el-tag
            >
            <el-tag size="small" type="primary" effect="plain">{{ mainNodeCount }} 个主干</el-tag>
          </div>
        </template>
        <template v-else>
          <el-divider direction="vertical" />
          <el-tooltip content="主干步骤列表" placement="bottom">
            <el-button
              size="default"
              :type="ctx.showMainStepList.value ? 'primary' : ''"
              @click="ctx.showMainStepList.value = !ctx.showMainStepList.value"
              ><el-icon><List /></el-icon
            ></el-button>
          </el-tooltip>
          <el-dropdown trigger="click" @command="handleFilterChange">
            <el-tooltip content="流程筛选" placement="bottom">
              <el-button size="default" :type="ctx.flowFilter.value !== 'all' ? 'warning' : ''"
                ><el-icon><Filter /></el-icon
              ></el-button>
            </el-tooltip>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  command="all"
                  :class="{ 'is-active': ctx.flowFilter.value === 'all' }"
                  >显示全部</el-dropdown-item
                >
                <el-dropdown-item
                  command="main"
                  :class="{ 'is-active': ctx.flowFilter.value === 'main' }"
                  >只看主干</el-dropdown-item
                >
                <el-dropdown-item
                  command="branch"
                  :class="{ 'is-active': ctx.flowFilter.value === 'branch' }"
                  >主干+分支</el-dropdown-item
                >
                <el-dropdown-item
                  command="exception"
                  :class="{ 'is-active': ctx.flowFilter.value === 'exception' }"
                  >主干+异常</el-dropdown-item
                >
                <el-dropdown-item
                  command="bypass"
                  :class="{ 'is-active': ctx.flowFilter.value === 'bypass' }"
                  >主干+弹窗</el-dropdown-item
                >
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button-group class="action-group">
            <el-dropdown trigger="click" @command="ctx.handleLayoutModeChange">
              <el-button size="default" title="自动布局 (Ctrl+L)"
                ><el-icon><Grid /></el-icon
              ></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="(label, mode) in LAYOUT_MODE_LABELS"
                    :key="mode"
                    :command="mode"
                    :class="{ 'is-active': ctx.layoutMode.value === mode }"
                    >{{ label }}</el-dropdown-item
                  >
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-tooltip content="预览 Prompt (Ctrl+P)" placement="bottom">
              <el-button size="default" @click="ctx.handlePreviewPrompt"
                ><el-icon><View /></el-icon
              ></el-button>
            </el-tooltip>
            <el-tooltip content="适配视图 (Ctrl+0)" placement="bottom">
              <el-button size="default" @click="ctx.handleFitView"
                ><el-icon><FullScreen /></el-icon
              ></el-button>
            </el-tooltip>
            <el-tooltip content="撤销 (Ctrl+Z)" placement="bottom">
              <el-button size="default" @click="ctx.handleUndo" :disabled="!ctx.canUndo.value"
                ><el-icon><RefreshLeft /></el-icon
              ></el-button>
            </el-tooltip>
            <el-tooltip content="流程完整度" placement="bottom">
              <el-button size="default" @click="toggleCompletenessPanel"
                ><el-icon><DataAnalysis /></el-icon
              ></el-button>
            </el-tooltip>
          </el-button-group>
          <el-divider direction="vertical" />
          <div v-if="ctx.selectedNodes.value.length > 0" class="selection-info">
            <el-tag type="primary" size="small" effect="plain"
              >已选 {{ ctx.selectedNodes.value.length }} 个节点</el-tag
            >
            <el-button size="small" type="danger" @click="ctx.handleDeleteSelected"
              ><el-icon><Delete /></el-icon>删除</el-button
            >
            <el-dropdown
              v-if="ctx.selectedNodes.value.length > 1"
              trigger="click"
              @command="ctx.handleBatchFlowTypeChange"
            >
              <el-button size="small" type="warning"
                >批量设置类型<el-icon class="el-icon--right"><ArrowDown /></el-icon
              ></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="main">主干流程</el-dropdown-item>
                  <el-dropdown-item command="branch">分支流程</el-dropdown-item>
                  <el-dropdown-item command="exception">异常流程</el-dropdown-item>
                  <el-dropdown-item command="bypass">弹窗/浮层</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <div v-if="ctx.getSelectedMainNodeId(ctx.vueFlowNodes.value)" class="main-order-actions">
            <el-tag type="success" size="small" effect="plain"
              >主干第 {{ ctx.getSelectedMainOrder(ctx.vueFlowNodes.value) }} 步</el-tag
            >
            <el-button
              size="small"
              @click="ctx.moveSelectedMainNode(-1)"
              :disabled="!ctx.canMoveMainBackward()"
              >主干前移</el-button
            >
            <el-button
              size="small"
              @click="ctx.moveSelectedMainNode(1)"
              :disabled="!ctx.canMoveMainForward()"
              >主干后移</el-button
            >
          </div>
          <div v-if="ctx.canQuickCreateBranch.value" class="quick-create-branch-action">
            <el-button size="small" type="success" @click="ctx.handleQuickCreateBranch"
              ><el-icon><Plus /></el-icon>创建分支</el-button
            >
          </div>
          <div class="zoom-controls">
            <el-tooltip content="智能识别跳转关系" placement="bottom">
              <el-button size="default" @click="ctx.showEdgeSuggestion.value = true"
                ><el-icon><MagicStick /></el-icon
              ></el-button>
            </el-tooltip>
            <el-tooltip
              :content="ctx.isPlaying.value ? '退出路径播放' : '路径播放'"
              placement="bottom"
            >
              <el-button
                size="default"
                :type="ctx.isPlaying.value ? 'primary' : ''"
                @click="
                  ctx.isPlaying.value
                    ? ctx.stopPlayback()
                    : ctx.startPlayback(ctx.vueFlowNodes.value, ctx.vueFlowEdges.value as any)
                "
              >
                <el-icon><VideoPlay v-if="!ctx.isPlaying.value" /><VideoPause v-else /></el-icon>
              </el-button>
            </el-tooltip>
            <div class="search-wrapper">
              <el-input
                v-model="ctx.searchKeyword.value"
                placeholder="搜索页面..."
                size="small"
                class="search-input"
                clearable
                :prefix-icon="Search"
                @input="ctx.debouncedSearch"
                @clear="ctx.clearSearch"
                @keydown.enter="ctx.locateFirstMatch"
                @keydown.escape="ctx.clearSearch"
                @focus="ctx.showSearchDropdown.value = true"
                @blur="ctx.handleSearchBlur"
              />
              <div
                v-if="ctx.showSearchDropdown.value && ctx.searchResults.value.length > 0"
                class="search-dropdown"
              >
                <div
                  v-for="item in ctx.searchResults.value"
                  :key="item.id"
                  class="search-result-item"
                  @click="ctx.locateNode(item.id)"
                >
                  <span class="result-name">{{ item.screen_name }}</span>
                  <el-tag
                    size="small"
                    :type="FLOW_TYPE_TAG_MAP[item.flow_type] || 'primary'"
                    effect="plain"
                    class="result-tag"
                    >{{ FLOW_TYPE_LABEL_MAP[item.flow_type] || '主干' }}</el-tag
                  >
                </div>
              </div>
              <div
                v-if="
                  ctx.showSearchDropdown.value &&
                  ctx.searchKeyword.value &&
                  ctx.searchResults.value.length === 0
                "
                class="search-dropdown"
              >
                <div class="search-empty">未找到匹配页面</div>
              </div>
            </div>
          </div>
        </template>
      </template>
      <div v-else class="quick-toolbar-summary">
        <el-tag size="small" type="info" effect="plain"
          >页面预览 {{ ctx.props.screens.length }}</el-tag
        >
        <el-tag v-if="ctx.vueFlowEdges.value.length > 0" size="small" type="warning" effect="plain"
          >已保存编排</el-tag
        >
      </div>
      <div class="save-controls">
        <template v-if="ctx.flowSortStore.saveStatus === 'unsaved'">
          <el-tooltip v-if="!ctx.flowSortStore.projectId" content="请先选择项目" placement="top">
            <el-button type="primary" size="small" disabled
              ><el-icon><Upload /></el-icon> 保存</el-button
            >
          </el-tooltip>
          <el-button v-else type="primary" size="small" @click="ctx.flowSortStore.manualSave()"
            ><el-icon><Upload /></el-icon> 保存</el-button
          >
        </template>
        <template v-else-if="ctx.flowSortStore.saveStatus === 'saving'">
          <span class="save-status-inner"
            ><el-icon class="is-loading"><Loading /></el-icon
            ><span class="save-text">保存中...</span></span
          >
        </template>
        <template v-else-if="ctx.flowSortStore.saveStatus === 'saved'">
          <span class="save-status-inner saved"
            ><el-icon><CircleCheck /></el-icon><span class="save-text">已保存</span></span
          >
        </template>
        <template v-else-if="ctx.flowSortStore.saveStatus === 'error'">
          <span class="save-status-inner error" @click="ctx.flowSortStore.manualRetrySave()">
            <el-icon><CircleClose /></el-icon><span class="save-text">保存失败</span>
            <el-button size="small" type="danger" text class="retry-btn">重试</el-button>
          </span>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import {
  Grid,
  View,
  RefreshLeft,
  Delete,
  FullScreen,
  Search,
  Plus,
  ArrowDown,
  VideoPlay,
  VideoPause,
  MagicStick,
  Upload,
  Loading,
  CircleCheck,
  CircleClose,
  DataAnalysis,
  List,
  Filter,
} from '@element-plus/icons-vue'
import {
  useFlowSortEditor,
  FLOW_TYPE_TAG_MAP,
  FLOW_TYPE_LABEL_MAP,
  LAYOUT_MODE_LABELS,
} from '@/composables/flowSort/useFlowSortEditor'

const ctx = useFlowSortEditor()

const mainNodeCount = computed(
  () => ctx.vueFlowNodes.value.filter((n: any) => n.data?.flow_type === 'main').length
)

const handleFilterChange = (command: string | number | boolean) => {
  ctx.flowFilter.value = command as 'all' | 'main' | 'branch' | 'exception' | 'bypass'
  ctx.applyFlowFilter()
}

/** 切换完整度面板显示/隐藏 */
const toggleCompletenessPanel = () => {
  ctx.showCompletenessPanel.value = !ctx.showCompletenessPanel.value
}

const EXISTING_EDGE_HINT_DISMISSED_KEY = 'flow-editor-quick-mode-hint-dismissed'

const showExistingEdgeHint = ref(false)

watch(
  () => ctx.flowSortStore.isBackendLoaded,
  (loaded) => {
    if (!loaded) return
    if (ctx.flowSortStore.quickMode === false) return
    if (ctx.flowSortStore.edges.length === 0) return
    let dismissed = false
    try {
      dismissed = localStorage.getItem(EXISTING_EDGE_HINT_DISMISSED_KEY) === 'true'
    } catch {
      /* silent */
    }
    if (!dismissed) showExistingEdgeHint.value = true
  },
  { immediate: true }
)

const dismissExistingEdgeHint = () => {
  showExistingEdgeHint.value = false
  try {
    localStorage.setItem(EXISTING_EDGE_HINT_DISMISSED_KEY, 'true')
  } catch {
    /* silent */
  }
}
</script>

<style scoped>
.mode-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.toolbar-mode-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-start;
  min-width: 0;
  overflow: visible;
}
.toolbar-actions :deep(.el-divider--vertical) {
  height: 24px;
  margin: 0 2px;
}
.toolbar-actions :deep(.el-button) {
  min-width: 32px;
}
.toolbar-actions .selection-info,
.toolbar-actions .main-order-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.toolbar-actions .zoom-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.toolbar-actions .save-controls {
  flex-shrink: 0;
  margin-left: auto;
}
.toolbar-actions.is-overview {
  gap: 0;
}
.toolbar-actions.is-overview .toolbar-mode-group {
  padding: 2px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #f5f7fa;
}
.toolbar-actions.is-overview .mode-label {
  padding: 0 8px;
}
.overview-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.quick-toolbar-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.mode-label {
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
}
.mode-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1;
}
.mode-hint-warning {
  color: #e6a23c;
}
.dismiss-link {
  margin-left: 8px;
  font-size: 12px;
}
.tip-fade-enter-active,
.tip-fade-leave-active {
  transition: opacity 0.3s ease;
}
.tip-fade-enter-from,
.tip-fade-leave-to {
  opacity: 0;
}
</style>
