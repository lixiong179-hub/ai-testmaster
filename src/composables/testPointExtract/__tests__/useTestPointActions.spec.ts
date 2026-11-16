import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage } from 'element-plus'
import { mockCancel, mockConfirm, silenceConsole, silenceElMessage } from '@/test-utils'
import type { ExtractSharedState, TestPointItem } from '../types'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  extract: vi.fn(),
  getList: vi.fn(),
  batchSave: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  batchDelete: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
  useRoute: () => ({ query: {} }),
}))

vi.mock('@/api/testPoint', () => ({
  testPointApi: {
    extract: mocks.extract,
    getList: mocks.getList,
    batchSave: mocks.batchSave,
    update: mocks.update,
    delete: mocks.remove,
    batchDelete: mocks.batchDelete,
  },
}))

import { createSharedState } from '../createSharedState'
import { useTestPointActions } from '../useTestPointActions'

let state: ExtractSharedState
/** 与 useTestPointActions 形参签名对齐，避免 Mock 默认 any 返回类型不兼容 */
const loadSavedTestPoints = vi.fn<[number, number?], Promise<void>>()
let clearSelection: ReturnType<typeof vi.fn>
let actions: ReturnType<typeof useTestPointActions>

function makePoint(overrides: Partial<TestPointItem> = {}): TestPointItem {
  return { id: 1, module: '登录', point: '登录成功', priority: 2, ...overrides }
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  silenceConsole()
  mockConfirm()
  state = createSharedState()
  loadSavedTestPoints.mockResolvedValue(undefined)
  clearSelection = vi.fn()
  actions = useTestPointActions(state, { loadSavedTestPoints, clearSelection })
})

describe('useTestPointActions — 批量删除', () => {
  it('未选中测试点时提示', async () => {
    await actions.batchDeleteTestPoints()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择要删除的测试点')
  })

  it('未选项目时提示', async () => {
    state.selectedRows.value = [makePoint()]

    await actions.batchDeleteTestPoints()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
  })

  it('落库模式下确认删除后刷新列表', async () => {
    state.formData.project_id = 9
    state.savedFromDb.value = true
    state.currentPage.value = 2
    state.selectedRows.value = [makePoint({ id: 3 }), makePoint({ id: 4 })]
    mocks.batchDelete.mockResolvedValue({
      code: 200,
      data: { deleted_count: 2 },
      message: '',
    })

    await actions.batchDeleteTestPoints()

    expect(mocks.batchDelete).toHaveBeenCalledWith(9, [3, 4])
    expect(clearSelection).toHaveBeenCalledTimes(1)
    expect(loadSavedTestPoints).toHaveBeenCalledWith(9, 2)
    expect(ElMessage.success).toHaveBeenCalledWith('成功删除 2 个测试点')
    expect(state.batchDeleting.value).toBe(false)
  })

  it('本地模式下确认删除后从列表移除', async () => {
    state.formData.project_id = 9
    state.testPoints.value = [makePoint({ id: 3 }), makePoint({ id: 4 })]
    state.selectedRows.value = [makePoint({ id: 3 })]
    mocks.batchDelete.mockResolvedValue({
      code: 200,
      data: { deleted_count: 1 },
      message: '删除完成',
    })

    await actions.batchDeleteTestPoints()

    expect(state.testPoints.value.map((tp) => tp.id)).toEqual([4])
    expect(loadSavedTestPoints).not.toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('删除完成')
  })

  it('接口返回非 200 时提示错误', async () => {
    state.formData.project_id = 9
    state.selectedRows.value = [makePoint()]
    mocks.batchDelete.mockResolvedValue({ code: 500, message: '服务异常' })

    await actions.batchDeleteTestPoints()

    expect(ElMessage.error).toHaveBeenCalledWith('服务异常')
  })

  it('取消确认时不提示错误', async () => {
    state.formData.project_id = 9
    state.selectedRows.value = [makePoint()]
    mockCancel()

    await actions.batchDeleteTestPoints()

    expect(mocks.batchDelete).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('请求异常时使用接口 detail 提示', async () => {
    state.formData.project_id = 9
    state.selectedRows.value = [makePoint()]
    mocks.batchDelete.mockRejectedValue({ response: { data: { detail: '权限不足' } } })

    await actions.batchDeleteTestPoints()

    expect(ElMessage.error).toHaveBeenCalledWith('权限不足')
  })
})

describe('useTestPointActions — 编辑测试点', () => {
  it('回填编辑表单并打开弹窗', () => {
    state.testPoints.value = [makePoint({ id: 2 }), makePoint({ id: 7, module: '支付' })]

    actions.editTestPoint(state.testPoints.value[1])

    expect(state.editingIndex.value).toBe(1)
    expect(state.editForm).toMatchObject({ id: 7, module: '支付' })
    expect(state.dialogVisible.value).toBe(true)
  })

  it('缺少 function 与 priority 时使用默认值', () => {
    state.testPoints.value = [{ id: 3, module: '登录', point: '登录成功' } as TestPointItem]

    actions.editTestPoint(state.testPoints.value[0])

    expect(state.editForm.function).toBe('')
    expect(state.editForm.priority).toBe(2)
  })

  it('找不到对应行时下标为 -1', () => {
    state.testPoints.value = [makePoint({ id: 1 })]

    actions.editTestPoint(makePoint({ id: 99 }))

    expect(state.editingIndex.value).toBe(-1)
  })
})

describe('useTestPointActions — 保存编辑', () => {
  it('module 或 point 为空时提示', async () => {
    state.editForm.module = ''

    await actions.saveTestPoint()

    expect(ElMessage.warning).toHaveBeenCalledWith('请填写完整的测试点信息')
  })

  it('落库模式下调用更新接口并刷新', async () => {
    state.formData.project_id = 9
    state.savedFromDb.value = true
    state.currentPage.value = 2
    state.testPoints.value = [makePoint({ id: 7, ai_prompt: 'p' })]
    state.editingIndex.value = 0
    state.editForm.module = '登录'
    state.editForm.point = '登录成功（新）'
    mocks.update.mockResolvedValue({
      code: 200,
      data: { id: 7, module: '登录', point: '登录成功（新）', priority: 2 },
    })

    await actions.saveTestPoint()

    expect(mocks.update).toHaveBeenCalledWith(7, {
      project_id: 9,
      module: '登录',
      function: '',
      point: '登录成功（新）',
      priority: 2,
      ai_prompt: 'p',
    })
    expect(loadSavedTestPoints).toHaveBeenCalledWith(9, 2)
    expect(ElMessage.success).toHaveBeenCalledWith('测试点更新成功')
    expect(state.dialogVisible.value).toBe(false)
    expect(state.updating.value).toBe(false)
  })

  it('本地模式只更新内存中的行', async () => {
    state.testPoints.value = [makePoint({ id: 7 })]
    state.editingIndex.value = 0
    state.editForm.module = '支付'
    state.editForm.point = '支付成功'

    await actions.saveTestPoint()

    expect(state.testPoints.value[0]).toMatchObject({ module: '支付', point: '支付成功' })
    expect(ElMessage.success).toHaveBeenCalledWith('测试点更新成功（本地）')
    expect(mocks.update).not.toHaveBeenCalled()
  })

  it('接口返回非 200 时提示错误', async () => {
    state.formData.project_id = 9
    state.savedFromDb.value = true
    state.testPoints.value = [makePoint({ id: 7 })]
    state.editingIndex.value = 0
    state.editForm.module = '登录'
    state.editForm.point = '登录成功'
    mocks.update.mockResolvedValue({ code: 500, message: '更新失败' })

    await actions.saveTestPoint()

    expect(ElMessage.error).toHaveBeenCalledWith('更新失败')
  })

  it('下标越界时不修改数据但复位 updating', async () => {
    state.testPoints.value = []
    state.editingIndex.value = 3
    state.editForm.module = '登录'
    state.editForm.point = '登录成功'

    await actions.saveTestPoint()

    expect(state.updating.value).toBe(false)
    expect(state.dialogVisible.value).toBe(false)
  })

  it('请求异常时提示错误详情', async () => {
    state.formData.project_id = 9
    state.savedFromDb.value = true
    state.testPoints.value = [makePoint({ id: 7 })]
    state.editingIndex.value = 0
    state.editForm.module = '登录'
    state.editForm.point = '登录成功'
    mocks.update.mockRejectedValue(new Error('网关超时'))

    await actions.saveTestPoint()

    expect(ElMessage.error).toHaveBeenCalledWith('网关超时')
  })
})

describe('useTestPointActions — 单条删除', () => {
  it('未选项目时提示', async () => {
    await actions.deleteTestPoint(makePoint())

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
  })

  it('落库模式删除后按剩余总数回退页码', async () => {
    state.formData.project_id = 9
    state.savedFromDb.value = true
    state.currentPage.value = 3
    state.pageSize.value = 10
    state.dbTotal.value = 21
    mocks.remove.mockResolvedValue({ code: 200, message: '' })

    await actions.deleteTestPoint(makePoint({ id: 5 }))

    expect(mocks.remove).toHaveBeenCalledWith(5, 9)
    expect(loadSavedTestPoints).toHaveBeenCalledWith(9, 2)
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(state.deleting.value).toBe(false)
  })

  it('落库模式删除失败时提示接口信息', async () => {
    state.formData.project_id = 9
    state.savedFromDb.value = true
    mocks.remove.mockResolvedValue({ code: 500, message: '该测试点已生成用例' })

    await actions.deleteTestPoint(makePoint({ id: 5 }))

    expect(ElMessage.error).toHaveBeenCalledWith('该测试点已生成用例')
  })

  it('本地模式直接从列表移除', async () => {
    state.formData.project_id = 9
    state.testPoints.value = [makePoint({ id: 5 }), makePoint({ id: 6 })]

    await actions.deleteTestPoint(makePoint({ id: 5 }))

    expect(state.testPoints.value.map((tp) => tp.id)).toEqual([6])
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功（本地）')
  })

  it('本地下标不存在时不抛错', async () => {
    state.formData.project_id = 9
    state.testPoints.value = [makePoint({ id: 5 })]

    await actions.deleteTestPoint(makePoint({ id: 99 }))

    expect(state.testPoints.value).toHaveLength(1)
  })

  it('请求异常时提示错误详情', async () => {
    state.formData.project_id = 9
    state.savedFromDb.value = true
    mocks.remove.mockRejectedValue({ response: { data: { message: '数据库繁忙' } } })

    await actions.deleteTestPoint(makePoint({ id: 5 }))

    expect(ElMessage.error).toHaveBeenCalledWith('数据库繁忙')
  })
})

describe('useTestPointActions — 保存到数据库', () => {
  it('测试点为空时提示', async () => {
    await actions.saveToDatabase()

    expect(ElMessage.warning).toHaveBeenCalledWith('没有可保存的测试点')
  })

  it('未选项目时提示', async () => {
    state.testPoints.value = [makePoint()]

    await actions.saveToDatabase()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
  })

  it('优先使用所选资源的项目 ID，并按 _raw 提交', async () => {
    state.testPoints.value = [
      makePoint({ id: 1, _raw: { module: '登录', point: '登录成功', extra: 'x' } }),
      makePoint({ id: 2, module: '支付', point: '支付成功', priority: 1 }),
    ]
    state.selectedResource.value = { id: 5, project_id: 12 } as never
    mocks.batchSave.mockResolvedValue({ code: 200, message: '' })

    await actions.saveToDatabase()

    expect(mocks.batchSave).toHaveBeenCalledWith(12, [
      { module: '登录', point: '登录成功', extra: 'x' },
      { module: '支付', point: '支付成功', priority: 1 },
    ])
    expect(state.savedFromDb.value).toBe(true)
    expect(loadSavedTestPoints).toHaveBeenCalledWith(12)
    expect(ElMessage.success).toHaveBeenCalledWith('成功保存 2 个测试点')
    expect(state.saving.value).toBe(false)
  })

  it('过滤缺少 module 或 point 的无效数据', async () => {
    state.formData.project_id = 9
    state.testPoints.value = [makePoint({ module: '' }), makePoint({ id: 2 })]
    mocks.batchSave.mockResolvedValue({ code: 200, data: {} })

    await actions.saveToDatabase()

    expect(mocks.batchSave).toHaveBeenCalledWith(9, [
      { module: '登录', point: '登录成功', priority: 2 },
    ])
  })

  it('全部数据无效时提示且不请求接口', async () => {
    state.formData.project_id = 9
    state.testPoints.value = [makePoint({ point: '' })]

    await actions.saveToDatabase()

    expect(mocks.batchSave).not.toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalledWith('没有有效的测试点数据')
    expect(state.saving.value).toBe(false)
  })

  it('接口返回非 200 时提示失败', async () => {
    state.formData.project_id = 9
    state.testPoints.value = [makePoint()]
    mocks.batchSave.mockResolvedValue({ code: 500, message: '保存被拒绝' })

    await actions.saveToDatabase()

    expect(ElMessage.error).toHaveBeenCalledWith('保存被拒绝')
  })

  it('请求异常时兜底提示', async () => {
    state.formData.project_id = 9
    state.testPoints.value = [makePoint()]
    mocks.batchSave.mockRejectedValue(new Error(''))

    await actions.saveToDatabase()

    expect(ElMessage.error).toHaveBeenCalledWith('保存到数据库失败')
    expect(state.saving.value).toBe(false)
  })
})

describe('useTestPointActions — 跳转', () => {
  it('生成用例前校验测试点与项目', () => {
    actions.generateTestCases()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先提取或加载测试点')

    state.testPoints.value = [makePoint()]
    actions.generateTestCases()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('生成用例时携带测试点 ID 与资源信息', () => {
    state.formData.project_id = 9
    state.testPoints.value = [makePoint({ id: 1 }), makePoint({ id: 2 })]
    state.selectedResource.value = { id: 5, display_name: '需求.docx' } as never

    actions.generateTestCases()

    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/smart-generate',
      query: {
        project_id: '9',
        test_point_ids: '[1,2]',
        file_id: '5',
        filename: '需求.docx',
      },
    })
  })

  it('未选资源时跳转参数不含文件信息', () => {
    state.formData.project_id = 9
    state.testPoints.value = [makePoint({ id: 1 })]

    actions.generateTestCases()

    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/smart-generate',
      query: { project_id: '9', test_point_ids: '[1]' },
    })
  })

  it('跳转管理页携带 projectId，未选项目时不带', () => {
    actions.goToManagement()
    expect(mocks.push).toHaveBeenLastCalledWith({
      path: '/home/case/test-point-management',
      query: {},
    })

    state.formData.project_id = 9
    actions.goToManagement()
    expect(mocks.push).toHaveBeenLastCalledWith({
      path: '/home/case/test-point-management',
      query: { projectId: '9' },
    })
  })
})
