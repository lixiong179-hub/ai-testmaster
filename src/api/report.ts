import request from '@/utils/request'

// 报告接口类型定义
export interface Report {
  id: number
  project_id: number
  test_task_id: number
  name: string
  total_cases: number
  passed_cases: number
  failed_cases: number
  pass_rate: number
  created_at: string
  project_name?: string
  test_task_name?: string
  test_cases?: TestCaseResult[]
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
  exportReportPDF: (id: number, project_id: number) => {
    return request.get(`/api/v1/report/${id}/export`, {
      params: { project_id, format: 'pdf' },
      responseType: 'blob',
    })
  },

  // 导出报告为HTML
  exportReportHTML: (id: number, project_id: number) => {
    return request.get(`/api/v1/report/${id}/export`, {
      params: { project_id, format: 'html' },
      responseType: 'blob',
    })
  },
}

export default reportApi
