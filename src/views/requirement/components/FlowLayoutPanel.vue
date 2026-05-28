<template>
  <el-collapse-item name="flows" v-if="hasFlowData">
    <template #title>
      <div class="collapse-title">
        <el-icon><Guide /></el-icon>
        <span>跳转流程</span>
      </div>
    </template>
    <div class="flows-content">
      <div v-if="flows?.length" class="flow-list">
        <div v-for="(flow, index) in flows" :key="index" class="flow-item">
          <span class="flow-from">{{ flow.from }}</span>
          <el-icon><Right /></el-icon>
          <span class="flow-to">{{ flow.to }}</span>
          <el-tag v-if="flow.trigger" size="small" type="info">{{ flow.trigger }}</el-tag>
        </div>
      </div>
      <div v-if="navigation?.length" class="navigation-list">
        <div v-for="(nav, index) in navigation" :key="index" class="nav-item">
          <span class="nav-screen">{{ nav.screen }}</span>
          <span class="nav-actions" v-if="nav.actions?.length">
            操作: {{ nav.actions.join(', ') }}
          </span>
        </div>
      </div>
    </div>
  </el-collapse-item>

  <el-collapse-item name="layout" v-if="layoutConstraints?.length">
    <template #title>
      <div class="collapse-title">
        <el-icon><Setting /></el-icon>
        <span>布局约束</span>
      </div>
    </template>
    <div class="constraints-list">
      <div v-for="(constraint, index) in layoutConstraints" :key="index" class="constraint-item">
        <el-tag :type="getPriorityColor(constraint.priority)" size="small" class="priority-tag">
          {{ constraint.priority }}
        </el-tag>
        <span class="constraint-text">{{ constraint.constraint }}</span>
        <span v-if="constraint.target" class="constraint-target"
          >目标: {{ constraint.target }}</span
        >
      </div>
    </div>
  </el-collapse-item>

  <el-collapse-item name="visual" v-if="visualStyle">
    <template #title>
      <div class="collapse-title">
        <el-icon><Brush /></el-icon>
        <span>视觉风格</span>
      </div>
    </template>
    <div class="visual-style-content">
      <div v-if="visualStyle.background_color" class="style-item">
        <span class="style-label">背景色</span>
        <span class="style-value">
          <span
            class="color-swatch"
            :style="{ backgroundColor: visualStyle.background_color }"
          ></span>
          {{ visualStyle.background_color }}
        </span>
      </div>
      <div v-if="visualStyle.theme_color" class="style-item">
        <span class="style-label">主题色</span>
        <span class="style-value">
          <span class="color-swatch" :style="{ backgroundColor: visualStyle.theme_color }"></span>
          {{ visualStyle.theme_color }}
        </span>
      </div>
      <div v-if="visualStyle.border_radius_style" class="style-item">
        <span class="style-label">圆角风格</span>
        <span class="style-value">{{ visualStyle.border_radius_style }}</span>
      </div>
      <div v-if="visualStyle.shadow_style" class="style-item">
        <span class="style-label">阴影风格</span>
        <span class="style-value">{{ visualStyle.shadow_style }}</span>
      </div>
    </div>
  </el-collapse-item>

  <el-collapse-item name="warnings" v-if="warnings?.length">
    <template #title>
      <div class="collapse-title">
        <el-icon><WarningFilled /></el-icon>
        <span>警告信息</span>
        <el-tag size="small" type="danger">{{ warnings.length }}条</el-tag>
      </div>
    </template>
    <div class="warnings-list">
      <el-alert
        v-for="(warning, index) in warnings"
        :key="index"
        :title="warning"
        type="warning"
        :closable="false"
        show-icon
        class="warning-item"
      />
    </div>
  </el-collapse-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Guide, Right, Setting, Brush, WarningFilled } from '@element-plus/icons-vue'
import type { UILayoutConstraint, UIVisualStyle } from '@/api/uiPrototype'
import type { TagType } from '@/types/element-plus'

const props = defineProps<{
  flows?: Array<{ from: string; to: string; trigger?: string }>
  navigation?: Array<{ screen: string; actions?: string[] }>
  layoutConstraints?: UILayoutConstraint[]
  visualStyle?: UIVisualStyle
  warnings?: string[]
}>()

const hasFlowData = computed(() => {
  return !!(props.flows?.length || props.navigation?.length)
})

const getPriorityColor = (priority: string): TagType => {
  const colorMap: Record<string, TagType> = {
    high: 'danger',
    medium: 'warning',
    low: 'info',
  }
  return colorMap[priority] || 'info'
}
</script>

<style scoped>
.collapse-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.flows-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.flow-list,
.navigation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.flow-item,
.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 10px;
  font-size: 13px;
  flex-wrap: wrap;
}

.flow-from,
.flow-to,
.nav-screen {
  color: #303133;
  font-weight: 500;
}

.nav-actions {
  color: #909399;
  margin-left: auto;
}

.constraints-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.constraint-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 10px;
  font-size: 13px;
  flex-wrap: wrap;
}

.priority-tag {
  text-transform: uppercase;
  font-size: 10px;
}

.constraint-text {
  color: #303133;
}

.constraint-target {
  color: #909399;
  margin-left: auto;
}

.visual-style-content {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.style-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 10px;
  font-size: 13px;
  flex-wrap: wrap;
}

.style-label {
  color: #909399;
}

.style-value {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #303133;
}

.color-swatch {
  display: inline-block;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
}

.warnings-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.warning-item {
  margin-bottom: 0;
}

@media (max-width: 768px) {
  .nav-actions,
  .constraint-target {
    margin-left: 0;
    width: 100%;
  }

  .visual-style-content {
    grid-template-columns: 1fr;
  }
}
</style>
