<template>
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
        <el-button size="default" :type="ctx.displayMode.value === 'overview' ? 'primary' : ''" @click="ctx.displayMode.value = 'overview'">总览</el-button>
        <el-button size="default" :type="ctx.displayMode.value === 'edit' ? 'primary' : ''" @click="ctx.displayMode.value = 'edit'">编辑</el-button>
      </el-button-group>
      <el-divider direction="vertical" />
      <el-button-group class="action-group">
        <el-dropdown trigger="click" @command="ctx.handleLayoutModeChange">
          <el-button size="default" title="自动布局 (Ctrl+L)"><el-icon><Grid /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="(label, mode) in LAYOUT_MODE_LABELS" :key="mode" :command="mode" :class="{ 'is-active': ctx.layoutMode.value === mode }">{{ label }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-tooltip content="预览 Prompt (Ctrl+P)" placement="bottom">
          <el-button size="default" @click="ctx.handlePreviewPrompt"><el-icon><View /></el-icon></el-button>
        </el-tooltip>
        <el-tooltip content="适配视图 (Ctrl+0)" placement="bottom">
          <el-button size="default" @click="ctx.handleFitView"><el-icon><FullScreen /></el-icon></el-button>
        </el-tooltip>
        <el-tooltip content="撤销 (Ctrl+Z)" placement="bottom">
          <el-button size="default" @click="ctx.handleUndo" :disabled="!ctx.canUndo.value"><el-icon><RefreshLeft /></el-icon></el-button>
        </el-tooltip>
      </el-button-group>
      <el-divider direction="vertical" />
      <div v-if="ctx.selectedNodes.value.length > 0" class="selection-info">
        <el-tag type="primary" size="small" effect="plain">已选 {{ ctx.selectedNodes.value.length }} 个节点</el-tag>
        <el-button size="small" type="danger" @click="ctx.handleDeleteSelected"><el-icon><Delete /></el-icon>删除</el-button>
        <el-dropdown v-if="ctx.selectedNodes.value.length > 1" trigger="click" @command="ctx.handleBatchFlowTypeChange">
          <el-button size="small" type="warning">批量设置类型<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
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
      <div v-if="ctx.getSelectedMainNodeId(ctx.vueFlowNodes.value)" class="main-order-actions">
        <el-tag type="success" size="small" effect="plain">主干第 {{ ctx.getSelectedMainOrder(ctx.vueFlowNodes.value) }} 步</el-tag>
        <el-button size="small" @click="ctx.moveSelectedMainNode(-1)" :disabled="!ctx.canMoveMainBackward()">主干前移</el-button>
        <el-button size="small" @click="ctx.moveSelectedMainNode(1)" :disabled="!ctx.canMoveMainForward()">主干后移</el-button>
      </div>
      <div v-if="ctx.canQuickCreateBranch.value" class="quick-create-branch-action">
        <el-button size="small" type="success" @click="ctx.handleQuickCreateBranch"><el-icon><Plus /></el-icon>创建分支</el-button>
      </div>
      <div class="zoom-controls">
        <el-tooltip content="智能识别跳转关系" placement="bottom">
          <el-button size="default" @click="ctx.showEdgeSuggestion.value = true"><el-icon><MagicStick /></el-icon></el-button>
        </el-tooltip>
        <el-tooltip :content="ctx.isPlaying.value ? '退出路径播放' : '路径播放'" placement="bottom">
          <el-button size="default" :type="ctx.isPlaying.value ? 'primary' : ''" @click="ctx.isPlaying.value ? ctx.stopPlayback() : ctx.startPlayback(ctx.vueFlowNodes.value, ctx.vueFlowEdges.value as any)">
            <el-icon><VideoPlay v-if="!ctx.isPlaying.value" /><VideoPause v-else /></el-icon>
          </el-button>
        </el-tooltip>
        <div class="search-wrapper">
          <el-input v-model="ctx.searchKeyword.value" placeholder="搜索页面..." size="small" class="search-input" clearable :prefix-icon="Search" @input="ctx.debouncedSearch" @clear="ctx.clearSearch" @keydown.enter="ctx.locateFirstMatch" @focus="ctx.showSearchDropdown.value = true" @blur="ctx.handleSearchBlur" />
          <div v-if="ctx.showSearchDropdown.value && ctx.searchResults.value.length > 0" class="search-dropdown">
            <div v-for="item in ctx.searchResults.value" :key="item.id" class="search-result-item" @click="ctx.locateNode(item.id)">
              <span class="result-name">{{ item.screen_name }}</span>
              <el-tag size="small" :type="FLOW_TYPE_TAG_MAP[item.flow_type] || 'primary'" effect="plain" class="result-tag">{{ FLOW_TYPE_LABEL_MAP[item.flow_type] || '主干' }}</el-tag>
            </div>
          </div>
          <div v-if="ctx.showSearchDropdown.value && ctx.searchKeyword.value && ctx.searchResults.value.length === 0" class="search-dropdown">
            <div class="search-empty">未找到匹配页面</div>
          </div>
        </div>
      </div>
      <div class="save-controls">
        <template v-if="ctx.flowSortStore.saveStatus === 'unsaved'">
          <el-tooltip v-if="!ctx.flowSortStore.projectId" content="请先选择项目" placement="top">
            <el-button type="primary" size="small" disabled><el-icon><Upload /></el-icon> 保存</el-button>
          </el-tooltip>
          <el-button v-else type="primary" size="small" @click="ctx.flowSortStore.manualSave()"><el-icon><Upload /></el-icon> 保存</el-button>
        </template>
        <template v-else-if="ctx.flowSortStore.saveStatus === 'saving'">
          <span class="save-status-inner"><el-icon class="is-loading"><Loading /></el-icon><span class="save-text">保存中...</span></span>
        </template>
        <template v-else-if="ctx.flowSortStore.saveStatus === 'saved'">
          <span class="save-status-inner saved"><el-icon><CircleCheck /></el-icon><span class="save-text">已保存</span></span>
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
import { Grid, View, RefreshLeft, Delete, FullScreen, Search, Plus, ArrowDown, VideoPlay, VideoPause, MagicStick, Upload, Loading, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { useFlowSortEditor, FLOW_TYPE_TAG_MAP, FLOW_TYPE_LABEL_MAP, LAYOUT_MODE_LABELS } from '@/composables/flowSort/useFlowSortEditor'

const ctx = useFlowSortEditor()
</script>
