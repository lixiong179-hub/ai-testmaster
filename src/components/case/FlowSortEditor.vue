<template>
  <div
    class="flow-sort-editor"
    :class="{ 'overview-mode': ctx.displayMode.value === 'overview' }"
    @keydown="ctx.handleKeyDown"
    tabindex="0"
    ref="ctx.editorRef.value"
  >
    <FlowSortToolbar />
    <div class="editor-container">
      <div class="graph-mode">
        <VueFlow
          v-model:nodes="ctx.vueFlowNodes.value"
          v-model:edges="ctx.vueFlowEdges.value"
          @edges-change="ctx.onEdgesChange"
          :default-viewport="{ x: 0, y: 0, zoom: 1 }"
          :default-edge-options="ctx.defaultEdgeOptions.value"
          :min-zoom="0.2"
          :max-zoom="4"
          :nodes-draggable="ctx.displayMode.value === 'edit'"
          :nodes-connectable="ctx.displayMode.value === 'edit'"
          :elements-selectable="ctx.displayMode.value === 'edit'"
          fit-view-on-init
          @connect="ctx.onConnect"
          @node-drag-start="ctx.onNodeDragStart"
          @node-drag-stop="ctx.onNodeDragStop"
          @pane-click="ctx.handlePaneClick"
          @edge-mouse-enter="ctx.onEdgeMouseEnter"
          @edge-mouse-move="ctx.onEdgeMouseMove"
          @edge-mouse-leave="ctx.onEdgeMouseLeave"
          @node-click="ctx.handleNodeClick"
          @selection-change="ctx.handleSelectionChange"
        >
          <Background pattern-color="#e4e7ed" :gap="20" />
          <Controls />
          <MiniMap :node-color="ctx.minimapNodeColor" :node-stroke-color="ctx.minimapNodeStroke" />
          <svg
            v-if="ctx.showGroupBackground.value && ctx.nodeGroups.value.length > 0"
            class="group-bg-svg"
            :style="{ transform: `translate(${ctx.svgViewBox.value.x}px, ${ctx.svgViewBox.value.y}px) scale(${ctx.currentZoom.value})`, transformOrigin: '0 0' }"
          >
            <rect v-for="group in ctx.nodeGroups.value" :key="group.id" :x="group.bounds.x - ctx.groupPadding" :y="group.bounds.y - ctx.groupPadding" :width="group.bounds.width + ctx.groupPadding * 2" :height="group.bounds.height + ctx.groupPadding * 2" :rx="12" :fill="group.color" :stroke="group.strokeColor" stroke-width="1.5" stroke-dasharray="6 3" :opacity="0.25" />
            <text v-for="group in ctx.nodeGroups.value" :key="'label-' + group.id" :x="group.bounds.x - ctx.groupPadding + 8" :y="group.bounds.y - ctx.groupPadding + 16" font-size="12" :fill="group.strokeColor" :opacity="0.6">{{ group.label }}</text>
          </svg>
          <template #node-custom="nodeProps">
            <FlowNodeCard
              :data="nodeProps.data"
              :is-selected="ctx.selectedNodes.value.includes(nodeProps.id)"
              :is-dragging="ctx.draggingNodeId.value === nodeProps.id"
              :display-mode="ctx.displayMode.value"
              :is-search-match="ctx.searchMatchIds.value.includes(nodeProps.id)"
              :is-focused="ctx.focusedNodeId.value === nodeProps.id"
              :is-upstream="ctx.upstreamNodeIds.value.has(nodeProps.id)"
              :is-downstream="ctx.downstreamNodeIds.value.has(nodeProps.id)"
              :is-path-dimmed="ctx.focusedNodeId.value !== null && !ctx.allPathNodeIds.value.has(nodeProps.id)"
              :child-branch-count="ctx.getChildBranchCount(nodeProps.id)"
              :is-collapsed="ctx.collapsedParentNodeIds.value.includes(nodeProps.id)"
              :is-test-point-related="ctx.highlightedScreenIds.value.has(nodeProps.data.screen_id)"
              @update:flow-type="(type: string) => ctx.handleFlowTypeChange(nodeProps.id, type)"
              @preview="ctx.handleNodePreview(nodeProps.data)"
              @toggle-collapse="(nodeId: string) => ctx.handleToggleCollapse(nodeId)"
            />
          </template>
        </VueFlow>
      </div>
    </div>

    <FlowSortEdgeTooltip />

    <EdgeConditionDialog v-model:visible="ctx.conditionDialogVisible.value" :edge-data="ctx.currentEdgeForm.value" @confirm="ctx.onEdgeConditionConfirm" />
    <FlowTypeConfigDialog v-model:visible="ctx.flowTypeConfigVisible.value" :flow-type="(ctx.pendingFlowTypeChange.value?.type as any) || 'branch'" :main-node-options="ctx.mainNodeOptions.value" :initial-data="ctx.pendingFlowMeta.value" @confirm="ctx.handleFlowTypeConfigConfirm" />
    <EdgeSuggestionDialog v-model:visible="ctx.showEdgeSuggestion.value" v-model:nodes="ctx.vueFlowNodes.value" v-model:edges="ctx.vueFlowEdges.value" @confirm="ctx.handleEdgeSuggestionsConfirmed" />
    <FlowPromptPreviewDialog v-model:visible="ctx.showPromptPreview.value" :flow-sort-data="ctx.promptPreviewFlowData.value" />

    <transition name="tip-fade">
      <div v-if="ctx.showShortcutsTip.value" class="shortcuts-tip">
        <kbd>Delete</kbd> 删除选中 | <kbd>Ctrl+Z</kbd> 撤销 | <kbd>Ctrl+S</kbd> 保存 | <kbd>Ctrl+P</kbd> 预览 Prompt | <kbd>Space</kbd> 预览图片 | <kbd>Ctrl+L</kbd> 自动布局 | <kbd>Ctrl+0</kbd> 适配视图 | <kbd>Esc</kbd> 取消选择
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { VueFlow } from '@vue-flow/core'
import { Background, Controls, MiniMap } from '@vue-flow/additional-components'
import FlowNodeCard from './FlowNodeCard.vue'
import EdgeConditionDialog from './EdgeConditionDialog.vue'
import FlowTypeConfigDialog from './FlowTypeConfigDialog.vue'
import EdgeSuggestionDialog from './EdgeSuggestionDialog.vue'
import FlowPromptPreviewDialog from './FlowPromptPreviewDialog.vue'
import { provideFlowSortEditor } from '@/composables/flowSort/useFlowSortEditor'
import { useFlowSortEditorSync } from '@/composables/flowSort/useFlowSortEditorSync'
import FlowSortToolbar from './components/FlowSortToolbar.vue'
import FlowSortEdgeTooltip from './components/FlowSortEdgeTooltip.vue'
import type { UIScreen } from '@/api/uiPrototype'

const props = defineProps<{
  screens: UIScreen[]
  screenImageUrls?: Record<number, string>
  moduleInfo?: { name: string; description: string }
  highlightedScreenIds?: number[]
}>()

const emit = defineEmits<{
  'update:sort-data': [data: any]
  'preview-screen': [screen: any]
}>()

const ctx = provideFlowSortEditor(props, emit)
useFlowSortEditorSync(ctx)

defineExpose({ getFlowSortSubmitData: ctx.getFlowSortSubmitData, getFlowValidationIssues: ctx.getFlowValidationIssues })
</script>

<style scoped lang="scss">
@import './FlowSortEditor.scss';
</style>
