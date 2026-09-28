import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import bugApi from '@/api/bug'
import projectApi from '@/api/project'
import { useProjectStore } from '@/store/project'
import type { TagType } from '@/types/element-plus'
import type {
  BugItem,
  BugSeverity,
  BugSource,
  BugStatus,
  BugUxCategory,
} from '@/api/bug'
import type { Project } from '@/api/project'

/** 严重级别选项：value 与后端 severity(1-4) 对齐 */
export const severityOptions = [
  { label: '致命', value: 1 as BugSeverity },
  { label: '严重', value: 2 as BugSeverity },
  { label: '一般', value: 3 as BugSeverity },
  { label: '轻微', value: 4 as BugSeverity },
] as const

/** 来源选项：value 与后端 source(manual/self_test) 对齐 */
export const sourceOptions = [
  { label: '手动', value: 'manual' as BugSource },
  { label: '自测', value: 'self_test' as BugSource },
] as const

/** 状态选项：value 与后端 status 枚举对齐 */
export const statusOptions = [
  { label: '待处理', value: 'open' as BugStatus },
  { label: '处理中', value: 'in_progress' as BugStatus },
  { label: '已修复', value: 'fixed' as BugStatus },
  { label: '已关闭', value: 'closed' as BugStatus },
  { label: '已拒绝', value: 'rejected' as BugStatus },
] as const

/** UX 分类选项：value 与后端 VALID_UX_CATEGORIES 对齐 */
export const uxCategoryOptions = [
  { label: '加载体验', value: 'loading_experience' as BugUxCategory },
  { label: '错误反馈', value: 'error_feedback' as BugUxCategory },
  { label: '响应性能', value: 'response_performance' as BugUxCategory },
  { label: '视觉一致性', value: 'visual_consistency' as BugUxCategory },
  { label: '空状态', value: 'empty_state' as BugUxCategory },
  { label: '安全', value: 'security' as BugUxCategory },
] as const

/** Bug 列表筛选条件（project_id 必填） */
export interface BugFilters {
  project_id: number | ''
  severity: BugSeverity | ''
  source: BugSource | ''
  ux_category: BugUxCategory | ''
  status: BugStatus | ''
}

// ==================== 标签/颜色/文案映射（模块级工具） ====================

const severityLabelMap = new Map<number, string>(
  severityOptions.map((opt) => [opt.value, opt.label])
)
const severityTagTypeMap = new Map<number, TagType>([
  [1, 'danger'],
  [2, 'warning'],
  [3, 'primary'],
  [4, 'info'],
])
const sourceLabelMap = new Map<string, string>(
  sourceOptions.map((opt) => [opt.value, opt.label])
)
const statusLabelMap = new Map<string, string>(
  statusOptions.map((opt) => [opt.value, opt.label])
)
const statusTagTypeMap = new Map<string, TagType>([
  ['open', 'info'],
  ['in_progress', 'primary'],
  ['fixed', 'success'],
  ['closed', 'success'],
  ['rejected', 'danger'],
])
const uxCategoryLabelMap = new Map<string, string>(
  uxCategoryOptions.map((opt) => [opt.value, opt.label])
)
const priorityLabelMap = new Map<number, string>([
  [1, '高'],
  [2, '中'],
  [3, '低'],
])

/** 严重级别文案 */
export function getSeverityLabel(severity: number): string {
  return severityLabelMap.get(severity) ?? String(severity)
}
/** 严重级别 Tag 颜色 */
export function getSeverityTagType(severity: number): TagType {
  return severityTagTypeMap.get(severity) ?? 'info'
}
/** 来源文案 */
export function getSourceLabel(source: string): string {
  return sourceLabelMap.get(source) ?? source
}
/** 状态文案 */
export function getStatusLabel(status: string): string {
  return statusLabelMap.get(status) ?? status
}
/** 状态 Tag 颜色 */
export function getStatusTagType(status: string): TagType {
  return statusTagTypeMap.get(status) ?? 'info'
}
/** UX 分类文案 */
export function getUxCategoryLabel(category: string | null): string {
  if (!category) return '-'
  return uxCategoryLabelMap.get(category) ?? category
}
/** 优先级文案 */
export function getPriorityLabel(priority: number): string {
  return priorityLabelMap.get(priority) ?? String(priority)
}

/** 解析 attachments（后端为 JSON 数组字符串），失败时返回空数组 */
export function parseAttachments(raw: string): string[] {
  try {
    const parsed = JSON.parse(raw) as unknown
    if (Array.isArray(parsed)) {
      return parsed.filter((item): item is string => typeof item === 'string')
    }
    return []
  } catch {
    return []
  }
}

/**
 * Bug 缺陷列表组合式逻辑。
 * 负责项目下拉加载、Bug 列表查询、筛选/分页/重置与详情弹窗状态。
 *
 * 支持两种使用模式：
 * 1. 独立页面（默认）：从 URL query 回填 project_id，用户手动选择项目后查询。
 * 2. 嵌入式（options.taskId / options.projectId）：父组件直接传入任务ID与项目ID，
 *    挂载即自动按 task_id 查询该任务产生的缺陷，常用于报告详情"关联缺陷"Tab。
 */
export interface UseBugListOptions {
  /** 任务ID：固定按该任务筛选缺陷（嵌入式场景，来自报告的 test_task_id） */
  taskId?: number
  /** 项目ID：父组件直接指定项目，免去用户手动选择 */
  projectId?: number
}

export function useBugList(options: UseBugListOptions = {}) {
  const route = useRoute()
  const projectStore = useProjectStore()

  const loading = ref(false)
  const errorMessage = ref('')
  const bugs = ref<BugItem[]>([])
  const projects = ref<Project[]>([])

  /** 固定的任务ID筛选（嵌入式场景），独立页面模式下为 undefined */
  const taskId = ref<number | undefined>(options.taskId)

  /** 分页状态 */
  const pagination = reactive({
    page: 1,
    pageSize: 20,
    total: 0,
  })

  /** 筛选条件 */
  const filters = reactive<BugFilters>({
    project_id: '',
    severity: '',
    source: '',
    ux_category: '',
    status: '',
  })

  /** 详情弹窗状态 */
  const detailVisible = ref(false)
  const currentBug = ref<BugItem | null>(null)

  /** 加载项目下拉数据，并从 URL query 回填 project_id */
  const loadProjects = async (): Promise<void> => {
    try {
      const response = await projectApi.getProjects({ page: 1, page_size: 100 })
      projects.value = response.data.items ?? []

      // 支持 URL 参数 project_id 预选，便于从其他页面深链接
      const projectIdQuery = route.query.project_id
      if (projectIdQuery) {
        const parsed = Number(projectIdQuery)
        if (!Number.isNaN(parsed) && parsed > 0) {
          filters.project_id = parsed
        }
      } else if (projectStore.currentProjectId) {
        // URL 无参数时回退到全局项目上下文（跨模块联动）
        filters.project_id = projectStore.currentProjectId
      }
    } catch (error: unknown) {
      // 项目下拉加载失败时透出原因，不阻断页面
      const msg = error instanceof Error ? error.message : '获取项目列表失败'
      ElMessage.error(msg)
    }
  }

  /** 加载 Bug 列表（project_id 必填，未选时给出提示） */
  const loadBugs = async (): Promise<void> => {
    if (!filters.project_id) {
      ElMessage.warning('请先选择项目')
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      const params = {
        project_id: filters.project_id,
        page: pagination.page,
        page_size: pagination.pageSize,
        ...(filters.severity !== '' ? { severity: filters.severity } : {}),
        ...(filters.source !== '' ? { source: filters.source } : {}),
        ...(filters.ux_category !== '' ? { ux_category: filters.ux_category } : {}),
        ...(filters.status !== '' ? { status: filters.status } : {}),
        ...(taskId.value ? { task_id: taskId.value } : {}),
      }
      const response = await bugApi.getBugList(params)
      const data = response.data as unknown as {
        items: BugItem[]
        total: number
      }
      bugs.value = data.items ?? []
      pagination.total = data.total ?? 0
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '获取缺陷列表失败'
      errorMessage.value = msg
      ElMessage.error(msg)
    } finally {
      loading.value = false
    }
  }

  /** 查询：重置到第一页后加载 */
  const handleSearch = (): void => {
    pagination.page = 1
    loadBugs()
  }

  /** 重置筛选条件（保留项目选择，避免用户重复选择项目） */
  const handleReset = (): void => {
    filters.severity = ''
    filters.source = ''
    filters.ux_category = ''
    filters.status = ''
    pagination.page = 1
    loadBugs()
  }

  /** 分页大小变更 */
  const handleSizeChange = (size: number): void => {
    pagination.pageSize = size
    pagination.page = 1
    loadBugs()
  }

  /** 当前页变更 */
  const handleCurrentChange = (page: number): void => {
    pagination.page = page
    loadBugs()
  }

  /** 打开详情弹窗 */
  const handleViewDetail = (bug: BugItem): void => {
    currentBug.value = bug
    detailVisible.value = true
  }

  /** 关闭详情弹窗 */
  const handleDetailClose = (): void => {
    detailVisible.value = false
    currentBug.value = null
  }

  /** 列表接口未返回 project_id/project_name，按当前筛选项目回填名称 */
  const currentProjectName = (): string => {
    const pid = filters.project_id
    if (!pid) return '-'
    return projects.value.find((p) => p.id === pid)?.name ?? '-'
  }

  onMounted(async () => {
    // 嵌入式场景：父组件直接传入 projectId，免去加载项目下拉与用户选择
    if (options.projectId && options.projectId > 0) {
      filters.project_id = options.projectId
      loadBugs()
      return
    }
    await loadProjects()
    // 若 URL 已带回 project_id 或用户手动选择后，自动加载首屏
    if (filters.project_id) {
      loadBugs()
    }
  })

  return {
    loading,
    errorMessage,
    bugs,
    projects,
    pagination,
    filters,
    taskId,
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
  }
}
