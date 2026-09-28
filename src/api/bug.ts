import request from '@/utils/request'

// ==================== Bug 缺陷类型定义 ====================
// 字段对齐后端 app/models/bug.py 与 app/api/v1/endpoints/bug.py 的 /list 响应

/** Bug 严重程度: 1=致命 2=严重 3=一般 4=轻微 */
export type BugSeverity = 1 | 2 | 3 | 4

/** Bug 优先级: 1=高 2=中 3=低 */
export type BugPriority = 1 | 2 | 3

/** Bug 状态: open=待处理 in_progress=处理中 fixed=已修复 closed=已关闭 rejected=已拒绝 */
export type BugStatus = 'open' | 'in_progress' | 'fixed' | 'closed' | 'rejected'

/** Bug 来源: manual=手动 self_test=自测 */
export type BugSource = 'manual' | 'self_test'

/** UX 缺陷分类（与后端 VALID_UX_CATEGORIES 对齐） */
export type BugUxCategory =
  | 'loading_experience'
  | 'error_feedback'
  | 'response_performance'
  | 'visual_consistency'
  | 'empty_state'
  | 'security'

/**
 * Bug 列表条目。
 * 必填字段为 /bugs/list 接口实际返回的字段；
 * 扩展字段（description/reproduction_steps 等）当前列表接口未返回，标记为可选，
 * 便于后续接入详情接口时复用同一类型，详情弹窗以 v-if 条件渲染。
 */
export interface BugItem {
  id: number
  bug_no: string
  title: string
  severity: BugSeverity
  priority: BugPriority
  status: BugStatus
  source: BugSource
  ux_category: BugUxCategory | null
  reporter_id: number
  assignee_id: number | null
  test_case_id: number | null
  test_result_id: number | null
  create_time: string | null
  update_time: string | null
  // 扩展字段（详情接口返回时填充，列表接口当前不返回）
  description?: string
  reproduction_steps?: string | null
  expected_behavior?: string | null
  actual_behavior?: string | null
  attachments?: string | null
}

/** Bug 列表分页响应 */
export interface BugListResponse {
  items: BugItem[]
  total: number
  page: number
  page_size: number
}

/** Bug 列表查询参数（project_id 必填，后端 Query(...) 强制要求） */
export interface BugListParams {
  project_id: number
  severity?: BugSeverity
  source?: BugSource
  ux_category?: BugUxCategory
  status?: BugStatus
  /** 任务ID：筛选该任务执行产生的缺陷（通过 test_result 关联） */
  task_id?: number
  page?: number
  page_size?: number
}

/** Bug 列表 API 封装 */
const bugApi = {
  /**
   * 获取 Bug 列表（GET /api/v1/bugs/list）。
   * 支持按项目、严重级别、来源、UX 分类、状态、任务ID筛选。
   * 响应拦截器返回 ApiResponse，response.data 即 BugListResponse。
   */
  getBugList: (params: BugListParams) => {
    return request.get<BugListResponse>('/api/v1/bugs/list', { params })
  },
}

export default bugApi
