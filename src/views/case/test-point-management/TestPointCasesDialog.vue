<template>
  <el-dialog
    :model-value="modelValue"
    :title="dialogTitle"
    class="test-point-cases-dialog"
    width="900px"
    @close="emit('update:modelValue', false)"
  >
    <div class="dialog-hero">
      <div class="hero-title">查看当前测试点关联的测试用例</div>
      <div class="hero-meta">
        <el-tag effect="plain" type="info">共 {{ total }} 条</el-tag>
        <el-tag v-if="props.testPoint?.module" effect="plain">{{ props.testPoint?.module }}</el-tag>
      </div>
    </div>

    <el-table class="cases-table" :data="cases" v-loading="loading" border stripe>
      <el-table-column prop="case_no" label="用例编号" width="180" />
      <el-table-column prop="title" label="用例标题" min-width="260" show-overflow-tooltip />
      <el-table-column prop="module" label="模块" width="140" />
      <el-table-column prop="priority" label="优先级" width="100">
        <template #default="{ row }">
          <el-tag :type="priorityTagType(row.priority)">
            {{ priorityText(row.priority) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="case_type" label="类型" width="140" />
      <el-table-column prop="create_time" label="创建时间" width="180" />
      <template #empty>
        <div class="cases-empty-state">
          <div class="empty-title">当前测试点还没有关联用例</div>
          <div class="empty-text">可以回到列表中点击“生成用例”，系统会自动把结果绑定回来。</div>
        </div>
      </template>
    </el-table>
    <div class="pagination">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="loadCases"
        @size-change="handleSizeChange"
      />
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { testPointApi } from '@/api/testPoint'
import type { RelatedTestCase, TestPoint } from '@/types/testPoint'

const props = defineProps<{
  modelValue: boolean
  testPoint: TestPoint | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const loading = ref(false)
const cases = ref<RelatedTestCase[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const dialogTitle = computed(() => `关联用例 - ${props.testPoint?.point ?? ''}`)

function priorityText(priority: number): string {
  if (priority === 1) return '高'
  if (priority === 2) return '中'
  return '低'
}

function priorityTagType(priority: number): 'danger' | 'warning' | 'info' {
  if (priority === 1) return 'danger'
  if (priority === 2) return 'warning'
  return 'info'
}

async function loadCases(): Promise<void> {
  if (!props.testPoint) {
    return
  }
  loading.value = true
  try {
    const response = await testPointApi.getRelatedCases(
      props.testPoint.id,
      props.testPoint.project_id,
      page.value,
      pageSize.value
    )
    cases.value = response.items
    total.value = response.total
  } catch (error) {
    const message = error instanceof Error ? error.message : '获取关联用例失败'
    ElMessage.error(message)
    cases.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSizeChange(size: number): void {
  pageSize.value = size
  page.value = 1
  void loadCases()
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible && props.testPoint) {
      page.value = 1
      void loadCases()
    }
  }
)
</script>

<style scoped>
.dialog-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  margin-bottom: 18px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.12), rgba(103, 194, 58, 0.08));
  border-radius: 18px;
}

.hero-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2d3d;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cases-table :deep(.el-table__header th) {
  background: #f7faff;
  color: #4a5565;
  font-weight: 700;
}

.cases-empty-state {
  padding: 36px 12px;
  text-align: center;
}

.empty-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2d3d;
}

.empty-text {
  margin-top: 8px;
  color: #7a8594;
  line-height: 1.6;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.test-point-cases-dialog :deep(.el-dialog) {
  border-radius: 24px;
  overflow: hidden;
}
</style>
