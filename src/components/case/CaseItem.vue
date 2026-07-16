<template>
  <el-card class="case-item case-card" :class="{ failed: caseItem.generate_status === 2 }">
    <template #header>
      <div class="case-header">
        <div class="case-info">
          <span class="case-no">{{ caseItem.case_no }}</span>
          <span
            class="case-priority"
            :class="{
              high: caseItem.priority === 1,
              medium: caseItem.priority === 2,
              low: caseItem.priority === 3,
            }"
          >
            {{ priorityText(caseItem.priority) }}
          </span>
          <el-tag
            v-if="lifecycleTag"
            :type="lifecycleTag.type"
            size="small"
            effect="dark"
            class="lifecycle-badge"
          >
            {{ lifecycleTag.label }}
          </el-tag>
        </div>
        <div class="case-status" :class="statusClass(caseItem.generate_status)">
          {{ statusText(caseItem.generate_status) }}
        </div>
      </div>
    </template>

    <div class="case-content">
      <h3 class="case-title">{{ caseItem.title }}</h3>
      <div class="case-meta">
        <span class="case-meta-item">
          <el-icon><Folder /></el-icon>
          {{ caseItem.module }}
        </span>
        <el-tag :type="caseTypeTagType" size="small" effect="plain" class="case-type-tag">
          {{ caseTypeLabel }}
        </el-tag>
        <span class="case-meta-item">
          <el-icon><Clock /></el-icon>
          {{ formatTime(caseItem.create_time) }}
        </span>
      </div>
      <div class="case-details">
        <div v-if="caseItem.precondition" class="case-section">
          <div class="section-header">
            <el-icon><Document /></el-icon>
            <span>前置条件</span>
          </div>
          <div class="section-content">
            <p>{{ caseItem.precondition }}</p>
          </div>
        </div>
        <div v-if="caseItem.steps && caseItem.steps.length > 0" class="case-section">
          <div class="section-header">
            <el-icon><List /></el-icon>
            <span>测试步骤</span>
          </div>
          <div class="section-content">
            <ul class="steps-list">
              <li v-for="(step, index) in caseItem.steps" :key="index">
                <span class="step-number">{{ step.step_number || step.step || index + 1 }}</span>
                <span class="step-content"
                  >{{ step.display_action || step.description || step.step || step.action
                  }}{{ step.param ? ` (${step.param})` : '' }}</span
                >
                <span v-if="(step as unknown as { expected?: string }).expected" class="step-expected"
                  >→ {{ (step as unknown as { expected?: string }).expected }}</span
                >
              </li>
            </ul>
          </div>
        </div>
        <div v-if="caseItem.expected_result" class="case-section">
          <div class="section-header">
            <el-icon><SuccessFilled /></el-icon>
            <span>预期结果</span>
          </div>
          <div class="section-content">
            <p>{{ caseItem.expected_result }}</p>
          </div>
        </div>
      </div>
    </div>

    <div class="case-actions">
      <el-button type="primary" size="small" @click="viewDetail">
        <el-icon><View /></el-icon>
        查看详情
      </el-button>
      <el-button type="info" size="small" @click="copyCase">
        <el-icon><DocumentCopy /></el-icon>
        复制用例
      </el-button>
      <el-button
        type="warning"
        size="small"
        v-if="caseItem.generate_status === 2"
        @click="retryGenerate"
      >
        <el-icon><Refresh /></el-icon>
        重试生成
      </el-button>
      <el-button type="danger" size="small" @click="deleteCase">
        <el-icon><Delete /></el-icon>
        删除
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import {
  Folder,
  Clock,
  Document,
  List,
  SuccessFilled,
  View,
  DocumentCopy,
  Refresh,
  Delete,
} from '@element-plus/icons-vue'
import type { TestCase } from '@/types/testCase'
import { useCaseItem } from './useCaseItem'

const props = defineProps<{
  caseItem: TestCase
}>()

const emit = defineEmits<{
  (e: 'viewDetail', caseId: number): void
  (e: 'copyCase', caseItem: TestCase): void
  (e: 'retryGenerate', caseId: number): void
  (e: 'deleteCase', caseId: number): void
}>()

const {
  lifecycleTag,
  caseTypeLabel,
  caseTypeTagType,
  priorityText,
  statusText,
  statusClass,
  formatTime,
} = useCaseItem(props)

const viewDetail = () => {
  emit('viewDetail', props.caseItem.id)
}
const copyCase = () => {
  emit('copyCase', props.caseItem)
}
const retryGenerate = () => {
  emit('retryGenerate', props.caseItem.id)
}
const deleteCase = () => {
  emit('deleteCase', props.caseItem.id)
}
</script>

<style lang="scss">
@use './CaseItem.scss';
</style>
