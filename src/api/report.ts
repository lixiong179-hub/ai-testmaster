import request from '@/utils/request'

// ==================== 缺陷维度类型定义 ====================

/** 缺陷概览 - 按严重度统计 */
export interface DefectOverview {
  p0_count: number        // 致命数
  p1_count: number        // 严重数
  p2_count: number        // 一般数
  p3_count: number        // 轻微数
  total_count: number     // 缺陷总数
  defect_density: number  // 缺陷密度（缺陷/用例数）
  high_severity_ratio: number  // 高严重度占比（P0+P1 / total）
  defect_coverage_rate: number // 缺陷发现覆盖率
  coverage_insufficient_warning: boolean // 覆盖不足警告
}

/** 单条缺陷记录 */
export interface DefectItem {
  bug_no: string          // Bug编号
  title: string           // 缺陷标题
  severity: number        // 严重度: 1=P0致命 2=P1严重 3=P2一般 4=P3轻微
  ux_category: string     // UX缺陷分类
  module: string          // 功能模块
  status: string          // 状态
  reproduction_steps: string | null  // 复现步骤
  evidence: Record<string, unknown> | null  // 缺陷证据
  ai_analysis: string | null  // AI分析
  fix_suggestion: string | null  // 修复建议
}

/** 缺陷分布 - 按模块 */
export interface ModuleDistribution {
  module: string
  count: number
}

/** 缺陷分布 - 按类型 */
export interface CategoryDistribution {
  category: string
  count: number
}

/** 缺陷分布 */
export interface DefectDistribution {
  by_module: ModuleDistribution[]     // 按功能模块分布
  by_category: CategoryDistribution[] // 按缺陷类型分布
}

/** 控制台错误 */
export interface ConsoleError {
  error_type: string   // 错误类型
  message: string      // 错误消息
  source: string       // 来源
  timestamp: string    // 时间戳
}

/** 网络失败 */
export interface NetworkFailure {
  url: string          // 请求URL
  status_code: number  // HTTP状态码
  duration: number     // 耗时(ms)
  method: string       // 请求方法
  timestamp: string    // 时间戳
}

/** 内存泄漏嫌疑 */
export interface MemoryLeakSuspect {
  description: string  // 描述
  evidence: string     // 证据
  severity: string     // 严重程度
}

/** 隐性缺陷 */
export interface ImplicitDefects {
  console_errors: ConsoleError[]     // 控制台错误列表
  network_failures: NetworkFailure[] // 网络失败列表
  memory_leaks: MemoryLeakSuspect[]  // 内存泄漏嫌疑
}

/** 安全发现 */
export interface SecurityFinding {
  type: string         // 安全缺陷类型
  description: string  // 描述
  evidence: string     // 证据
  severity: string     // 严重程度
}

/** 覆盖评估 */
export interface CoverageAssessment {
  covered_modules: string[]    // 已发现缺陷的模块
  uncovered_modules: string[]  // 未发现缺陷的模块
  coverage_rate: number        // 覆盖率百分比
}

/** 报告 content JSON 中的完整结构 */
export interface ReportContent {
  test_cases: TestCaseResult[]
  statistics: Record<string, unknown>
  environment: Record<string, unknown> | null
  defect_overview: DefectOverview | null
  defect_list: DefectItem[] | null
  defect_distribution: DefectDistribution | null
  implicit_defects: ImplicitDefects | null
  security_findings: SecurityFinding[] | null
  coverage_assessment: CoverageAssessment | null
}

// ==================== 基础报告类型 ====================

// 报告接口类型定义
export interface Report {
  id: number
  project_id: number
  test_task_id: number
  name: string
  status: string
  total_cases: number
  passed_cases: number
  failed_cases: number
  blocked_cases: number
  pass_rate: number
  description?: string
  start_time?: string
  end_time?: string
  execution_time?: number
  summary?: string
  create_time: string
  update_time?: string
  project_name?: string
  test_task_name?: string
  test_cases?: TestCaseResult[]
  content?: ReportContent | null
}

export interface TestCaseResult {
  test_case_id: number
  status: string
  actual_result: string
  start_time: string
  end_time: string
  expected_result?: string
  test_case_name?: string
}

export interface ReportListResponse {
  items: Report[]
  total: number
  page: number
  page_size: number
}

// 报告API封装
const reportApi = {
  // 获取报告列表
  getReports: (params: { page?: number; page_size?: number; project_id?: number }) => {
    return request.get<ReportListResponse>('/api/v1/report/', { params })
  },

  // 获取报告详情（需要project_id）
  getReportDetail: (id: number, project_id: number) => {
    return request.get<Report>(`/api/v1/report/${id}`, { params: { project_id } })
  },

  // 删除报告（需要project_id）
  deleteReport: (id: number, project_id: number) => {
    return request.delete(`/api/v1/report/${id}`, { params: { project_id } })
  },

  // 导出报告为PDF
  // 后端：POST /api/v1/report/{report_id}/export
  exportReportPDF: (id: number, project_id: number) => {
    return request.post(
      `/api/v1/report/${id}/export`,
      {
        report_id: id,
        format: 'pdf',
        project_id,
      },
      {
        responseType: 'blob',
      }
    )
  },

  // 导出报告为HTML
  // 后端：POST /api/v1/report/{report_id}/export
  exportReportHTML: (id: number, project_id: number) => {
    return request.post(
      `/api/v1/report/${id}/export`,
      {
        report_id: id,
        format: 'html',
        project_id,
      },
      {
        responseType: 'blob',
      }
    )
  },
}

export default reportApi
