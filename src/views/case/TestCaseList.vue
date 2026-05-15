<template>
  <div class="test-case-list">
    <el-card class="main-card">
      <!-- 页面标题 -->
      <div class="page-header">
        <div class="header-left">
          <h2 class="page-title">测试用例列表</h2>
          <span class="case-count" v-if="filteredTestCases.length > 0">
            共 {{ filteredTestCases.length }} 条
          </span>
        </div>
        <div class="header-right">
          <!-- 批量操作按钮 -->
          <template v-if="selectedCases.length > 0">
            <el-tag type="warning" class="batch-tag"> 已选择 {{ selectedCases.length }} 条 </el-tag>
            <el-button type="danger" :icon="Delete" @click="handleBatchDelete">
              批量删除
            </el-button>
            <el-button @click="clearSelection"> 取消选择 </el-button>
          </template>
          <!-- 撤销删除按钮 -->
          <el-button
            v-if="recentlyDeletedIds.length > 0"
            type="warning"
            :icon="RefreshRight"
            @click="handleUndoDelete"
          >
            撤销删除 ({{ recentlyDeletedIds.length }})
          </el-button>
          <el-button
            v-if="selectedProjectId || route.params.projectId"
            type="primary"
            :icon="Plus"
            @click="goToAIGenerate"
          >
            AI生成用例
          </el-button>
          <el-dropdown
            v-if="selectedProjectId || route.params.projectId"
            :disabled="exporting || filteredTestCases.length === 0"
          >
            <el-button :loading="exporting">
              <el-icon><Download /></el-icon>
              导出
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleExportAll">
                  导出全部 ({{ filteredTestCases.length }})
                </el-dropdown-item>
                <el-dropdown-item
                  :disabled="selectedCases.length === 0"
                  @click="handleExportSelected"
                >
                  导出选中 ({{ selectedCases.length }})
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <!-- 视图切换 -->
          <el-button-group class="view-toggle">
            <el-button
              :type="viewMode === 'list' ? 'primary' : ''"
              :icon="List"
              @click="viewMode = 'list'"
              title="列表视图"
            />
            <el-button
              :type="viewMode === 'grid' ? 'primary' : ''"
              :icon="Grid"
              @click="viewMode = 'grid'"
              title="网格视图"
            />
          </el-button-group>
        </div>
      </div>

      <!-- 未选择项目提示 -->
      <div v-if="!selectedProjectId && !route.params.projectId" class="empty-state">
        <el-empty description="请先选择项目">
          <template #image>
            <el-icon :size="80" color="#dcdfe6"><FolderOpened /></el-icon>
          </template>
          <p class="empty-hint">选择项目后即可查看测试用例</p>
          <div class="empty-actions" v-if="projectList.length > 0">
            <el-select
              v-model="selectedProjectId"
              placeholder="请选择项目"
              class="project-select"
              filterable
              @change="handleProjectChange"
            >
              <el-option
                v-for="project in projectList"
                :key="project.id"
                :label="project.name"
                :value="project.id"
              />
            </el-select>
          </div>
        </el-empty>
      </div>

      <!-- 统计数据区域 -->
      <div v-else class="stats-section" v-loading="loading">
        <div class="stats-cards">
          <div class="stat-card stat-total" @click="applyStatsCardFilter(null)">
            <div class="stat-icon">
              <el-icon><Document /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ filteredTestCases.length }}</span>
              <span class="stat-label">全部用例</span>
            </div>
          </div>
          <div class="stat-card stat-success" @click="applyStatsCardFilter('')">
            <div class="stat-icon">
              <el-icon><SuccessFilled /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ successCount }}</span>
              <span class="stat-label">生成成功</span>
            </div>
          </div>
          <div class="stat-card stat-failed" @click="applyStatsCardFilter('')">
            <div class="stat-icon">
              <el-icon><CircleCloseFilled /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ failedCount }}</span>
              <span class="stat-label">生成失败</span>
            </div>
          </div>
          <div class="stat-card stat-manual" @click="applyStatsCardFilter('manual')">
            <div class="stat-icon">
              <el-icon><Edit /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ manualCount }}</span>
              <span class="stat-label">手工测试</span>
            </div>
          </div>
          <div class="stat-card stat-ui" @click="applyStatsCardFilter('ui_automation')">
            <div class="stat-icon">
              <el-icon><Monitor /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ uiCount }}</span>
              <span class="stat-label">UI自动化</span>
            </div>
          </div>
          <div class="stat-card stat-api" @click="applyStatsCardFilter('api_automation')">
            <div class="stat-icon">
              <el-icon><Connection /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ apiCount }}</span>
              <span class="stat-label">API自动化</span>
            </div>
          </div>
        </div>
        <!-- 优先级分布 -->
        <div class="priority-distribution">
          <span class="priority-label">优先级分布：</span>
          <div class="priority-bar">
            <div
              class="priority-segment high"
              :style="{
                width: (highPriorityCount / Math.max(filteredTestCases.length, 1)) * 100 + '%',
              }"
            >
              <span v-if="highPriorityCount > 0">P0 {{ highPriorityCount }}</span>
            </div>
            <div
              class="priority-segment medium"
              :style="{
                width: (mediumPriorityCount / Math.max(filteredTestCases.length, 1)) * 100 + '%',
              }"
            >
              <span v-if="mediumPriorityCount > 0">P2 {{ mediumPriorityCount }}</span>
            </div>
            <div
              class="priority-segment low"
              :style="{
                width: (lowPriorityCount / Math.max(filteredTestCases.length, 1)) * 100 + '%',
              }"
            >
              <span v-if="lowPriorityCount > 0">P3 {{ lowPriorityCount }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 筛选区域 -->
      <div v-if="selectedProjectId || route.params.projectId" class="filter-section">
        <div class="filter-header" @click="filterExpanded = !filterExpanded">
          <span class="filter-title">
            <el-icon><Filter /></el-icon>
            筛选条件
            <el-tag v-if="hasActiveFilter" type="primary" size="small" class="filter-active-tag">
              已设置筛选
            </el-tag>
          </span>
          <el-button link type="primary">
            {{ filterExpanded ? '收起' : '展开' }}
            <el-icon>
              <ArrowUp v-if="filterExpanded" />
              <ArrowDown v-else />
            </el-icon>
          </el-button>
        </div>
        <div class="filter-content" v-show="filterExpanded">
          <div class="filter-row">
            <div class="filter-item">
              <span class="filter-label">项目</span>
              <el-select
                v-model="selectedProjectId"
                placeholder="请选择项目"
                class="filter-select"
                filterable
                clearable
                @change="handleProjectChange"
              >
                <el-option
                  v-for="project in projectList"
                  :key="project.id"
                  :label="project.name"
                  :value="project.id"
                />
              </el-select>
            </div>
            <div class="filter-item">
              <span class="filter-label">需求文档</span>
              <el-select
                v-model="selectedRequirementFileId"
                placeholder="全部需求"
                class="filter-select"
                filterable
                clearable
                :disabled="!selectedProjectId || requirementFileList.length === 0"
                @change="handleRequirementFileChange"
              >
                <el-option
                  v-for="file in requirementFileList"
                  :key="file.id"
                  :label="file.file_name"
                  :value="file.id"
                />
              </el-select>
            </div>
            <div class="filter-item">
              <span class="filter-label">模块</span>
              <el-select
                v-model="filter.module"
                placeholder="全部模块"
                class="filter-select"
                filterable
                clearable
                :disabled="filteredTestCases.length === 0"
                @change="handleFilterChange"
              >
                <el-option
                  v-for="module in modules"
                  :key="module"
                  :label="module"
                  :value="module"
                />
              </el-select>
            </div>
            <div class="filter-item">
              <span class="filter-label">优先级</span>
              <el-select
                v-model="filter.priority"
                placeholder="全部优先级"
                class="filter-select"
                clearable
                :disabled="filteredTestCases.length === 0"
                @change="handleFilterChange"
              >
                <el-option label="高(P0)" :value="1" />
                <el-option label="中(P2)" :value="2" />
                <el-option label="低(P3)" :value="3" />
              </el-select>
            </div>
          </div>
          <div class="filter-row">
            <div class="filter-item">
              <span class="filter-label">生命周期</span>
              <el-select
                v-model="filter.lifecycle_status"
                placeholder="全部状态"
                class="filter-select"
                clearable
                multiple
                collapse-tags
                collapse-tags-tooltip
                :disabled="filteredTestCases.length === 0"
                @change="handleFilterChange"
              >
                <el-option label="草稿" value="draft" />
                <el-option label="可用" value="active" />
                <el-option label="评审中" value="pending_review" />
                <el-option label="待修改" value="needs_modify" />
                <el-option label="待重录" value="locator_broken" />
                <el-option label="已弃用" value="deprecated" />
              </el-select>
            </div>
            <div class="filter-item">
              <span class="filter-label">用例类型</span>
              <el-select
                v-model="filter.case_type"
                placeholder="全部类型"
                class="filter-select"
                clearable
                :disabled="filteredTestCases.length === 0"
                @change="handleFilterChange"
              >
                <el-option label="UI自动化" value="ui_automation" />
                <el-option label="手工测试" value="manual" />
                <el-option label="API自动化" value="api_automation" />
                <el-option label="性能测试" value="performance" />
                <el-option label="安全测试" value="security" />
              </el-select>
            </div>
            <div class="filter-item filter-search">
              <el-input
                v-model="filter.keyword"
                placeholder="搜索用例标题、编号..."
                clearable
                :disabled="filteredTestCases.length === 0"
                @keyup.enter="handleFilterChange"
                @clear="handleFilterChange"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </div>
            <el-button
              type="primary"
              :icon="Search"
              :disabled="filteredTestCases.length === 0"
              @click="handleFilterChange"
            >
              搜索
            </el-button>
            <el-button :icon="RefreshRight" :disabled="!hasActiveFilter" @click="resetFilter">
              重置
            </el-button>
          </div>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading && (selectedProjectId || route.params.projectId)" class="loading-state">
        <el-skeleton :rows="5" animated />
      </div>

      <!-- 测试用例列表 -->
      <div v-if="!loading && (selectedProjectId || route.params.projectId)" class="case-list">
        <el-empty v-if="paginatedTestCases.length === 0" description="暂无测试用例">
          <template #image>
            <el-icon :size="80" color="#dcdfe6"><Document /></el-icon>
          </template>
          <p class="empty-hint">该项目下还没有测试用例，点击右上角"AI生成用例"按钮创建</p>
        </el-empty>
        <div v-else>
          <!-- 全选操作栏 -->
          <div class="batch-operation-bar">
            <el-checkbox
              :model-value="isAllSelected"
              :indeterminate="isIndeterminate"
              :disabled="loading || paginatedTestCases.length === 0"
              @update:model-value="handleSelectAll"
            >
              全选当前页
            </el-checkbox>
            <el-button
              :disabled="selectedCases.length === 0"
              link
              type="primary"
              @click="handleSelectAllPages"
            >
              选择全部 {{ filteredTestCases.length }} 条
            </el-button>
          </div>
          <!-- 列表视图 -->
          <div v-if="viewMode === 'list'" class="case-items">
            <div
              v-for="item in paginatedTestCases"
              :key="item.id"
              class="case-item-wrapper"
              :class="{ 'is-selected': isSelected(item.id) }"
            >
              <el-checkbox
                :model-value="isSelected(item.id)"
                @update:model-value="(val: boolean) => handleCaseSelect(val, item.id)"
                class="case-checkbox"
              />
              <CaseItem
                :case-item="item"
                @view-detail="viewDetail"
                @copy-case="copyCase"
                @retry-generate="retryGenerate"
                @delete-case="deleteCase"
              />
            </div>
          </div>
          <!-- 网格视图 -->
          <div v-else class="case-grid">
            <div
              v-for="item in paginatedTestCases"
              :key="item.id"
              class="grid-item-wrapper"
              :class="{ 'is-selected': isSelected(item.id) }"
            >
              <el-checkbox
                :model-value="isSelected(item.id)"
                @update:model-value="(val: boolean) => handleCaseSelect(val, item.id)"
                class="grid-checkbox"
              />
              <CaseItem
                :case-item="item"
                @view-detail="viewDetail"
                @copy-case="copyCase"
                @retry-generate="retryGenerate"
                @delete-case="deleteCase"
              />
            </div>
          </div>
          <!-- 分页组件 -->
          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="pagination.currentPage"
              v-model:page-size="pagination.pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="filteredTestCases.length"
              layout="total, sizes, prev, pager, next, jumper"
              background
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
            />
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  RefreshRight,
  FolderOpened,
  Document,
  Delete,
  Download,
  Grid,
  List,
  Filter,
  ArrowUp,
  ArrowDown,
  SuccessFilled,
  CircleCloseFilled,
  Edit,
  Monitor,
  Connection,
} from '@element-plus/icons-vue'
import CaseItem from '@/components/case/CaseItem.vue'
import { useCaseStore } from '@/store/case'
import type { TestCase } from '@/types/testCase'
import request from '@/utils/request'
import { useCaseFilter } from '@/composables/useCaseFilter'
import { useCaseSelection } from '@/composables/useCaseSelection'
import { useCaseExport } from '@/composables/useCaseExport'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()

// ---- 组件本地状态 ----
const loading = ref(false)
const viewMode = ref<'list' | 'grid'>('list')

// 项目列表
const projectList = ref<any[]>([])
const selectedProjectId = ref<number | null>(null)

// 需求文件列表
const requirementFileList = ref<any[]>([])

// 分页状态
const pagination = ref({
  currentPage: 1,
  pageSize: 10,
})

// ---- 筛选与统计 composable ----
const {
  filter,
  filterExpanded,
  selectedRequirementFileId,
  hasActiveFilter,
  successCount,
  failedCount,
  manualCount,
  uiCount,
  apiCount,
  highPriorityCount,
  mediumPriorityCount,
  lowPriorityCount,
  modules,
  filteredTestCases,
  handleFilterChange,
  applyStatsCardFilter,
  resetFilter,
} = useCaseFilter({ caseStore, pagination, selectedProjectId })

// 分页后的测试用例（依赖 filteredTestCases + pagination）
const paginatedTestCases = computed(() => {
  const start = (pagination.value.currentPage - 1) * pagination.value.pageSize
  const end = start + pagination.value.pageSize
  return filteredTestCases.value.slice(start, end)
})

// ---- 选择与批量操作 composable ----
const {
  selectedCases,
  recentlyDeletedIds,
  isAllSelected,
  isIndeterminate,
  isSelected,
  handleCaseSelect,
  handleSelectAll,
  handleSelectAllPages,
  clearSelection,
  handleBatchDelete,
  handleUndoDelete,
} = useCaseSelection({
  caseStore,
  paginatedTestCases,
  filteredTestCases,
  pagination,
  loading,
})

// ---- 导出功能 composable ----
const {
  exporting,
  handleExportAll,
  handleExportSelected,
} = useCaseExport({ filteredTestCases, selectedCases })

// ---- 分页事件处理 ----
const handleSizeChange = (size: number) => {
  pagination.value.pageSize = size
  pagination.value.currentPage = 1
}

const handleCurrentChange = (page: number) => {
  pagination.value.currentPage = page
}

// ---- 数据加载 ----

const fetchProjectList = async () => {
  try {
    const response = await request.get('/api/v1/project/list')
    if (response?.data?.items) {
      projectList.value = response.data.items.filter((p: any) => p.name !== '默认项目')
    }
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

const fetchRequirementFileList = async (projectId: number) => {
  if (!projectId) {
    requirementFileList.value = []
    return
  }
  try {
    const response = await request.get(`/api/v1/file/list/${projectId}`)
    // 处理多种可能的响应格式
    let files: any[] = []
    if (Array.isArray(response)) {
      files = response
    } else if (response?.data && Array.isArray(response.data)) {
      files = response.data
    } else if (response?.data?.items && Array.isArray(response.data.items)) {
      files = response.data.items
    }
    // 只显示需求文档类型的文件
    requirementFileList.value = files.filter(
      (file: any) => file.resource_type === 'requirement' || file.file_type?.includes('requirement')
    )
  } catch (error) {
    console.error('获取需求文件列表失败:', error)
    requirementFileList.value = []
  }
}

// 项目变更处理
const handleProjectChange = async (projectId: number | null) => {
  // 先清空选择，避免 Checkbox 状态混乱
  selectedCases.value = []
  recentlyDeletedIds.value = []

  // 重置所有筛选条件和分页
  filter.value = { module: '', priority: null, case_type: '', keyword: '', lifecycle_status: [] }
  selectedRequirementFileId.value = null
  requirementFileList.value = []
  pagination.value.currentPage = 1

  if (projectId) {
    loading.value = true
    try {
      await fetchRequirementFileList(projectId)
      await caseStore.fetchTestCases(projectId)
    } finally {
      loading.value = false
    }
  } else {
    caseStore.testCases = []
  }
}

// 需求文件变更处理 - 使用前端过滤，与模块/优先级筛选保持一致
const handleRequirementFileChange = () => {
  // 重置到第一页
  pagination.value.currentPage = 1
}

// ---- 页面导航 ----

const goToAIGenerate = () => {
  const projectId = selectedProjectId.value || Number(route.params.projectId)
  if (projectId) {
    router.push({
      path: '/home/case/ai-generate',
      query: { project_id: String(projectId) },
    })
  }
}

const viewDetail = (caseId: number) => {
  router.push(`/home/case/detail/${caseId}`)
}

// ---- 用例操作 ----

const copyCase = (caseItem: TestCase) => {
  const caseText =
    `用例编号: ${caseItem.case_no}\n` +
    `模块: ${caseItem.module}\n` +
    `标题: ${caseItem.title}\n` +
    `前置条件: ${caseItem.precondition}\n` +
    `测试步骤:\n${caseItem.steps?.map((step) => `${step.step_number || ''}. ${step.display_action || step.description || step.step || step.action || ''}`).join('\n')}\n` +
    `预期结果: ${caseItem.expected_result}\n` +
    `优先级: ${priorityText(caseItem.priority)}\n` +
    `用例类型: ${caseItem.case_type}`

  navigator.clipboard
    .writeText(caseText)
    .then(() => {
      ElMessage.success('用例已复制到剪贴板')
    })
    .catch(() => {
      ElMessage.error('复制失败')
    })
}

const retryGenerate = async (caseId: number) => {
  const projectId = selectedProjectId.value || Number(route.params.projectId)
  if (projectId) {
    await caseStore.retryFailedCases(projectId, [caseId])
    ElMessage.success('重试生成成功')
  }
}

const deleteCase = (caseId: number) => {
  ElMessageBox.confirm('确定要删除这个测试用例吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      const success = await caseStore.deleteTestCase(caseId)
      if (success) {
        ElMessage.success('删除成功')
        // 如果该用例在选中列表中，移除它
        const index = selectedCases.value.indexOf(caseId)
        if (index > -1) {
          selectedCases.value.splice(index, 1)
        }
        // 检查当前页是否还有数据，如果没有则回到上一页
        const currentPageData = paginatedTestCases.value
        if (currentPageData.length === 0 && pagination.value.currentPage > 1) {
          pagination.value.currentPage--
        }
      } else {
        ElMessage.error('删除失败')
      }
    })
    .catch(() => {})
}

// 优先级文本
const priorityText = (priority: number): string => {
  const map: Record<number, string> = { 1: '高', 2: '中', 3: '低' }
  return map[priority] || '中'
}

// ---- 生命周期 ----

onMounted(async () => {
  await fetchProjectList()

  // 如果有项目ID参数，直接加载
  const routeProjectId = Number(route.params.projectId)
  if (routeProjectId) {
    selectedProjectId.value = routeProjectId
    await handleProjectChange(routeProjectId)
  }
})

// 监听筛选条件变化，清空选择
watch(
  [
    selectedProjectId,
    selectedRequirementFileId,
    () => filter.value.module,
    () => filter.value.priority,
    () => filter.value.keyword,
    () => filter.value.lifecycle_status,
  ],
  () => {
    // 立即清空选择，避免 Checkbox 组件状态混乱
    selectedCases.value = []
    recentlyDeletedIds.value = [] // 同时清空撤销记录
  },
  { deep: true, flush: 'sync' }
)
</script>

<style scoped>
@import './TestCaseList.css';
</style>
