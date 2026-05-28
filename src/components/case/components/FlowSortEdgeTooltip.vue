<template>
  <transition name="tooltip-fade">
    <div
      v-if="ctx.edgeTooltipVisible.value && ctx.edgeTooltipData.value"
      class="edge-tooltip"
      :style="{
        left: ctx.edgeTooltipPosition.value.x + 'px',
        top: ctx.edgeTooltipPosition.value.y + 'px',
      }"
      @mouseenter="ctx.onEdgeTooltipEnter"
      @mouseleave="ctx.onEdgeTooltipLeave"
    >
      <div class="tooltip-header">
        <el-tag
          size="small"
          :type="
            FLOW_TYPE_TAG_MAP[ctx.edgeTooltipData.value.data?.edge_type as string] || 'primary'
          "
          effect="dark"
        >
          {{ FLOW_TYPE_LABEL_MAP[ctx.edgeTooltipData.value.data?.edge_type as string] || '跳转' }}
        </el-tag>
        <el-button
          size="small"
          :icon="Edit"
          circle
          class="tooltip-edit-btn"
          @click="ctx.handleEditEdge(ctx.edgeTooltipData.value)"
        />
        <el-button
          size="small"
          :icon="Delete"
          circle
          class="tooltip-delete-btn"
          type="danger"
          @click="ctx.handleDeleteEdge(ctx.edgeTooltipData.value)"
        />
      </div>
      <div v-if="ctx.edgeTooltipData.value.data?.condition" class="tooltip-row">
        <span class="tooltip-label">触发条件：</span>
        <span class="tooltip-value">{{ ctx.edgeTooltipData.value.data.condition }}</span>
      </div>
      <div v-if="ctx.edgeTooltipData.value.data?.trigger_action" class="tooltip-row">
        <span class="tooltip-label">触发动作：</span>
        <span class="tooltip-value">{{ ctx.edgeTooltipData.value.data.trigger_action }}</span>
      </div>
      <div v-if="ctx.edgeTooltipData.value.data?.pre_action" class="tooltip-row">
        <span class="tooltip-label">前置操作：</span>
        <span class="tooltip-value">{{ ctx.edgeTooltipData.value.data.pre_action }}</span>
      </div>
      <div v-if="ctx.edgeTooltipData.value.data?.note" class="tooltip-row">
        <span class="tooltip-label">备注：</span>
        <span class="tooltip-value">{{ ctx.edgeTooltipData.value.data.note }}</span>
      </div>
      <div
        v-if="
          !ctx.edgeTooltipData.value.data?.condition &&
          !ctx.edgeTooltipData.value.data?.trigger_action &&
          !ctx.edgeTooltipData.value.data?.pre_action &&
          !ctx.edgeTooltipData.value.data?.note
        "
        class="tooltip-row"
      >
        <span class="tooltip-value">普通跳转</span>
      </div>
      <div class="tooltip-label-text">{{ ctx.edgeTooltipData.value.label }}</div>
    </div>
  </transition>

  <transition name="play-fade">
    <div v-if="ctx.isPlaying.value" class="play-controls">
      <el-button size="small" @click="ctx.prevStep" :disabled="!ctx.hasPrevStep.value">
        <el-icon><ArrowLeft /></el-icon>上一步
      </el-button>
      <span class="play-step-info">{{ ctx.getStepInfo() }}</span>
      <span class="play-current-name">{{
        ctx.playPath.value[ctx.currentPlayIndex.value]?.screenName || ''
      }}</span>
      <el-button
        size="small"
        type="primary"
        @click="ctx.nextStep"
        :disabled="
          !ctx.hasNextStep.value && !ctx.playPath.value[ctx.currentPlayIndex.value]?.isBranchChoice
        "
      >
        下一步<el-icon><ArrowRight /></el-icon>
      </el-button>
      <el-button size="small" type="danger" @click="ctx.stopPlayback">
        <el-icon><Close /></el-icon>退出
      </el-button>
    </div>
  </transition>

  <el-dialog
    v-model="ctx.showBranchChoice.value"
    title="选择分支路径"
    width="360px"
    :close-on-click-modal="false"
  >
    <div class="branch-choices">
      <div
        v-for="branch in ctx.playPath.value[ctx.currentPlayIndex.value]?.branchOptions || []"
        :key="branch.edgeId"
        class="branch-option"
        @click="
          ctx.followBranch(branch.targetNodeId, ctx.vueFlowEdges.value, ctx.vueFlowNodes.value)
        "
      >
        <el-icon><Connection /></el-icon>
        <span>{{ branch.targetName }}</span>
        <el-icon><ArrowRight /></el-icon>
      </div>
      <div
        class="branch-option continue-main"
        @click="
          () => {
            ctx.showBranchChoice.value = false
            ctx.nextStep()
          }
        "
      >
        <el-icon><Guide /></el-icon>
        <span>继续主干流程</span>
        <el-icon><ArrowRight /></el-icon>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import {
  Edit,
  Delete,
  ArrowLeft,
  ArrowRight,
  Close,
  Connection,
  Guide,
} from '@element-plus/icons-vue'
import {
  useFlowSortEditor,
  FLOW_TYPE_TAG_MAP,
  FLOW_TYPE_LABEL_MAP,
} from '@/composables/flowSort/useFlowSortEditor'

const ctx = useFlowSortEditor()
</script>
