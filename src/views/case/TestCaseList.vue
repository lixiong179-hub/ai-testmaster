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
          <div
            class="stat-card stat-total"
            @click="applyStatsCardFilter(null)"
          >
            <div class="stat-icon">
              <el-icon><Document /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ filteredTestCases.length }}</span>
              <span class="stat-label">全部用例</span>
            </div>
          </div>
          <div
            class="stat-card stat-success"
            @click="applyStatsCardFilter('')"
          >
            <div class="stat-icon">
              <el-icon><SuccessFilled /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ successCount }}</span>
              <span class="stat-label">生成成功</span>
            </div>
          </div>
          <div
            class="stat-card stat-failed"
            @click="applyStatsCardFilter('')"
          >
            <div class="stat-icon">
              <el-icon><CircleCloseFilled /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ failedCount }}</span>
              <span class="stat-label">生成失败</span>
            </div>
          </div>
          <div
            class="stat-card stat-manual"
            @click="applyStatsCardFilter('manual')"
          >
            <div class="stat-icon">
              <el-icon><Edit /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ manualCount }}</span>
              <span class="stat-label">手工测试</span>
            </div>
          </div>
          <div
            class="stat-card stat-ui"
            @click="applyStatsCardFilter('ui_automation')"
          >
            <div class="stat-icon">
              <el-icon><Monitor /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ uiCount }}</span>
              <span class="stat-label">UI自动化</span>
            </div>
          </div>
          <div
            class="stat-card stat-api"
            @click="applyStatsCardFilter('api_automation')"
          >
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
import { testCaseViewApi } from '@/api/testCaseView'
import { downloadFromResponse, parseBlobError } from '@/utils/download'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()

// 状态
const loading = ref(false)
const exporting = ref(false)
const viewMode = ref<'list' | 'grid'>('list')
const filterExpanded = ref(true)

// 项目列表
const projectList = ref<any[]>([])
const selectedProjectId = ref<number | null>(null)

// 需求文件列表
const requirementFileList = ref<any[]>([])
const selectedRequirementFileId = ref<number | null>(null)

// 筛选条件
const filter = ref({
  module: '',
  priority: null as number | null,
  case_type: '',
  keyword: '',
})

// 分页状态
const pagination = ref({
  currentPage: 1,
  pageSize: 10,
})

// 批量选择状态
const selectedCases = ref<number[]>([])

// 是否全选当前页 - 只读computed
const isAllSelected = computed((): boolean => {
  if (paginatedTestCases.value.length === 0) return false
  return paginatedTestCases.value.every((item) => selectedCases.value.includes(item.id))
})

// 是否半选状态
const isIndeterminate = computed(() => {
  if (paginatedTestCases.value.length === 0) return false
  const selectedCount = paginatedTestCases.value.filter((item) =>
    selectedCases.value.includes(item.id)
  ).length
  return selectedCount > 0 && selectedCount < paginatedTestCases.value.length
})

// 使用 Set 优化查找性能
const selectedCasesSet = computed(() => new Set(selectedCases.value))

// 判断是否已选择
const isSelected = (id: number) => {
  return selectedCasesSet.value.has(id)
}

// 处理单个用例的选择
const handleCaseSelect = (val: boolean, id: number) => {
  if (val) {
    if (!selectedCases.value.includes(id)) {
      selectedCases.value.push(id)
    }
  } else {
    selectedCases.value = selectedCases.value.filter((caseId) => caseId !== id)
  }
}

// 全选/取消全选当前页
const handleSelectAll = (val: boolean) => {
  if (val) {
    // 添加当前页所有未选择的项
    paginatedTestCases.value.forEach((item) => {
      if (!selectedCases.value.includes(item.id)) {
        selectedCases.value.push(item.id)
      }
    })
  } else {
    // 移除当前页所有项
    const currentPageIds = paginatedTestCases.value.map((item) => item.id)
    selectedCases.value = selectedCases.value.filter((id) => !currentPageIds.includes(id))
  }
}

// 选择所有页
const handleSelectAllPages = () => {
  filteredTestCases.value.forEach((item) => {
    if (!selectedCases.value.includes(item.id)) {
      selectedCases.value.push(item.id)
    }
  })
}

// 清空选择
const clearSelection = () => {
  selectedCases.value = []
}

// 存储最近删除的用例ID，用于撤销
const recentlyDeletedIds = ref<number[]>([])

// 撤销删除
const handleUndoDelete = async () => {
  if (recentlyDeletedIds.value.length === 0) {
    ElMessage.warning('没有可撤销的删除操作')
    return
  }

  try {
    loading.value = true
    const result = await caseStore.batchRestoreTestCases(recentlyDeletedIds.value)
    loading.value = false

    // 清空已记录的删除ID
    recentlyDeletedIds.value = []

    if (result.fail_count === 0 && result.not_found_count === 0) {
      ElMessage.success(`成功恢复 ${result.success_count} 个测试用例`)
    } else {
      ElMessage.warning(
        `恢复完成：成功 ${result.success_count} 个，失败 ${result.fail_count} 个，未找到 ${result.not_found_count} 个`
      )
    }
  } catch (error) {
    loading.value = false
    ElMessage.error('撤销删除失败，请稍后重试')
  }
}

// 批量删除
const handleBatchDelete = () => {
  if (selectedCases.value.length === 0) {
    ElMessage.warning('请先选择要删除的用例')
    return
  }

  ElMessageBox.confirm(
    `确定要删除选中的 ${selectedCases.value.length} 个测试用例吗？`,
    '批量删除确认',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    }
  )
    .then(async () => {
      loading.value = true

      try {
        // 调用批量删除API
        const result = await caseStore.batchDeleteTestCases(selectedCases.value)

        loading.value = false

        // 记录删除的ID用于撤销
        if (result.deleted_ids && result.deleted_ids.length > 0) {
          recentlyDeletedIds.value = result.deleted_ids
        }

        // 清空选择
        selectedCases.value = []

        if (result.fail_count === 0 && result.not_found_count === 0) {
          // 显示带撤销按钮的成功消息
          ElMessage.success({
            message: `成功删除 ${result.success_count} 个测试用例`,
            duration: 5000,
            showClose: true,
          })
        } else {
          // 显示详细结果弹窗
          ElMessageBox.alert(
            `<div style="text-align: center;">
            <div style="font-size: 48px; margin-bottom: 16px;">${result.success_count === 0 ? '❌' : '⚠️'}</div>
            <div style="font-size: 18px; margin-bottom: 12px;">删除完成</div>
            <div style="color: #67c23a; margin-bottom: 8px;">✓ 成功：${result.success_count} 个</div>
            ${result.fail_count > 0 ? `<div style="color: #f56c6c; margin-bottom: 8px;">✗ 失败：${result.fail_count} 个</div>` : ''}
            ${result.not_found_count > 0 ? `<div style="color: #e6a23c;">⚠ 未找到：${result.not_found_count} 个</div>` : ''}
          </div>`,
            '删除结果',
            {
              confirmButtonText: '确定',
              dangerouslyUseHTMLString: true,
              type: result.success_count === 0 ? 'error' : 'warning',
            }
          )
        }

        // 检查当前页是否还有数据，如果没有则回到上一页
        const currentPageData = paginatedTestCases.value
        if (currentPageData.length === 0 && pagination.value.currentPage > 1) {
          pagination.value.currentPage--
        }
      } catch (error) {
        loading.value = false
        ElMessage.error('批量删除失败，请稍后重试')
      }
    })
    .catch(() => {})
}

// 计算属性
const hasActiveFilter = computed(() => {
  return (
    filter.value.module ||
    filter.value.priority !== null ||
    filter.value.keyword ||
    filter.value.case_type ||
    selectedRequirementFileId.value !== null
  )
})

// 统计数据计算
const successCount = computed(() => {
  return caseStore.testCases.filter((c) => c.generate_status === 1).length
})

const failedCount = computed(() => {
  return caseStore.testCases.filter((c) => c.generate_status === 2).length
})

const manualCount = computed(() => {
  const MANUAL_TYPES = ['manual', '功能', '功能测试', 'functional']
  return caseStore.testCases.filter((c) => MANUAL_TYPES.includes(c.case_type)).length
})

const uiCount = computed(() => {
  const UI_TYPES = ['ui_automation', 'UI', 'UI自动化']
  return caseStore.testCases.filter((c) => UI_TYPES.includes(c.case_type)).length
})

const apiCount = computed(() => {
  const API_TYPES = ['api_automation', 'API', '接口']
  return caseStore.testCases.filter((c) => API_TYPES.includes(c.case_type)).length
})

const highPriorityCount = computed(() => {
  return caseStore.testCases.filter((c) => c.priority === 1).length
})

const mediumPriorityCount = computed(() => {
  return caseStore.testCases.filter((c) => c.priority === 2).length
})

const lowPriorityCount = computed(() => {
  return caseStore.testCases.filter((c) => c.priority === 3).length
})

// 分页后的测试用例
const paginatedTestCases = computed(() => {
  const start = (pagination.value.currentPage - 1) * pagination.value.pageSize
  const end = start + pagination.value.pageSize
  return filteredTestCases.value.slice(start, end)
})

// 分页事件处理
const handleSizeChange = (size: number) => {
  pagination.value.pageSize = size
  pagination.value.currentPage = 1 // 切换每页条数时重置到第一页
}

const handleCurrentChange = (page: number) => {
  pagination.value.currentPage = page
}

// 获取项目列表
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

// 获取需求文件列表
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
  filter.value = { module: '', priority: null, case_type: '', keyword: '' }
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

// 筛选处理
const handleFilterChange = () => {
  // 重置到第一页
  pagination.value.currentPage = 1
}

const applyStatsCardFilter = (caseType: string | null) => {
  if (caseType === null) {
    filter.value = { module: '', priority: null, case_type: '', keyword: '' }
  } else {
    filter.value = { ...filter.value, case_type: caseType }
  }
  handleFilterChange()
}

// 重置筛选
const resetFilter = () => {
  filter.value = { module: '', priority: null, case_type: '', keyword: '' }
  selectedRequirementFileId.value = null
  pagination.value.currentPage = 1
  // 重新加载当前项目的全部用例
  if (selectedProjectId.value) {
    caseStore.fetchTestCases(selectedProjectId.value)
  }
}

// 模块列表
const modules = computed(() => {
  const moduleSet = new Set<string>()
  caseStore.testCases.forEach((caseItem) => {
    if (caseItem.module) moduleSet.add(caseItem.module)
  })
  return Array.from(moduleSet).sort()
})

// 筛选后的测试用例
const filteredTestCases = computed(() => {
  let filtered = caseStore.testCases

  // 按需求文件筛选
  if (selectedRequirementFileId.value !== null) {
    filtered = filtered.filter(
      (caseItem) => (caseItem as any).requirement_file_id === selectedRequirementFileId.value
    )
  }

  if (filter.value.module) {
    filtered = filtered.filter((caseItem) => caseItem.module === filter.value.module)
  }

  if (filter.value.priority !== null) {
    filtered = filtered.filter((caseItem) => caseItem.priority === filter.value.priority)
  }

  if (filter.value.case_type) {
    filtered = filtered.filter((caseItem) => caseItem.case_type === filter.value.case_type)
  }

  if (filter.value.keyword) {
    const keyword = filter.value.keyword.toLowerCase()
    filtered = filtered.filter(
      (caseItem) =>
        (caseItem.title && caseItem.title.toLowerCase().includes(keyword)) ||
        (caseItem.case_no && caseItem.case_no.toLowerCase().includes(keyword))
    )
  }

  return filtered
})

// 导出指定用例ID列表为功能用例Excel
const exportFunctionalExcel = async (ids: number[]) => {
  if (ids.length === 0) {
    ElMessage.warning('暂无可导出的用例')
    return
  }
  exporting.value = true
  try {
    const resp = await testCaseViewApi.exportToFunctionalExcel(ids)
    const fallback = `功能测试用例_${new Date().toISOString().slice(0, 10)}.xlsx`
    downloadFromResponse(resp, fallback)

    // 后端可能因权限静默过滤掉部分用例，前端给出提示
    const skippedRaw = resp.headers?.['x-export-skipped-count']
    const skipped = skippedRaw ? Number(skippedRaw) : 0
    const exported = ids.length - skipped
    if (skipped > 0) {
      ElMessage.warning(`已导出 ${exported} 条用例，${skipped} 条因权限被忽略`)
    } else {
      ElMessage.success(`已导出 ${exported} 条用例`)
    }
  } catch (err) {
    const msg = await parseBlobError(err, '导出失败，请稍后重试')
    console.error('导出失败:', err)
    ElMessage.error(msg)
  } finally {
    exporting.value = false
  }
}

// 导出全部（按当前筛选）
const handleExportAll = () => {
  const ids = filteredTestCases.value.map((c) => c.id)
  return exportFunctionalExcel(ids)
}

// 导出选中
const handleExportSelected = () => {
  if (selectedCases.value.length === 0) {
    ElMessage.warning('请先选择要导出的用例')
    return
  }
  return exportFunctionalExcel([...selectedCases.value])
}

// 跳转到AI生成页面
const goToAIGenerate = () => {
  const projectId = selectedProjectId.value || Number(route.params.projectId)
  if (projectId) {
    router.push({
      path: '/home/case/ai-generate',
      query: { project_id: String(projectId) },
    })
  }
}

// 查看用例详情
const viewDetail = (caseId: number) => {
  router.push(`/home/case/detail/${caseId}`)
}

// 复制用例
const copyCase = (caseItem: TestCase) => {
  const caseText =
    `用例编号: ${caseItem.case_no}\n` +
    `模块: ${caseItem.module}\n` +
    `标题: ${caseItem.title}\n` +
    `前置条件: ${caseItem.precondition}\n` +
    `测试步骤:\n${caseItem.steps?.map((step) => `${step.step_number}. ${step.action}`).join('\n')}\n` +
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

// 重试生成单个用例
const retryGenerate = async (caseId: number) => {
  const projectId = selectedProjectId.value || Number(route.params.projectId)
  if (projectId) {
    await caseStore.retryFailedCases(projectId, [caseId])
    ElMessage.success('重试生成成功')
  }
}

// 删除用例
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

// 页面加载
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
.test-case-list {
  padding: 20px;
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);
}

.main-card {
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.case-count {
  font-size: 14px;
  color: #909399;
  background-color: #f4f4f5;
  padding: 4px 12px;
  border-radius: 12px;
}

.filter-section {
  background-color: #f5f7fa;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.filter-row:last-child {
  margin-bottom: 0;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
  min-width: 60px;
  text-align: right;
}

.filter-select {
  width: 200px;
}

.filter-search {
  flex: 1;
  max-width: 300px;
}

.empty-state,
.loading-state {
  padding: 60px 0;
}

.empty-hint {
  margin-top: 16px;
  color: #909399;
  font-size: 14px;
}

.case-list {
  min-height: 400px;
}

.case-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}

:deep(.el-empty__image) {
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 批量操作样式 */
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.view-toggle {
  margin-left: 8px;
}

.view-toggle :deep(.el-button) {
  padding: 8px 12px;
}

.batch-tag {
  font-size: 14px;
  padding: 0 12px;
  height: 32px;
  line-height: 32px;
}

.batch-operation-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background-color: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 16px;
  border: 1px solid #e4e7ed;
}

.case-item-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 0;
  border-radius: 0;
  transition: all 0.3s ease;
  border: none;
  width: 100%;
}

.case-item-wrapper:hover {
  background-color: transparent;
}

.case-item-wrapper.is-selected {
  background-color: transparent;
  border-color: transparent;
}

.case-checkbox {
  margin-top: 4px;
  flex-shrink: 0;
}

.case-checkbox :deep(.el-checkbox__label) {
  display: none;
}

.case-checkbox :deep(.el-checkbox__input) {
  transform: scale(1.2);
}

/* 统计数据区域 */
.stats-section {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid #e2e8f0;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: white;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  border: 1px solid transparent;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-total .stat-icon {
  background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%);
  color: #409eff;
}

.stat-success .stat-icon {
  background: linear-gradient(135deg, #f0f9eb 0%, #e1f3d8 100%);
  color: #67c23a;
}

.stat-failed .stat-icon {
  background: linear-gradient(135deg, #fef0f0 0%, #fee2e2 100%);
  color: #f56c6c;
}

.stat-manual .stat-icon {
  background: linear-gradient(135deg, #fdf6ec 0%, #faecd8 100%);
  color: #e6a23c;
}

.stat-ui .stat-icon {
  background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%);
  color: #409eff;
}

.stat-api .stat-icon {
  background: linear-gradient(135deg, #f0f9eb 0%, #e1f3d8 100%);
  color: #67c23a;
}

.stat-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  line-height: 1;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
}

.priority-distribution {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: white;
  border-radius: 8px;
}

.priority-label {
  font-size: 14px;
  color: #6b7280;
  white-space: nowrap;
}

.priority-bar {
  flex: 1;
  height: 24px;
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  background: #f1f5f9;
}

.priority-segment {
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
  font-weight: 600;
  transition: width 0.3s ease;
  min-width: 0;
}

.priority-segment.high {
  background: linear-gradient(135deg, #f56c6c 0%, #f78909 100%);
}

.priority-segment.medium {
  background: linear-gradient(135deg, #e6a23c 0%, #ebb563 100%);
}

.priority-segment.low {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
}

/* 筛选区域 */
.filter-section {
  background-color: #f5f7fa;
  border-radius: 12px;
  margin-bottom: 20px;
  overflow: hidden;
  border: 1px solid #e4e7ed;
}

.filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: white;
  cursor: pointer;
  transition: background-color 0.3s ease;
}

.filter-header:hover {
  background-color: #f5f7fa;
}

.filter-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.filter-active-tag {
  margin-left: 8px;
}

.filter-content {
  padding: 16px 20px;
  background: white;
  border-top: 1px solid #ebeef5;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.filter-row:last-child {
  margin-bottom: 0;
}

/* 网格视图 */
.case-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.grid-item-wrapper {
  position: relative;
  transition: all 0.3s ease;
}

.grid-item-wrapper:hover {
  transform: translateY(-2px);
}

.grid-checkbox {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 10;
}

.grid-checkbox :deep(.el-checkbox__label) {
  display: none;
}

.grid-checkbox :deep(.el-checkbox__input) {
  transform: scale(1.2);
}

/* 空状态操作区 */
.empty-state {
  padding: 60px 0;
}

.empty-actions {
  margin-top: 20px;
}

.project-select {
  width: 280px;
}

@media (max-width: 1400px) {
  .stats-cards {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 1200px) {
  .case-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .stats-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .filter-row {
    flex-wrap: wrap;
  }
}
</style>
