import { describe, it, expect, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  router: { push: vi.fn() },
  route: { query: {} as Record<string, string> },
}))

vi.mock('vue-router', () => ({
  useRouter: () => mocks.router,
  useRoute: () => mocks.route,
}))

import { createSharedState } from '../createSharedState'

describe('createSharedState — 默认状态', () => {
  it('步骤、表单与分页取默认值', () => {
    const state = createSharedState()

    expect(state.currentStep.value).toBe(0)
    expect(state.formData.project_id).toBe('')
    expect(state.currentPage.value).toBe(1)
    expect(state.pageSize.value).toBe(10)
    expect(state.dbTotal.value).toBe(0)
  })

  it('进度与提示文案取默认值', () => {
    const state = createSharedState()

    expect(state.progress.value).toBe(0)
    expect(state.progressText.value).toBe('准备提取...')
    expect(state.progressInterval.value).toBeNull()
    expect(state.errorMessage.value).toBe('')
  })

  it('编辑表单默认优先级为中', () => {
    const state = createSharedState()

    expect(state.editForm).toEqual({
      id: 0,
      module: '',
      function: '',
      point: '',
      priority: 2,
    })
    expect(state.editingIndex.value).toBe(-1)
  })

  it('各类加载中与弹窗状态默认为 false', () => {
    const state = createSharedState()

    const flags = [
      state.extracting.value,
      state.saving.value,
      state.batchDeleting.value,
      state.deleting.value,
      state.savedFromDb.value,
      state.loadingTestPoints.value,
      state.dialogVisible.value,
      state.updating.value,
    ]
    expect(flags).toEqual(new Array(flags.length).fill(false))
  })

  it('注入 vue-router 的实例', () => {
    const state = createSharedState()

    expect(state.router).toBe(mocks.router)
    expect(state.route).toBe(mocks.route)
  })

  it('多次调用返回互不干扰的独立状态', () => {
    const first = createSharedState()
    const second = createSharedState()

    first.testPoints.value = [{ id: 1, module: 'm', point: 'p', priority: 1 }]
    first.currentStep.value = 2

    expect(second.testPoints.value).toEqual([])
    expect(second.currentStep.value).toBe(0)
  })
})
