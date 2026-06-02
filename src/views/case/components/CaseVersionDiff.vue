<template>
  <div class="case-version-diff">
    <!-- 普通字段变更 -->
    <el-descriptions
      v-if="Object.keys(diffData).length > 0"
      title="字段变更"
      :column="3"
      border
      class="diff-section"
    >
      <el-descriptions-item
        v-for="(change, field) in diffData"
        :key="field"
        :label="fieldLabelMap[field] ?? field"
        :label-class-name="getLabelClass(change.changeType)"
      >
        <div class="diff-values">
          <span class="diff-old" :class="getOldValueClass(change.changeType)">
            {{ formatValue(change.old) }}
          </span>
          <el-icon class="diff-arrow"><ArrowRight /></el-icon>
          <span class="diff-new" :class="getNewValueClass(change.changeType)">
            {{ formatValue(change.new) }}
          </span>
        </div>
        <el-tag
          :type="changeTagType(change.changeType)"
          size="small"
          class="diff-tag"
        >
          {{ changeTagLabel(change.changeType) }}
        </el-tag>
      </el-descriptions-item>
    </el-descriptions>

    <!-- 步骤变更 -->
    <div v-if="stepsDiff.length > 0" class="diff-section">
      <h4 class="section-title">步骤变更</h4>
      <div
        v-for="step in stepsDiff"
        :key="step.stepNumber"
        class="step-diff-card"
      >
        <div class="step-diff-header">
          <el-tag type="info" size="small">步骤 {{ step.stepNumber }}</el-tag>
        </div>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item
            v-for="(change, field) in step.fields"
            :key="field"
            :label="stepFieldLabelMap[field] ?? field"
            :label-class-name="getLabelClass(change.changeType)"
          >
            <div class="diff-values">
              <span class="diff-old" :class="getOldValueClass(change.changeType)">
                {{ formatValue(change.old) }}
              </span>
              <el-icon class="diff-arrow"><ArrowRight /></el-icon>
              <span class="diff-new" :class="getNewValueClass(change.changeType)">
                {{ formatValue(change.new) }}
              </span>
            </div>
            <el-tag
              :type="changeTagType(change.changeType)"
              size="small"
              class="diff-tag"
            >
              {{ changeTagLabel(change.changeType) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>

    <!-- 无变更 -->
    <el-empty
      v-if="Object.keys(diffData).length === 0 && stepsDiff.length === 0"
      description="两个版本之间无差异"
    />
  </div>
</template>

<script setup lang="ts">
import { ArrowRight } from '@element-plus/icons-vue'
import type { FieldDiff, StepDiff } from '@/api/case/types'

defineProps<{
  /** 普通字段变更映射 */
  diffData: Record<string, FieldDiff>
  /** 步骤级变更列表 */
  stepsDiff: StepDiff[]
}>()

/** 字段名中文映射 */
const fieldLabelMap: Record<string, string> = {
  title: '标题',
  module: '模块',
  precondition: '前置条件',
  expected_result: '预期结果',
  priority: '优先级',
  case_type: '用例类型',
  test_category: '测试分类',
  exec_script: '执行脚本',
  lifecycle_status: '生命周期状态',
}

/** 步骤字段名中文映射 */
const stepFieldLabelMap: Record<string, string> = {
  action: '操作',
  expected_result: '预期结果',
  param: '参数',
  description: '描述',
  display_action: '展示操作',
  input_value: '输入值',
  target_element: '目标元素',
  action_type: '操作类型',
}

/** 格式化显示值：null/undefined/空字符串统一展示为 '-' */
const formatValue = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

/** 变更类型对应的标签类型 */
const changeTagType = (changeType: FieldDiff['changeType']): 'success' | 'danger' | 'warning' => {
  const map: Record<FieldDiff['changeType'], 'success' | 'danger' | 'warning'> = {
    added: 'success',
    deleted: 'danger',
    modified: 'warning',
  }
  return map[changeType] ?? 'warning'
}

/** 变更类型对应的中文标签 */
const changeTagLabel = (changeType: FieldDiff['changeType']): string => {
  const map: Record<FieldDiff['changeType'], string> = {
    added: '新增',
    deleted: '删除',
    modified: '修改',
  }
  return map[changeType] ?? '修改'
}

/** 描述项 label 的 CSS 类名 */
const getLabelClass = (changeType: FieldDiff['changeType']): string => {
  return `diff-label-${changeType}`
}

/** 旧值 CSS 类名 */
const getOldValueClass = (changeType: FieldDiff['changeType']): string => {
  if (changeType === 'added') return 'value-added-bg'
  if (changeType === 'deleted') return 'value-deleted-bg'
  return 'value-modified-bg'
}

/** 新值 CSS 类名 */
const getNewValueClass = (changeType: FieldDiff['changeType']): string => {
  if (changeType === 'added') return 'value-added-bg'
  if (changeType === 'deleted') return 'value-deleted-bg'
  return 'value-modified-bg'
}
</script>

<style scoped>
.case-version-diff {
  padding: 8px 0;
}

.diff-section {
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.step-diff-card {
  margin-bottom: 16px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
}

.step-diff-header {
  margin-bottom: 8px;
}

.diff-values {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.diff-old,
.diff-new {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 13px;
  max-width: 300px;
  word-break: break-all;
  white-space: pre-wrap;
}

.diff-arrow {
  color: #909399;
  flex-shrink: 0;
}

.diff-tag {
  margin-left: 8px;
}

/* 变更高亮色 */
.value-added-bg {
  background-color: #f0f9eb;
  color: #67c23a;
  border: 1px solid #c2e7b0;
}

.value-deleted-bg {
  background-color: #fef0f0;
  color: #f56c6c;
  border: 1px solid #fbc4c4;
}

.value-modified-bg {
  background-color: #fdf6ec;
  color: #e6a23c;
  border: 1px solid #f5dab1;
}

/* label 列高亮 */
:deep(.diff-label-added) {
  background-color: #f0f9eb !important;
}

:deep(.diff-label-deleted) {
  background-color: #fef0f0 !important;
}

:deep(.diff-label-modified) {
  background-color: #fdf6ec !important;
}
</style>
