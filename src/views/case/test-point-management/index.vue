<template>
  <div class="test-point-page">
    <div class="page-hero">
      <div class="hero-copy">
        <div class="hero-kicker">Test Point Workspace</div>
        <h2 class="page-title">测试点管理</h2>
        <p class="page-subtitle">统一管理测试点，支持需求提取、XMind 导入并直接生成关联测试用例</p>
        <div class="hero-meta">
          <el-tag effect="dark" type="primary">主入口工作台</el-tag>
          <el-tag v-if="selectedProjectName" effect="plain" type="info"
            >当前项目：{{ selectedProjectName }}</el-tag
          >
          <el-tag v-if="selectedProjectId" effect="plain" type="success"
            >筛选结果：{{ total }}</el-tag
          >
        </div>
      </div>

      <div class="header-actions">
        <el-select
          v-model="selectedProjectId"
          class="project-select"
          placeholder="请选择项目"
          filterable
          @change="handleProjectChange"
        >
          <template #prefix>
            <el-icon><FolderOpened /></el-icon>
          </template>
          <el-option
            v-for="project in projects"
            :key="project.id"
            :label="project.name"
            :value="project.id"
          />
        </el-select>

        <div class="hero-action-group">
          <el-button :disabled="!selectedProjectId" @click="openTaskList">查看任务</el-button>
          <el-button :icon="MagicStick" :disabled="!selectedProjectId" @click="openExtractDialog"
            >从需求提取</el-button
          >
          <el-button :icon="Upload" :disabled="!selectedProjectId" @click="openXmindImportDialog"
            >导入 XMind</el-button
          >
          <el-button
            type="primary"
            :icon="Plus"
            :disabled="!selectedProjectId"
            @click="openCreateDialog"
            >新增测试点</el-button
          >
        </div>

        <el-button
          link
          type="primary"
          :disabled="!selectedProjectId"
          @click="openLegacyExtractGuide"
          >高级提取向导</el-button
        >
      </div>
    </div>

    <div class="workspace-card">
      <el-empty v-if="!selectedProjectId" description="请选择项目后查看测试点列表">
        <template #image>
          <div class="empty-illustration">
            <el-icon><DataAnalysis /></el-icon>
          </div>
        </template>
        <template #description>
          <div class="empty-description">
            <p>从这里开始统一管理测试点、提取需求结果和生成关联用例。</p>
            <p>先选择一个项目，再进行后续操作。</p>
          </div>
        </template>
      </el-empty>

      <template v-else>
        <div class="stats-cards">
          <button
            class="stat-card"
            :class="{ 'is-active': !filters.priority }"
            type="button"
            @click="applyPriorityFilter(undefined)"
          >
            <span class="stat-caption">全部测试点</span>
            <span class="stat-value">{{ statsTotal }}</span>
            <span class="stat-label">当前筛选范围内总数</span>
          </button>
          <button
            class="stat-card high"
            :class="{ 'is-active': filters.priority === 1 }"
            type="button"
            @click="applyPriorityFilter(1)"
          >
            <span class="stat-caption">高优先级</span>
            <span class="stat-value">{{ highCount }}</span>
            <span class="stat-label">点击快速筛选高优先级</span>
          </button>
          <button
            class="stat-card medium"
            :class="{ 'is-active': filters.priority === 2 }"
            type="button"
            @click="applyPriorityFilter(2)"
          >
            <span class="stat-caption">中优先级</span>
            <span class="stat-value">{{ mediumCount }}</span>
            <span class="stat-label">适合常规回归与覆盖补齐</span>
          </button>
          <button
            class="stat-card low"
            :class="{ 'is-active': filters.priority === 3 }"
            type="button"
            @click="applyPriorityFilter(3)"
          >
            <span class="stat-caption">低优先级</span>
            <span class="stat-value">{{ lowCount }}</span>
            <span class="stat-label">可作为补充储备任务</span>
          </button>
          <div class="stat-card generated non-clickable">
            <span class="stat-caption">已生成用例</span>
            <span class="stat-value">{{ generatedCaseCount }}</span>
            <span class="stat-label">已绑定到测试用例的累计数量</span>
          </div>
        </div>

        <el-card class="section-card filter-card" shadow="never">
          <div class="section-header">
            <div>
              <div class="section-title">筛选与定位</div>
              <div class="section-subtitle">
                快速收敛测试点范围，聚焦需要处理的模块、需求和负责人。
              </div>
            </div>
            <div class="section-actions">
              <el-button type="primary" :icon="Search" @click="fetchTestPoints">查询</el-button>
              <el-button :icon="RefreshRight" @click="resetFilters">重置</el-button>
            </div>
          </div>

          <el-form :model="filters" inline class="filter-form">
            <el-form-item label="模块"
              ><el-input v-model="filters.module" placeholder="模块名称" clearable
            /></el-form-item>
            <el-form-item label="优先级">
              <el-select v-model="filters.priority" placeholder="全部" clearable>
                <el-option label="高" :value="1" />
                <el-option label="中" :value="2" />
                <el-option label="低" :value="3" />
              </el-select>
            </el-form-item>
            <el-form-item label="需求">
              <el-select
                v-model="filters.requirement_id"
                placeholder="全部需求"
                clearable
                filterable
                class="requirement-select"
              >
                <el-option
                  v-for="item in requirementOptions"
                  :key="item.id"
                  :label="`${item.req_no} - ${item.title}`"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="创建人"
              ><el-input v-model="filters.created_by" placeholder="创建人" clearable
            /></el-form-item>
            <el-form-item label="创建时间">
              <el-date-picker
                v-model="dateRange"
                type="daterange"
                value-format="YYYY-MM-DD"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
              />
            </el-form-item>
            <el-form-item label="关键词"
              ><el-input
                v-model="filters.keyword"
                placeholder="搜索模块/功能/测试点"
                clearable
                @keyup.enter="fetchTestPoints"
            /></el-form-item>
          </el-form>
        </el-card>

        <el-card class="section-card table-card" shadow="never">
          <div class="section-header">
            <div>
              <div class="section-title">测试点列表</div>
              <div class="section-subtitle">
                支持批量处理、关联用例查看和单点生成，适合作为日常工作台。
              </div>
            </div>
            <div class="table-summary">
              <el-tag effect="plain" type="info">共 {{ total }} 条</el-tag>
              <el-tag v-if="selectedRows.length > 0" effect="plain" type="warning"
                >已选 {{ selectedRows.length }} 条</el-tag
              >
            </div>
          </div>

          <div v-if="selectedRows.length > 0" class="batch-actions">
            <el-tag type="warning">已选择 {{ selectedRows.length }} 条</el-tag>
            <div class="batch-action-buttons">
              <el-button type="danger" @click="handleBatchDelete">批量删除</el-button>
              <el-button type="success" @click="handleBatchGenerate">批量生成用例</el-button>
            </div>
          </div>

          <el-table
            class="management-table"
            :data="testPoints"
            border
            stripe
            row-key="id"
            v-loading="loading"
            @selection-change="handleSelectionChange"
            @sort-change="handleSortChange"
          >
            <el-table-column type="selection" width="48" />
            <el-table-column prop="module" label="模块" min-width="120" sortable="custom" />
            <el-table-column prop="point" label="测试点" min-width="320" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="point-cell">
                  <div class="point-text">{{ row.point }}</div>
                  <div class="point-meta">
                    <span>{{ row.module }}</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="100" sortable="custom">
              <template #default="{ row }"
                ><el-tag :type="priorityTagType(row.priority)">{{
                  priorityText(row.priority)
                }}</el-tag></template
              >
            </el-table-column>
            <el-table-column label="已生成用例数" width="130">
              <template #default="{ row }"
                ><el-link type="primary" @click="openCasesDialog(row)">{{
                  row.test_case_count ?? 0
                }}</el-link></template
              >
            </el-table-column>
            <el-table-column prop="created_by" label="创建人" width="120" />
            <el-table-column prop="create_time" label="创建时间" width="180" sortable="custom" />
            <el-table-column label="操作" width="340" fixed="right">
              <template #default="{ row }">
                <div class="action-group">
                  <el-button
                    class="table-action action-primary"
                    text
                    bg
                    @click="openCasesDialog(row)"
                    >查看用例</el-button
                  >
                  <el-button
                    class="table-action action-success"
                    text
                    bg
                    @click="handleGenerate(row)"
                    >生成用例</el-button
                  >
                  <el-button
                    class="table-action action-warning"
                    text
                    bg
                    @click="openEditDialog(row)"
                    >编辑</el-button
                  >
                  <el-button class="table-action action-danger" text bg @click="handleDelete(row)"
                    >删除</el-button
                  >
                </div>
              </template>
            </el-table-column>
            <template #empty>
              <div class="table-empty-state">
                <div class="table-empty-icon">
                  <el-icon><DataAnalysis /></el-icon>
                </div>
                <div class="table-empty-title">当前筛选下暂无测试点</div>
                <div class="table-empty-text">
                  可以直接从需求提取、导入 XMind，或手动新增第一条测试点。
                </div>
                <div class="table-empty-actions">
                  <el-button :icon="MagicStick" @click="openExtractDialog">从需求提取</el-button>
                  <el-button :icon="Upload" @click="openXmindImportDialog">导入 XMind</el-button>
                  <el-button type="primary" :icon="Plus" @click="openCreateDialog"
                    >新增测试点</el-button
                  >
                </div>
              </div>
            </template>
          </el-table>

          <div class="pagination">
            <el-pagination
              v-model:current-page="page"
              v-model:page-size="pageSize"
              :total="total"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              @current-change="fetchTestPoints"
              @size-change="handlePageSizeChange"
            />
          </div>
        </el-card>
      </template>
    </div>

    <TestPointFormDialog
      v-model="formDialogVisible"
      :project-id="selectedProjectId || 0"
      :editing-point="editingPoint"
      @success="fetchTestPoints"
    />
    <TestPointCasesDialog v-model="casesDialogVisible" :test-point="currentTestPoint" />
    <TestPointExtractDialog
      v-model:visible="extractDialogVisible"
      :project-id="selectedProjectId || 0"
      :initial-file-id="initialExtractFileId || undefined"
      @saved="handleIngestSaved"
    />
    <XmindImportDialog
      v-model:visible="xmindImportDialogVisible"
      :project-id="selectedProjectId || 0"
      @imported="handleIngestSaved"
    />

    <el-dialog
      v-model="generateDialogVisible"
      class="generate-status-dialog"
      title="生成测试用例进度"
      width="520px"
      :close-on-click-modal="false"
      :show-close="!generating"
    >
      <div class="generate-status-panel">
        <div class="generate-status-head">
          <div class="generate-status-icon">
            <el-icon><MagicStick /></el-icon>
          </div>
          <div>
            <div class="generate-status-title">
              {{ generating ? '正在处理测试点' : '生成流程已结束' }}
            </div>
            <div class="generate-status-subtitle">系统会自动刷新列表并同步最新的关联用例数量。</div>
          </div>
        </div>
        <el-progress :percentage="generateProgress" :status="progressStatus" />
        <p class="generate-message">{{ generateMessage }}</p>
      </div>
      <template #footer
        ><el-button :disabled="generating" type="primary" @click="generateDialogVisible = false"
          >关闭</el-button
        ></template
      >
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  DataAnalysis,
  FolderOpened,
  MagicStick,
  Plus,
  RefreshRight,
  Search,
  Upload,
} from '@element-plus/icons-vue'

import projectApi, { type Project } from '@/api/project'
import { testPointApi } from '@/api/testPoint'
import type {
  AnalysisProgress,
  TestPoint,
  TestPointListParams,
  TestPointListStats,
  TestPointRequirementOption,
} from '@/types/testPoint'
import XmindImportDialog from '@/components/xmind/XmindImportDialog.vue'
import TestPointExtractDialog from './TestPointExtractDialog.vue'
import TestPointCasesDialog from './TestPointCasesDialog.vue'
import TestPointFormDialog from './TestPointFormDialog.vue'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const generating = ref(false)
const generateDialogVisible = ref(false)
const generateProgress = ref(0)
const generateMessage = ref('')
const generateStatus = ref<'running' | 'success' | 'partial' | 'warning' | 'error'>('running')
const xmindImportDialogVisible = ref(false)
const extractDialogVisible = ref(false)
const initialExtractFileId = ref<number>(Number(route.query.file_id) || 0)
const hasConsumedInitialExtract = ref(false)

const projects = ref<Project[]>([])
const testPoints = ref<TestPoint[]>([])
const requirementOptions = ref<TestPointRequirementOption[]>([])
const selectedRows = ref<TestPoint[]>([])
const initialProjectId = Number(route.query.projectId || route.query.project_id)
const selectedProjectId = ref<number | undefined>(
  Number.isFinite(initialProjectId) && initialProjectId > 0 ? initialProjectId : undefined
)
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const dateRange = ref<string[]>([])
const formDialogVisible = ref(false)
const casesDialogVisible = ref(false)
const editingPoint = ref<TestPoint | null>(null)
const currentTestPoint = ref<TestPoint | null>(null)
const listStats = ref<TestPointListStats>({
  total: 0,
  high_priority_count: 0,
  medium_priority_count: 0,
  low_priority_count: 0,
  generated_case_count: 0,
})

const filters = reactive<TestPointListParams>({
  module: '',
  created_by: '',
  keyword: '',
  sort_by: 'create_time',
  sort_order: 'desc',
})

const highCount = computed(() => listStats.value.high_priority_count)
const mediumCount = computed(() => listStats.value.medium_priority_count)
const lowCount = computed(() => listStats.value.low_priority_count)
const statsTotal = computed(() => listStats.value.total)
const generatedCaseCount = computed(() => listStats.value.generated_case_count)
const selectedProjectName = computed(
  () => projects.value.find((project) => project.id === selectedProjectId.value)?.name || ''
)
const progressStatus = computed<'success' | 'warning' | 'exception' | undefined>(() => {
  if (generateStatus.value === 'success') return 'success'
  if (generateStatus.value === 'partial' || generateStatus.value === 'warning') return 'warning'
  if (generateStatus.value === 'error') return 'exception'
  return undefined
})

function createEmptyStats(): TestPointListStats {
  return {
    total: 0,
    high_priority_count: 0,
    medium_priority_count: 0,
    low_priority_count: 0,
    generated_case_count: 0,
  }
}

function priorityText(priority: number): string {
  return priority === 1 ? '高' : priority === 2 ? '中' : '低'
}
function priorityTagType(priority: number): 'danger' | 'warning' | 'info' {
  return priority === 1 ? 'danger' : priority === 2 ? 'warning' : 'info'
}
function isCancelError(error: unknown): boolean {
  return error === 'cancel' || error === 'close'
}

async function loadProjects(): Promise<void> {
  try {
    const response = await projectApi.getProjects({ page: 1, page_size: 100 })
    projects.value = response.data.items.filter((project) => project.name !== '默认项目')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载项目失败')
  }
}

async function fetchTestPoints(): Promise<void> {
  if (!selectedProjectId.value) {
    testPoints.value = []
    total.value = 0
    listStats.value = createEmptyStats()
    return
  }
  loading.value = true
  try {
    const response = await testPointApi.getList(selectedProjectId.value, {
      ...filters,
      created_from: dateRange.value[0],
      created_to: dateRange.value[1],
      page: page.value,
      page_size: pageSize.value,
    })
    testPoints.value = response.items
    total.value = response.total
    listStats.value = response.stats
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载测试点失败')
    testPoints.value = []
    total.value = 0
    listStats.value = createEmptyStats()
  } finally {
    loading.value = false
  }
}

async function refreshManagementData(): Promise<void> {
  if (!selectedProjectId.value) return
  await Promise.all([loadRequirementOptions(), fetchTestPoints()])
}

async function loadRequirementOptions(): Promise<void> {
  if (!selectedProjectId.value) {
    requirementOptions.value = []
    return
  }
  try {
    requirementOptions.value = await testPointApi.getRequirementOptions(selectedProjectId.value)
  } catch (error) {
    requirementOptions.value = []
    ElMessage.error(error instanceof Error ? error.message : '加载需求列表失败')
  }
}

function resetProjectScopedState(): void {
  page.value = 1
  total.value = 0
  testPoints.value = []
  selectedRows.value = []
  requirementOptions.value = []
  currentTestPoint.value = null
  listStats.value = createEmptyStats()
  filters.module = ''
  filters.priority = undefined
  filters.requirement_id = undefined
  filters.created_by = ''
  filters.keyword = ''
  filters.sort_by = 'create_time'
  filters.sort_order = 'desc'
  dateRange.value = []
}

async function handleProjectChange(): Promise<void> {
  resetProjectScopedState()
  if (!selectedProjectId.value) {
    return
  }
  await refreshManagementData()
  maybeOpenInitialExtractDialog()
}

function handleSelectionChange(rows: TestPoint[]): void {
  selectedRows.value = rows
}
function openCreateDialog(): void {
  editingPoint.value = null
  formDialogVisible.value = true
}
function openEditDialog(row: TestPoint): void {
  editingPoint.value = row
  formDialogVisible.value = true
}
function openCasesDialog(row: TestPoint): void {
  currentTestPoint.value = row
  casesDialogVisible.value = true
}
function applyPriorityFilter(priority?: number): void {
  filters.priority = priority
  page.value = 1
  void fetchTestPoints()
}
function openXmindImportDialog(): void {
  xmindImportDialogVisible.value = true
}
function openExtractDialog(): void {
  extractDialogVisible.value = true
}

function openLegacyExtractGuide(): void {
  // 旧向导页已下线，统一使用 ExtractDialog 入口
  openExtractDialog()
}

function openTaskList(): void {
  if (!selectedProjectId.value) return
  void router.push(`/home/task/list/${selectedProjectId.value}`)
}

async function handleIngestSaved(): Promise<void> {
  await refreshManagementData()
}

function maybeOpenInitialExtractDialog(): void {
  if (hasConsumedInitialExtract.value || !selectedProjectId.value) {
    return
  }
  const shouldOpen = route.query.openExtract === '1' || Boolean(route.query.file_id)
  if (!shouldOpen) {
    return
  }
  hasConsumedInitialExtract.value = true
  if (route.query.file_id) {
    initialExtractFileId.value = Number(route.query.file_id)
  }
  extractDialogVisible.value = true
}

function requireSelectedProjectId(): number | null {
  if (!selectedProjectId.value) {
    ElMessage.warning('请先选择项目')
    return null
  }

  return selectedProjectId.value
}

async function handleDelete(row: TestPoint): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除测试点“${row.point}”吗？`, '提示', { type: 'warning' })
    await testPointApi.delete(row.id, row.project_id)
    ElMessage.success('删除成功')
    await fetchTestPoints()
  } catch (error) {
    if (!isCancelError(error) && error instanceof Error && error.message) {
      ElMessage.error(error.message)
    }
  }
}

async function handleBatchDelete(): Promise<void> {
  const projectId = requireSelectedProjectId()
  if (!projectId) return

  try {
    await ElMessageBox.confirm('确定删除选中的测试点吗？', '提示', { type: 'warning' })
    await testPointApi.batchDelete(
      projectId,
      selectedRows.value.map((item) => item.id)
    )
    selectedRows.value = []
    ElMessage.success('批量删除成功')
    await fetchTestPoints()
  } catch (error) {
    if (!isCancelError(error) && error instanceof Error && error.message) {
      ElMessage.error(error.message)
    }
  }
}

async function startGenerate(testPointIds: number[]): Promise<void> {
  const projectId = requireSelectedProjectId()
  if (!projectId) return

  generateDialogVisible.value = true
  generating.value = true
  generateProgress.value = 0
  generateMessage.value = '准备开始生成...'
  generateStatus.value = 'running'
  try {
    const generator = await testPointApi.batchGenerateStream({
      project_id: projectId,
      test_point_ids: testPointIds,
    })
    for await (const progress of generator) {
      const streamProgress = progress as AnalysisProgress
      generateProgress.value = streamProgress.progress ?? generateProgress.value
      generateMessage.value = streamProgress.message ?? '生成中...'
      if (streamProgress.status === 'error') {
        generateStatus.value = 'error'
      } else if (streamProgress.status === 'partial') {
        generateStatus.value = 'partial'
      } else if (streamProgress.status === 'warning') {
        if (generateStatus.value === 'running') {
          generateStatus.value = 'warning'
        }
      } else if (streamProgress.status === 'success' || streamProgress.status === 'completed') {
        if (generateStatus.value === 'running') {
          generateStatus.value = 'success'
        }
      }
    }
    if (generateStatus.value === 'running') {
      generateStatus.value = 'success'
    }
    if (generateStatus.value === 'success') {
      ElMessage.success('测试用例生成完成')
    } else if (generateStatus.value === 'partial' || generateStatus.value === 'warning') {
      ElMessage.warning(generateMessage.value || '测试用例部分生成成功，请检查结果')
    }
    await fetchTestPoints()
  } catch (error) {
    generateStatus.value = 'error'
    generateMessage.value = error instanceof Error ? error.message : '生成失败'
    ElMessage.error(generateMessage.value)
  } finally {
    generating.value = false
  }
}

async function handleGenerate(row: TestPoint): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定为“${row.point}”生成测试用例吗？`, '提示', { type: 'warning' })
    await startGenerate([row.id])
  } catch (error) {
    if (!isCancelError(error) && error instanceof Error && error.message) {
      ElMessage.error(error.message)
    }
  }
}

async function handleBatchGenerate(): Promise<void> {
  try {
    await ElMessageBox.confirm('确定为选中的测试点批量生成测试用例吗？', '提示', {
      type: 'warning',
    })
    await startGenerate(selectedRows.value.map((item) => item.id))
  } catch (error) {
    if (!isCancelError(error) && error instanceof Error && error.message) {
      ElMessage.error(error.message)
    }
  }
}

function handleSortChange({
  prop,
  order,
}: {
  prop: string
  order: 'ascending' | 'descending' | null
}): void {
  filters.sort_by = (prop as TestPointListParams['sort_by']) || 'create_time'
  filters.sort_order = order === 'ascending' ? 'asc' : 'desc'
  void fetchTestPoints()
}

function handlePageSizeChange(size: number): void {
  pageSize.value = size
  page.value = 1
  void fetchTestPoints()
}

function resetFilters(): void {
  filters.module = ''
  filters.priority = undefined
  filters.requirement_id = undefined
  filters.created_by = ''
  filters.keyword = ''
  filters.sort_by = 'create_time'
  filters.sort_order = 'desc'
  dateRange.value = []
  page.value = 1
  void fetchTestPoints()
}

onMounted(async () => {
  await loadProjects()
  if (selectedProjectId.value) {
    await handleProjectChange()
  }
})
</script>

<style scoped>
.test-point-page {
  padding: 20px;
  background:
    radial-gradient(circle at top right, rgba(64, 158, 255, 0.12), transparent 24%),
    linear-gradient(180deg, #f7faff 0%, #f3f6fb 100%);
}

.page-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px;
  margin-bottom: 20px;
  background: linear-gradient(135deg, #ffffff 0%, #f7fbff 55%, #eef5ff 100%);
  border: 1px solid rgba(64, 158, 255, 0.12);
  border-radius: 24px;
  box-shadow: 0 14px 40px rgba(31, 45, 61, 0.08);
}

.hero-copy {
  min-width: 0;
}

.hero-kicker {
  margin-bottom: 10px;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #409eff;
  font-weight: 700;
}

.page-title {
  margin: 0;
  font-size: 30px;
  line-height: 1.2;
  color: #1f2d3d;
}

.page-subtitle {
  margin: 10px 0 0;
  max-width: 760px;
  color: #5f6b7a;
  line-height: 1.6;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}

.header-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  min-width: 420px;
}

.hero-action-group {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.project-select {
  width: 280px;
}

.workspace-card {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(220, 230, 241, 0.9);
  border-radius: 24px;
  box-shadow: 0 18px 48px rgba(31, 45, 61, 0.06);
}

.empty-illustration {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 110px;
  height: 110px;
  margin: 0 auto;
  border-radius: 50%;
  font-size: 52px;
  color: #409eff;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.16), rgba(103, 194, 58, 0.12));
}

.empty-description {
  color: #606266;
  line-height: 1.8;
}

.empty-description p {
  margin: 0;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px 18px 16px;
  text-align: left;
  background: linear-gradient(180deg, #ffffff 0%, #f7faff 100%);
  border: 1px solid rgba(220, 230, 241, 0.95);
  border-radius: 18px;
  box-shadow: 0 8px 24px rgba(31, 45, 61, 0.05);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

button.stat-card {
  width: 100%;
  cursor: pointer;
}

button.stat-card:hover,
.stat-card.is-active {
  transform: translateY(-2px);
  border-color: rgba(64, 158, 255, 0.4);
  box-shadow: 0 16px 30px rgba(64, 158, 255, 0.12);
}

.stat-card.high {
  background: linear-gradient(180deg, #fff7f7 0%, #fff0f0 100%);
}

.stat-card.medium {
  background: linear-gradient(180deg, #fffaf2 0%, #fdf4e5 100%);
}

.stat-card.low {
  background: linear-gradient(180deg, #f8f9fc 0%, #f2f4f8 100%);
}

.stat-card.generated {
  background: linear-gradient(180deg, #f4fff8 0%, #ebf8ef 100%);
}

.stat-card.non-clickable {
  cursor: default;
}

.stat-card.non-clickable:hover {
  transform: none;
  border-color: rgba(220, 230, 241, 0.95);
  box-shadow: 0 8px 24px rgba(31, 45, 61, 0.05);
}

.stat-caption {
  font-size: 13px;
  color: #7a8594;
  font-weight: 600;
}

.stat-value {
  font-size: 30px;
  line-height: 1.1;
  font-weight: 700;
  color: #1f2d3d;
}

.stat-label {
  color: #6b7684;
  font-size: 12px;
  line-height: 1.5;
}

.section-card {
  border: none;
  border-radius: 20px;
  box-shadow: 0 10px 28px rgba(31, 45, 61, 0.05);
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
}

.section-subtitle {
  margin-top: 6px;
  color: #7a8594;
  line-height: 1.5;
}

.section-actions,
.table-summary,
.batch-actions,
.batch-action-buttons,
.pagination {
  display: flex;
  align-items: center;
}

.section-actions,
.table-summary,
.batch-action-buttons {
  gap: 10px;
}

.filter-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 2px 12px;
  margin-bottom: 0;
}

:deep(.filter-form .el-form-item) {
  margin-right: 0;
  margin-bottom: 16px;
}

:deep(.filter-form .el-input),
:deep(.filter-form .el-select),
:deep(.filter-form .el-date-editor) {
  width: 100%;
}

.requirement-select {
  width: 100%;
}

.batch-actions {
  justify-content: space-between;
  padding: 14px 16px;
  margin-bottom: 16px;
  background: linear-gradient(90deg, rgba(250, 236, 216, 0.42), rgba(255, 250, 244, 0.8));
  border: 1px solid rgba(230, 162, 60, 0.18);
  border-radius: 16px;
}

.management-table :deep(.el-table__cell) {
  padding-top: 14px;
  padding-bottom: 14px;
}

.management-table :deep(.el-table__header th) {
  background: #f7faff;
  color: #4a5565;
  font-weight: 700;
}

.point-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.point-text {
  color: #1f2d3d;
  font-weight: 600;
  line-height: 1.5;
}

.point-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #7a8594;
}

.meta-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #c0c8d4;
}

.action-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.table-action {
  margin-left: 0;
  border-radius: 999px;
  font-weight: 600;
}

.action-primary {
  color: #409eff;
}

.action-success {
  color: #67c23a;
}

.action-warning {
  color: #e6a23c;
}

.action-danger {
  color: #f56c6c;
}

.table-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
  text-align: center;
}

.table-empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 84px;
  height: 84px;
  margin-bottom: 16px;
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.16), rgba(103, 194, 58, 0.14));
  color: #409eff;
  font-size: 36px;
}

.table-empty-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
}

.table-empty-text {
  max-width: 460px;
  margin-top: 8px;
  color: #7a8594;
  line-height: 1.6;
}

.table-empty-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 20px;
}

.generate-status-panel {
  padding: 4px 2px 8px;
}

.generate-status-head {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 20px;
}

.generate-status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.16), rgba(118, 75, 162, 0.14));
  color: #409eff;
  font-size: 22px;
}

.generate-status-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2d3d;
}

.generate-status-subtitle {
  margin-top: 4px;
  color: #7a8594;
  line-height: 1.5;
}

.pagination {
  justify-content: flex-end;
  margin-top: 18px;
}

.generate-message {
  margin: 16px 0 0;
  color: #606266;
  line-height: 1.6;
}

@media (max-width: 1280px) {
  .stats-cards {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .page-hero,
  .section-header,
  .batch-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    min-width: 0;
    align-items: stretch;
  }

  .hero-action-group {
    justify-content: flex-start;
  }

  .project-select {
    width: 100%;
  }

  .stats-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .table-summary,
  .section-actions,
  .batch-action-buttons,
  .table-empty-actions {
    flex-wrap: wrap;
  }
}

@media (max-width: 640px) {
  .test-point-page {
    padding: 12px;
  }

  .workspace-card,
  .page-hero {
    padding: 16px;
    border-radius: 18px;
  }

  .stats-cards {
    grid-template-columns: 1fr;
  }
}
</style>
