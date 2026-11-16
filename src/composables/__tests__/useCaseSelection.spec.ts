import { describe, it, expect, beforeEach, vi } from 'vitest'
import { computed, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useCaseSelection } from '../useCaseSelection'
import type { PaginationState } from '../useCaseFilter'
import type { useCaseStore } from '@/store/case'
import type { TestCase } from '@/api/case'
import { mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'

function testCase(id: number): TestCase {
  return { id, title: `用例${id}` } as TestCase
}

function setup(pageIds: number[] = [1, 2, 3], allIds: number[] = [1, 2, 3, 4, 5]) {
  const pageSource = ref<TestCase[]>(pageIds.map(testCase))
  const allSource = ref<TestCase[]>(allIds.map(testCase))
  const caseStore = {
    batchRestoreTestCases: vi.fn(),
    batchDeleteTestCases: vi.fn(),
  }
  const pagination = ref<PaginationState>({ currentPage: 1, pageSize: 10 })
  const loading = ref(false)

  const api = useCaseSelection({
    caseStore: caseStore as unknown as ReturnType<typeof useCaseStore>,
    paginatedTestCases: computed(() => pageSource.value),
    filteredTestCases: computed(() => allSource.value),
    pagination,
    loading,
  })

  return { api, caseStore, pagination, loading, pageSource, allSource }
}

describe('useCaseSelection — 选择状态', () => {
  it('空页时全选与半选均为 false', () => {
    const { api } = setup([], [])

    expect(api.isAllSelected.value).toBe(false)
    expect(api.isIndeterminate.value).toBe(false)
  })

  it('全部选中时 isAllSelected 为 true、半选为 false', () => {
    const { api } = setup()
    api.selectedCases.value = [1, 2, 3]

    expect(api.isAllSelected.value).toBe(true)
    expect(api.isIndeterminate.value).toBe(false)
  })

  it('部分选中时半选为 true', () => {
    const { api } = setup()
    api.selectedCases.value = [1]

    expect(api.isAllSelected.value).toBe(false)
    expect(api.isIndeterminate.value).toBe(true)
  })

  it('跨页选中不影响当前页全选判定', () => {
    const { api } = setup()
    api.selectedCases.value = [1, 2, 3, 99]

    expect(api.isAllSelected.value).toBe(true)
    expect(api.isIndeterminate.value).toBe(false)
  })

  it('isSelected 基于 Set 查询', () => {
    const { api } = setup()
    api.selectedCases.value = [2]

    expect(api.isSelected(2)).toBe(true)
    expect(api.isSelected(1)).toBe(false)
  })

  it('单选添加与取消，重复添加不产生重复项', () => {
    const { api } = setup()

    api.handleCaseSelect(true, 5)
    api.handleCaseSelect(true, 5)
    expect(api.selectedCases.value).toEqual([5])

    api.handleCaseSelect(false, 5)
    expect(api.selectedCases.value).toEqual([])
  })

  it('全选当前页只影响本页，取消全选保留其它页选择', () => {
    const { api } = setup()
    api.selectedCases.value = [99]

    api.handleSelectAll(true)
    expect(api.selectedCases.value).toEqual([99, 1, 2, 3])

    api.handleSelectAll(false)
    expect(api.selectedCases.value).toEqual([99])
  })

  it('全选所有页覆盖筛选结果', () => {
    const { api } = setup()

    api.handleSelectAllPages()

    expect(api.selectedCases.value).toEqual([1, 2, 3, 4, 5])
  })

  it('clearSelection 清空选择', () => {
    const { api } = setup()
    api.selectedCases.value = [1, 2]

    api.clearSelection()

    expect(api.selectedCases.value).toEqual([])
  })
})

describe('useCaseSelection — 批量删除', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    silenceElMessage('warning')
    silenceElMessage('error')
    silenceElMessage('success')
  })

  it('未选中时提示且不发起请求', () => {
    const { api, caseStore } = setup()

    api.handleBatchDelete()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择要删除的用例')
    expect(caseStore.batchDeleteTestCases).not.toHaveBeenCalled()
  })

  it('确认后删除成功：记录可撤销ID、清空选择并提示', async () => {
    mockConfirm()
    const { api, caseStore, loading } = setup()
    caseStore.batchDeleteTestCases.mockResolvedValue({
      success_count: 2,
      fail_count: 0,
      not_found_count: 0,
      deleted_ids: [1, 2],
    })
    api.selectedCases.value = [1, 2]

    api.handleBatchDelete()
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      '确定要删除选中的 2 个测试用例吗？',
      '批量删除确认',
      expect.objectContaining({ type: 'warning' })
    )
    expect(caseStore.batchDeleteTestCases).toHaveBeenCalledWith([1, 2])
    expect(api.recentlyDeletedIds.value).toEqual([1, 2])
    expect(api.selectedCases.value).toEqual([])
    expect(ElMessage.success).toHaveBeenCalledWith({
      message: '成功删除 2 个测试用例',
      duration: 5000,
      showClose: true,
    })
    expect(loading.value).toBe(false)
  })

  it('部分失败时弹出结果详情', async () => {
    mockConfirm()
    const alertSpy = vi.spyOn(ElMessageBox, 'alert').mockResolvedValue('confirm' as never)
    const { api, caseStore } = setup()
    caseStore.batchDeleteTestCases.mockResolvedValue({
      success_count: 1,
      fail_count: 1,
      not_found_count: 2,
      deleted_ids: [1],
    })
    api.selectedCases.value = [1, 2]

    api.handleBatchDelete()
    await flushPromises()

    expect(alertSpy).toHaveBeenCalledWith(
      expect.stringContaining('成功：1 个'),
      '删除结果',
      expect.objectContaining({ dangerouslyUseHTMLString: true, type: 'warning' })
    )
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('删除后当前页为空且非首页时回退一页', async () => {
    mockConfirm()
    const { api, caseStore, pagination, pageSource } = setup()
    caseStore.batchDeleteTestCases.mockResolvedValue({
      success_count: 1,
      fail_count: 0,
      not_found_count: 0,
      deleted_ids: [1],
    })
    api.selectedCases.value = [1]
    pagination.value.currentPage = 3
    pageSource.value = []

    api.handleBatchDelete()
    await flushPromises()

    expect(pagination.value.currentPage).toBe(2)
  })

  it('取消确认时不请求也不更新状态', async () => {
    mockCancel()
    const { api, caseStore } = setup()
    api.selectedCases.value = [1]

    api.handleBatchDelete()
    await flushPromises()

    expect(caseStore.batchDeleteTestCases).not.toHaveBeenCalled()
    expect(api.selectedCases.value).toEqual([1])
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('请求异常时提示失败并复位 loading', async () => {
    mockConfirm()
    const { api, caseStore, loading } = setup()
    caseStore.batchDeleteTestCases.mockRejectedValue(new Error('boom'))
    api.selectedCases.value = [1]

    api.handleBatchDelete()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('批量删除失败，请稍后重试')
    expect(loading.value).toBe(false)
  })
})

describe('useCaseSelection — 撤销删除', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    silenceElMessage('warning')
    silenceElMessage('error')
    silenceElMessage('success')
  })

  it('无可撤销记录时提示', async () => {
    const { api } = setup()

    await api.handleUndoDelete()

    expect(ElMessage.warning).toHaveBeenCalledWith('没有可撤销的删除操作')
  })

  it('全部恢复成功时提示成功并清空记录', async () => {
    const { api, caseStore } = setup()
    caseStore.batchRestoreTestCases.mockResolvedValue({
      success_count: 3,
      fail_count: 0,
      not_found_count: 0,
    })
    api.recentlyDeletedIds.value = [1, 2, 3]

    await api.handleUndoDelete()

    expect(caseStore.batchRestoreTestCases).toHaveBeenCalledWith([1, 2, 3])
    expect(ElMessage.success).toHaveBeenCalledWith('成功恢复 3 个测试用例')
    expect(api.recentlyDeletedIds.value).toEqual([])
  })

  it('部分失败时给出明细提示', async () => {
    const { api, caseStore } = setup()
    caseStore.batchRestoreTestCases.mockResolvedValue({
      success_count: 1,
      fail_count: 1,
      not_found_count: 1,
    })
    api.recentlyDeletedIds.value = [1, 2, 3]

    await api.handleUndoDelete()

    expect(ElMessage.warning).toHaveBeenCalledWith('恢复完成：成功 1 个，失败 1 个，未找到 1 个')
  })

  it('恢复异常时提示失败并复位 loading', async () => {
    const { api, caseStore, loading } = setup()
    caseStore.batchRestoreTestCases.mockRejectedValue(new Error('boom'))
    api.recentlyDeletedIds.value = [1]

    await api.handleUndoDelete()

    expect(ElMessage.error).toHaveBeenCalledWith('撤销删除失败，请稍后重试')
    expect(loading.value).toBe(false)
  })
})
