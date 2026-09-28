<template>
  <div :class="embedded ? 'bug-list-embedded' : 'bug-list-page'">
    <el-card class="page-card">
      <template v-if="!embedded" #header>
        <div class="card-header">
          <h2>缺陷管理</h2>
        </div>
      </template>

      <!-- 筛选区：项目(必选) / 严重级别 / 来源 / UX分类 / 状态 -->
      <div class="search-filter">
        <el-row :gutter="16">
          <el-col v-if="!embedded" :xs="24" :sm="12" :md="6">
            <el-select
              v-model="filters.project_id"
              placeholder="请选择项目"
              clearable
              style="width: 100%"
              @change="handleSearch"
            >
              <el-option
                v-for="project in projects"
                :key="project.id"
                :label="project.name"
                :value="project.id"
              />
            </el-select>
          </el-col>
          <el-col :xs="24" :sm="12" :md="6">
            <el-select
              v-model="filters.severity"
              placeholder="严重级别"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="opt in severityOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-col>
          <el-col :xs="24" :sm="12" :md="6">
            <el-select
              v-model="filters.source"
              placeholder="来源"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="opt in sourceOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-col>
          <el-col :xs="24" :sm="12" :md="6">
            <el-select
              v-model="filters.ux_category"
              placeholder="UX分类"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="opt in uxCategoryOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-col>
          <el-col :xs="24" :sm="12" :md="6">
            <el-select
              v-model="filters.status"
              placeholder="状态"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="opt in statusOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-col>
          <el-col :xs="24" :sm="12" :md="6" class="text-right">
            <el-button type="primary" @click="handleSearch">
              <el-icon><Search /></el-icon>查询
            </el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-col>
        </el-row>
      </div>

      <!-- 错误状态 -->
      <ErrorState
        v-if="errorMessage && !loading"
        title="缺陷列表加载失败"
        :reason="errorMessage"
        :retryable="true"
        @retry="loadBugs"
      />

      <!-- 数据表格 -->
      <el-table
        v-else
        v-loading="loading"
        :data="bugs"
        style="width: 100%"
        border
        stripe
      >
        <el-table-column prop="bug_no" label="Bug编号" width="170" />
        <el-table-column prop="title" label="缺陷标题" min-width="220" show-overflow-tooltip />
        <el-table-column v-if="!embedded" label="所属项目" width="160">
          <template #default>
            {{ currentProjectName() }}
          </template>
        </el-table-column>
        <el-table-column label="严重级别" width="110">
          <template #default="{ row }">
            <el-tag :type="getSeverityTagType(row.severity)" size="small">
              {{ getSeverityLabel(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="90">
          <template #default="{ row }">
            {{ getSourceLabel(row.source) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small" effect="plain">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="180">
          <template #default="{ row }">
            {{ row.create_time ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleViewDetail(row)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="emptyDescription" :image-size="embedded ? 100 : undefined">
            <div v-if="!embedded" class="bug-empty-hint">执行测试任务后自动生成缺陷记录</div>
            <slot v-else name="empty-action" />
          </el-empty>
        </template>
      </el-table>

      <!-- 分页 -->
      <div class="pagination" v-if="pagination.total > 0">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="pagination.total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 详情弹窗：展示完整字段 -->
    <el-dialog
      v-model="detailVisible"
      title="缺陷详情"
      width="720px"
      destroy-on-close
      @close="handleDetailClose"
    >
      <el-descriptions v-if="currentBug" :column="2" border>
        <el-descriptions-item label="Bug编号">{{ currentBug.bug_no }}</el-descriptions-item>
        <el-descriptions-item label="所属项目">
          {{ currentProjectName() }}
        </el-descriptions-item>
        <el-descriptions-item label="缺陷标题" :span="2">
          {{ currentBug.title }}
        </el-descriptions-item>
        <el-descriptions-item label="严重级别">
          <el-tag :type="getSeverityTagType(currentBug.severity)" size="small">
            {{ getSeverityLabel(currentBug.severity) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="优先级">
          {{ getPriorityLabel(currentBug.priority) }}
        </el-descriptions-item>
        <el-descriptions-item label="来源">
          {{ getSourceLabel(currentBug.source) }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusTagType(currentBug.status)" size="small" effect="plain">
            {{ getStatusLabel(currentBug.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="UX分类">
          {{ getUxCategoryLabel(currentBug.ux_category) }}
        </el-descriptions-item>
        <el-descriptions-item label="报告人ID">{{ currentBug.reporter_id }}</el-descriptions-item>
        <el-descriptions-item label="处理人ID">
          {{ currentBug.assignee_id ?? '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="关联用例ID">
          {{ currentBug.test_case_id ?? '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="关联结果ID">
          {{ currentBug.test_result_id ?? '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ currentBug.create_time ?? '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ currentBug.update_time ?? '-' }}
        </el-descriptions-item>
        <!-- 扩展字段：列表接口当前未返回，接入详情接口后自动展示 -->
        <el-descriptions-item v-if="currentBug.description" label="详细描述" :span="2">
          {{ currentBug.description }}
        </el-descriptions-item>
        <el-descriptions-item v-if="currentBug.reproduction_steps" label="复现步骤" :span="2">
          {{ currentBug.reproduction_steps }}
        </el-descriptions-item>
        <el-descriptions-item v-if="currentBug.expected_behavior" label="预期行为" :span="2">
          {{ currentBug.expected_behavior }}
        </el-descriptions-item>
        <el-descriptions-item v-if="currentBug.actual_behavior" label="实际行为" :span="2">
          {{ currentBug.actual_behavior }}
        </el-descriptions-item>
        <el-descriptions-item
          v-if="currentBug.attachments && parseAttachments(currentBug.attachments).length > 0"
          label="截图/附件"
          :span="2"
        >
          <div class="attachment-links">
            <a
              v-for="(url, idx) in parseAttachments(currentBug.attachments)"
              :key="idx"
              :href="sanitizeUrl(url)"
              target="_blank"
              rel="noopener noreferrer"
            >
              附件{{ idx + 1 }}
            </a>
          </div>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="handleDetailClose">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
import ErrorState from '@/views/case/components/ErrorState.vue'
import { sanitizeUrl } from '@/utils/security'
import {
  useBugList,
  severityOptions,
  sourceOptions,
  statusOptions,
  uxCategoryOptions,
  getSeverityLabel,
  getSeverityTagType,
  getSourceLabel,
  getStatusLabel,
  getStatusTagType,
  getUxCategoryLabel,
  getPriorityLabel,
  parseAttachments,
} from './useBugList'

/**
 * 组件支持两种使用模式：
 * 1. 独立页面（默认）：通过 URL query 选择项目后查询。
 * 2. 嵌入式（embedded）：由父组件传入 taskId/projectId，挂载即按任务筛选，
 *    隐藏项目选择列与"所属项目"列，并暴露 empty-action 插槽用于自定义空状态操作。
 */
const props = withDefaults(defineProps<{
  taskId?: number
  projectId?: number
  embedded?: boolean
  /** 空状态描述文案，嵌入式场景下默认"本次执行未发现缺陷" */
  emptyDescription?: string
}>(), {
  taskId: undefined,
  projectId: undefined,
  embedded: false,
  emptyDescription: '暂无缺陷数据',
})

const {
  loading,
  errorMessage,
  bugs,
  projects,
  pagination,
  filters,
  detailVisible,
  currentBug,
  loadBugs,
  handleSearch,
  handleReset,
  handleSizeChange,
  handleCurrentChange,
  handleViewDetail,
  handleDetailClose,
  currentProjectName,
} = useBugList({
  taskId: props.taskId,
  projectId: props.projectId,
})
</script>

<style scoped lang="scss">
.bug-list-page {
  padding: 20px;
}

/* 嵌入式：去除页面级内边距，适配 Tab 内嵌场景 */
.bug-list-embedded {
  padding: 0;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }
}

.search-filter {
  margin-bottom: 20px;
}

.text-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.attachment-links {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;

  a {
    color: var(--el-color-primary);
    text-decoration: underline;
  }
}

.bug-empty-hint {
  margin-top: 8px;
  color: var(--color-text-muted, #909399);
  font-size: 13px;
}
</style>
