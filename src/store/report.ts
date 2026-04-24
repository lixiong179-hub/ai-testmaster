import { defineStore } from 'pinia'
import reportApi, { Report } from '@/api/report'

export const useReportStore = defineStore('report', {
  state: () => ({
    reports: [] as Report[],
    total: 0,
    currentReport: null as Report | null,
    loading: false,
    error: null as string | null,
  }),

  getters: {
    getReportById: (state) => (id: number) => {
      return state.reports.find((report) => report.id === id)
    },
  },

  actions: {
    // 获取报告列表
    async fetchReports(params: { page?: number; page_size?: number; project_id?: number }) {
      this.loading = true
      this.error = null
      try {
        const response = (await reportApi.getReports(params)) as any
        // 响应拦截器已返回response.data，所以response就是ApiResponse对象
        const data = response?.data || response || {}
        this.reports = data.reports || data.items || []
        this.total = data.total || 0
      } catch (error: unknown) {
        const err = error as { message?: string }
        this.error = err?.message || '获取报告列表失败'
        console.error('获取报告列表失败:', error)
      } finally {
        this.loading = false
      }
    },

    // 获取报告详情（需要project_id）
    async fetchReportDetail(id: number, project_id: number) {
      this.loading = true
      this.error = null
      try {
        const response = (await reportApi.getReportDetail(id, project_id)) as any
        const responseData = response?.data?.data || response?.data || response || {}
        this.currentReport = responseData
        return this.currentReport
      } catch (error: unknown) {
        const err = error as { message?: string }
        this.error = err?.message || '获取报告详情失败'
        console.error('获取报告详情失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    // 删除报告（需要project_id）
    async deleteReport(id: number, project_id: number) {
      this.loading = true
      this.error = null
      try {
        await reportApi.deleteReport(id, project_id)
        // 从列表中移除删除的报告
        this.reports = this.reports.filter((report) => report.id !== id)
        this.total--
      } catch (error: unknown) {
        const err = error as { message?: string }
        this.error = err?.message || '删除报告失败'
        console.error('删除报告失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    // 导出报告为PDF（需要project_id）
    async exportReportPDF(id: number, project_id: number) {
      this.loading = true
      this.error = null
      try {
        const response = await reportApi.exportReportPDF(id, project_id)
        return response
      } catch (error: unknown) {
        const err = error as { message?: string }
        this.error = err?.message || '导出PDF失败'
        console.error('导出PDF失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    // 导出报告为HTML（需要project_id）
    async exportReportHTML(id: number, project_id: number) {
      this.loading = true
      this.error = null
      try {
        const response = await reportApi.exportReportHTML(id, project_id)
        return response
      } catch (error: unknown) {
        const err = error as { message?: string }
        this.error = err?.message || '导出HTML失败'
        console.error('导出HTML失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    // 重置状态
    resetState() {
      this.reports = []
      this.total = 0
      this.currentReport = null
      this.loading = false
      this.error = null
    },
  },
})
