<template>
  <!-- 用例卡片渲染子组件：抽取自 smart-generate.vue 预览列表，保持主文件单文件行数可控 -->
  <div>
    <div class="case-header">
      <el-checkbox v-model="caseData.selected_for_save" @change="$emit('toggle-select')" />
      <span class="case-title">{{ caseData.title }}</span>
      <el-tag :type="qualityTagType(caseData.quality_status)" size="small">{{
        qualityLabel(caseData.quality_status)
      }}</el-tag>
      <el-tag size="small" type="info">{{ caseData.case_type }}</el-tag>
      <el-tag v-if="caseData.dirty" size="small" type="warning">已编辑</el-tag>
      <el-tag v-if="caseData.regenerating" size="small" type="info">重新生成中...</el-tag>
      <div class="case-actions">
        <el-button size="small" text type="primary" @click="$emit('edit', caseData)"
          >编辑</el-button
        >
        <el-button
          size="small"
          text
          type="primary"
          :loading="caseData.regenerating"
          @click="$emit('regenerate', caseData.client_id)"
          >重新生成</el-button
        >
        <el-button size="small" text type="danger" @click="$emit('remove', caseData.client_id)"
          >删除</el-button
        >
      </div>
    </div>
    <el-descriptions :column="2" size="small" class="case-detail">
      <el-descriptions-item label="模块">{{ caseData.module || '-' }}</el-descriptions-item>
      <el-descriptions-item label="优先级">{{
        priorityLabel(caseData.priority)
      }}</el-descriptions-item>
      <el-descriptions-item label="前置条件" :span="2">{{
        caseData.precondition || '无'
      }}</el-descriptions-item>
      <el-descriptions-item label="步骤" :span="2">
        <ol class="step-list">
          <li v-for="(s, i) in caseData.steps" :key="i">{{ stepText(s) }}</li>
        </ol>
      </el-descriptions-item>
      <el-descriptions-item label="预期结果" :span="2">{{
        caseData.expected_result
      }}</el-descriptions-item>
      <el-descriptions-item
        v-if="caseData.source_refs && Object.keys(caseData.source_refs).length > 0"
        label="来源依据"
        :span="2"
      >
        <span v-if="caseData.source_refs.ui_screen_name" class="source-ref-item"
          ><el-tag size="small" type="success"
            >UI: {{ caseData.source_refs.ui_screen_name }}</el-tag
          ></span
        >
        <span v-if="caseData.source_refs.requirement_file_name" class="source-ref-item"
          ><el-tag size="small"
            >需求: {{ caseData.source_refs.requirement_file_name }}</el-tag
          ></span
        >
        <span v-if="caseData.source_refs.test_point_name" class="source-ref-item"
          ><el-tag size="small" type="info"
            >测试点: {{ caseData.source_refs.test_point_name }}</el-tag
          ></span
        >
      </el-descriptions-item>
    </el-descriptions>
  </div>
</template>

<script setup lang="ts">
import type { QualityStatus, SmartPreviewCase } from '@/store/smartGeneration'

/** 用例卡片渲染子组件，统一处理普通列表与虚拟滚动列表的卡片样式 */
const props = defineProps<{
  /** 待渲染的用例数据 */
  c: SmartPreviewCase
}>()

// 解构为非响应式引用会让 v-model 失效，这里保留 caseData 别名供模板使用
const caseData = props.c

function qualityTagType(s: QualityStatus): 'success' | 'warning' | 'info' | 'danger' {
  return (
    (
      { passed: 'success', warning: 'warning', pending_review: 'info', rejected: 'danger' } as const
    )[s] || 'info'
  )
}
function qualityLabel(s: QualityStatus) {
  return (
    (
      {
        passed: '通过',
        warning: '有轻微问题',
        pending_review: '需要确认',
        rejected: '不建议保存',
      } as const
    )[s] || s
  )
}
function priorityLabel(p: number) {
  return ({ 1: '高', 2: '中', 3: '低' } as const)[p] || '中'
}

/** 提取步骤文本：优先 action 字段，回退 step 字段，避免模板内 as 断言导致 prettier 解析失败 */
function stepText(s: Record<string, unknown>): string {
  const action = s.action
  const step = s.step
  if (typeof action === 'string' && action) return action
  if (typeof step === 'string' && step) return step
  if (step != null) return String(step)
  return ''
}

defineEmits<{
  (e: 'edit', c: SmartPreviewCase): void
  (e: 'regenerate', clientId: string): void
  (e: 'remove', clientId: string): void
  (e: 'toggle-select'): void
}>()
</script>

<style scoped>
.case-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.case-title {
  font-weight: 600;
  flex: 1;
  min-width: 120px;
}
.case-actions {
  margin-left: auto;
  white-space: nowrap;
}
.case-detail {
  margin-top: 8px;
}
.step-list {
  margin: 0;
  padding-left: 16px;
}
.step-list li {
  line-height: 1.8;
}
.source-ref-item {
  margin-right: 8px;
}
</style>
