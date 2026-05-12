import { defineStore } from 'pinia'
import type { TestCase } from '@/api/case'
import { testCaseApi } from '@/api/case'
import type { CasePageResponse } from '@/api/case'

export const useCaseStore = defineStore('case', {
  state: () => ({
    // 测试用例列表
    testCases: [] as TestCase[],
    // 生成进度
    generateProgress: 0,
    // 生成状态：idle, generating, success, failed
    generateStatus: 'idle' as 'idle' | 'generating' | 'success' | 'failed',
    // 生成消息
    generateMessage: '',
    // 当前项目ID
    currentProjectId: 0,
  }),

  getters: {
    // 按模块分组的测试用例
    testCasesByModule: (state) => {
      const grouped: Record<string, TestCase[]> = {}
      state.testCases.forEach((caseItem) => {
        if (!grouped[caseItem.module]) {
          grouped[caseItem.module] = []
        }
        grouped[caseItem.module].push(caseItem)
      })
      return grouped
    },

    // 按优先级分组的测试用例
    testCasesByPriority: (state) => {
      const grouped: Record<number, TestCase[]> = {
        1: [],
        2: [],
        3: [],
      }
      state.testCases.forEach((caseItem) => {
        const key = caseItem.priority as number
        if (!grouped[key]) {
          grouped[key] = []
        }
        grouped[key].push(caseItem)
      })
      return grouped
    },

    testCasesByStatus: (state) => {
      const grouped: Record<number, TestCase[]> = {
        0: [],
        1: [],
        2: [],
      }
      state.testCases.forEach((caseItem) => {
        if (caseItem.generate_status !== undefined && caseItem.generate_status !== null) {
          const key = caseItem.generate_status as number
          if (!grouped[key]) {
            grouped[key] = []
          }
          grouped[key].push(caseItem)
        }
      })
      return grouped
    },
  },

  actions: {
    // 生成测试用例
    async generateCases(projectId: number, pointIds?: number[]) {
      this.currentProjectId = projectId
      this.generateStatus = 'generating'
      this.generateProgress = 0
      this.generateMessage = '开始生成测试用例...'

      try {
        const generator = await testCaseApi.generate({
          project_id: projectId,
          point_ids: pointIds,
        })

        for await (const progress of generator) {
          this.generateProgress = progress.progress
          this.generateMessage = progress.message || '生成中...'
        }

        this.generateStatus = 'success'
        this.generateMessage = '生成完成'
        // 重新获取测试用例列表
        await this.fetchTestCases(projectId)
      } catch (error) {
        console.error('生成测试用例失败:', error)
        this.generateStatus = 'failed'
        this.generateMessage = '生成失败，请检查DeepSeek配置'
      }
    },

    // 重试生成失败的测试用例
    async retryFailedCases(projectId: number, caseIds?: number[]) {
      this.currentProjectId = projectId
      this.generateStatus = 'generating'
      this.generateProgress = 0
      this.generateMessage = '开始重试生成...'

      try {
        const generator = await testCaseApi.retry(projectId, {
          case_ids: caseIds,
        })

        for await (const progress of generator) {
          this.generateProgress = progress.progress
          this.generateMessage = progress.message || '重试中...'
        }

        this.generateStatus = 'success'
        this.generateMessage = '重试完成'
        // 重新获取测试用例列表
        await this.fetchTestCases(projectId)
      } catch (error) {
        console.error('重试生成失败:', error)
        this.generateStatus = 'failed'
        this.generateMessage = '重试失败，请检查DeepSeek配置'
      }
    },

    async fetchTestCases(
      projectId: number,
      params?: {
        module?: string
        priority?: number
        generate_status?: number
      }
    ) {
      try {
        const allCases: TestCase[] = []
        let page = 1
        const pageSize = 100
        let hasMore = true
        const MAX_CASES = 5000

        while (hasMore) {
          const response: CasePageResponse = await testCaseApi.getCaseList({
            project_id: projectId,
            page: page,
            page_size: pageSize,
            ...params,
          })
          const items = response?.data?.items || []
          const total = response?.data?.total || 0

          allCases.push(...items)

          if (items.length < pageSize || allCases.length >= total || allCases.length >= MAX_CASES) {
            hasMore = false
          } else {
            page++
          }
        }

        this.testCases = allCases
        this.currentProjectId = projectId
      } catch (error) {
        console.error('获取测试用例失败:', error)
        this.testCases = []
      }
    },

    // 删除测试用例
    async deleteTestCase(caseId: number) {
      try {
        await testCaseApi.deleteCase(caseId)
        this.testCases = this.testCases.filter((caseItem) => caseItem.id !== caseId)
        return true
      } catch (error) {
        console.error('删除测试用例失败:', error)
        return false
      }
    },

    // 批量删除测试用例
    async batchDeleteTestCases(caseIds: number[]) {
      try {
        const result = await testCaseApi.batchDeleteCases(caseIds)
        // 从本地列表中移除已删除的用例
        this.testCases = this.testCases.filter((caseItem) => !caseIds.includes(caseItem.id))
        return result
      } catch (error) {
        console.error('批量删除测试用例失败:', error)
        throw error
      }
    },

    // 批量恢复测试用例（撤销删除）
    async batchRestoreTestCases(caseIds: number[]) {
      try {
        const result = await testCaseApi.batchRestoreCases(caseIds)
        // 恢复成功后重新获取用例列表
        await this.fetchTestCases(this.currentProjectId)
        return result
      } catch (error) {
        console.error('批量恢复测试用例失败:', error)
        throw error
      }
    },

    // 更新测试用例
    async updateTestCase(caseId: number, data: Partial<TestCase>) {
      try {
        const response = await testCaseApi.updateCase(
          caseId,
          data as Record<string, unknown> as Parameters<typeof testCaseApi.updateCase>[1]
        )
        await this.fetchTestCases(this.currentProjectId)
        return response
      } catch (error) {
        console.error('更新测试用例失败:', error)
        throw error
      }
    },

    // 复制测试用例
    async copyTestCase(caseId: number) {
      try {
        const caseItem = this.testCases.find((c) => c.id === caseId)
        if (!caseItem) throw new Error('用例不存在')
        const { id: _id, case_no: _case_no, create_time: _create_time, generate_status: _generate_status, ...copyData } = caseItem
        const { title, module, priority, case_type, precondition, steps, expected_result } =
          copyData
        await testCaseApi.createCase({
          project_id: this.currentProjectId,
          title,
          module,
          priority,
          case_type,
          precondition,
          steps,
          expected_result,
        })
        await this.fetchTestCases(this.currentProjectId)
      } catch (error) {
        console.error('复制测试用例失败:', error)
        throw error
      }
    },

    // 重置生成状态
    resetGenerateState() {
      this.generateProgress = 0
      this.generateStatus = 'idle'
      this.generateMessage = ''
    },
  },
})
