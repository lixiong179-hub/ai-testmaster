import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createGenerateState, type GenerateState } from '../state'
import { createGenerateComputed, type GenerateComputed } from '../computed'
import { createSaveActions } from '../saveActions'
import { createTestPointActions } from '../testPointActions'
import { TEST_POINT_CACHE_MAX } from '../types'

const { mockMessage, mockCaseApi, mockGetList } = vi.hoisted(() => ({
  mockMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() },
  mockCaseApi: { createCase: vi.fn(), updateCase: vi.fn() },
  mockGetList: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage: mockMessage }))
vi.mock('@/api/case', () => ({ default: mockCaseApi }))
vi.mock('@/api/testPoint', () => ({
  testPointApi: { getList: mockGetList },
}))

function setupSave() {
  const state: GenerateState = createGenerateState()
  const computed: GenerateComputed = createGenerateComputed(state)
  const actions = createSaveActions(state, computed)
  return { state, computed, actions }
}

describe('createSaveActions — payload 组装', () => {
  it('buildStepsPayload：步骤号缺省补序，param 优先取 input_value', () => {
    const { actions } = setupSave()

    const payload = actions.buildStepsPayload([
      { action: '点击', input_value: 'admin', param: 'ignored' } as never,
      { step: 5, action: '输入', param: 'p' } as never,
    ])

    expect(payload[0]).toMatchObject({ step: '1', action: '点击', param: 'admin' })
    expect(payload[1]).toMatchObject({ step: '5', param: 'p' })
    expect(payload[0].ui_elements).toEqual([])
  })

  it('buildStepsPayload：undefined 返回空数组', () => {
    const { actions } = setupSave()
    expect(actions.buildStepsPayload(undefined)).toEqual([])
  })

  it('buildCaseCreatePayload：空字段走默认值，空步骤兜底一步', () => {
    const { state, actions } = setupSave()
    state.formData.project_id = 12

    const payload = actions.buildCaseCreatePayload({})

    expect(payload).toMatchObject({
      project_id: 12,
      title: '未命名测试用例',
      module: '默认模块',
      precondition: '系统已通过配置自动登录至目标页面',
      expected_result: '操作成功',
      priority: 2,
      generate_status: 1,
    })
    expect(payload.steps).toEqual([{ step: 1, action: '执行测试', param: '预期结果正常' }])
    expect(payload.case_no).toContain('CASE12-')
  })

  it('buildCaseCreatePayload：priority 越界归一，test_category 回退 case_type', () => {
    const { state, actions } = setupSave()
    state.formData.project_id = ''

    expect(actions.buildCaseCreatePayload({ priority: 9 }).priority).toBe(3)
    expect(actions.buildCaseCreatePayload({ priority: 0 }).priority).toBe(1)
    expect(actions.buildCaseCreatePayload({ case_type: 'ui_automation' }).test_category).toBe(
      'ui_automation'
    )
  })
})

type SavableCase = Parameters<ReturnType<typeof createSaveActions>['saveSingleCaseToDb']>[0]

describe('createSaveActions — 单条入库与保存', () => {
  let state: GenerateState
  let actions: ReturnType<typeof createSaveActions>

  beforeEach(() => {
    vi.clearAllMocks()
    ;({ state, actions } = setupSave())
  })

  it('saveSingleCaseToDb 成功时回写 _saved/_dbId', async () => {
    mockCaseApi.createCase.mockResolvedValueOnce({ id: 77 })
    const target = { title: 'A' } as SavableCase

    const ok = await actions.saveSingleCaseToDb(target)

    expect(ok).toBe(true)
    expect(target._saved).toBe(true)
    expect(target._dbId).toBe(77)
  })

  it('saveSingleCaseToDb 失败时返回 false 且不改状态', async () => {
    mockCaseApi.createCase.mockRejectedValueOnce(new Error('500'))
    const target = { title: 'A' } as SavableCase

    const ok = await actions.saveSingleCaseToDb(target)

    expect(ok).toBe(false)
    expect(target._saved).toBeUndefined()
  })

  it('handleSaveCase：无用例/生成失败/未选项目三种拦截', async () => {
    await actions.handleSaveCase()
    expect(mockMessage.warning).toHaveBeenCalledWith('没有可保存的用例')

    state.generatedCases.value = [{ title: 'A', _error: 'boom' }] as never
    await actions.handleSaveCase()
    expect(mockMessage.warning).toHaveBeenCalledWith('该用例生成失败，无法保存，请重新生成')

    state.generatedCases.value = [{ title: 'A' }] as never
    await actions.handleSaveCase()
    expect(mockMessage.warning).toHaveBeenCalledWith('请先选择项目')
  })

  it('handleSaveCase：已入库用例走 updateCase', async () => {
    state.formData.project_id = 10
    state.generatedCases.value = [{ title: 'A', _dbId: 55, steps: [] }] as never
    state.currentCaseIndex.value = 0
    mockCaseApi.updateCase.mockResolvedValueOnce(undefined)

    await actions.handleSaveCase()

    expect(mockCaseApi.updateCase).toHaveBeenCalledWith(55, expect.objectContaining({ title: 'A' }))
    expect(mockCaseApi.createCase).not.toHaveBeenCalled()
    expect(mockMessage.success).toHaveBeenCalledWith('"A" 更新成功')
    expect(state.saving.value).toBe(false)
  })

  it('handleSaveCase：未入库用例走 createCase 并回填数据库 ID', async () => {
    state.formData.project_id = 10
    state.generatedCases.value = [{ title: 'A', steps: [] }] as never
    state.currentCaseIndex.value = 0
    mockCaseApi.createCase.mockResolvedValueOnce({ id: 91 })

    await actions.handleSaveCase()

    expect(state.generatedCases.value[0]).toMatchObject({ _saved: true, _dbId: 91 })
    expect(mockMessage.success).toHaveBeenCalledWith('"A" 保存成功')
  })

  it('handleSaveCase：编辑态保存后把编辑字段回写到当前用例', async () => {
    state.formData.project_id = 10
    state.generatedCases.value = [{ title: '旧', module: 'M0', _dbId: 55 }] as never
    state.currentCaseIndex.value = 0
    state.isEditingResult.value = true
    state.editingCase.value = {
      title: '新标题',
      module: 'M1',
      case_type: '功能测试',
      precondition: '',
      expected_result: '成功',
      priority: 1,
      steps: [],
    }
    mockCaseApi.updateCase.mockResolvedValueOnce(undefined)

    await actions.handleSaveCase()

    expect(state.generatedCases.value[0]).toMatchObject({ title: '新标题', module: 'M1' })
    expect(state.isEditingResult.value).toBe(false)
  })

  it('handleSaveCase：接口报错时优先展示后端 detail', async () => {
    state.formData.project_id = 10
    state.generatedCases.value = [{ title: 'A' }] as never
    state.currentCaseIndex.value = 0
    mockCaseApi.createCase.mockRejectedValueOnce({
      response: { data: { detail: '标题重复' } },
    })

    await actions.handleSaveCase()

    expect(mockMessage.error).toHaveBeenCalledWith('标题重复')
  })
})

describe('createTestPointActions — 列表加载与缓存', () => {
  let state: GenerateState
  let actions: ReturnType<typeof createTestPointActions>

  beforeEach(() => {
    vi.clearAllMocks()
    state = createGenerateState()
    actions = createTestPointActions(state)
  })

  it('未选择项目时不发请求', async () => {
    await actions.loadTestPoints()
    expect(mockGetList).not.toHaveBeenCalled()
  })

  it('首页加载：替换列表、写入缓存与全集 ID，并累加重挂载键', async () => {
    state.formData.project_id = 1
    state.testPointPageSize.value = 2
    mockGetList.mockResolvedValueOnce({
      items: [
        { id: 1, module: 'M', point: 'P' },
        { id: 2, module: 'M', point: 'P2' },
      ],
      total: 2,
    })

    await actions.loadTestPoints(1, false, true)

    expect(state.testPoints.value).toHaveLength(2)
    expect(state.testPointCache.get(1)).toMatchObject({ id: 1 })
    expect(state.testPointAllIds.value).toEqual([1, 2])
    expect(state.testPointTotal.value).toBe(2)
    expect(state.testPointPage.value).toBe(1)
    expect(state.testPointSelectKey.value).toBe(1)
  })

  it('追加加载：page>1 时拼接且不重置 selectKey', async () => {
    state.formData.project_id = 1
    state.testPoints.value = [{ id: 1 }] as never
    mockGetList.mockResolvedValueOnce({ items: [{ id: 2, module: 'M', point: 'P' }], total: 5 })

    await actions.loadTestPoints(2, true, false)

    expect(state.testPoints.value.map((p) => p.id)).toEqual([1, 2])
    expect(state.testPointSelectKey.value).toBe(0)
  })

  it('首页且总数 ≤200 时补拉全量 ID', async () => {
    state.formData.project_id = 1
    mockGetList
      .mockResolvedValueOnce({ items: [{ id: 1, module: 'M', point: 'P' }], total: 3 })
      .mockResolvedValueOnce({
        items: [
          { id: 1, module: 'M', point: 'P' },
          { id: 2, module: 'M', point: 'P' },
          { id: 3, module: 'M', point: 'P' },
        ],
        total: 3,
      })

    await actions.loadTestPoints(1, false, true)

    expect(mockGetList).toHaveBeenCalledTimes(2)
    expect(state.testPointAllIds.value).toEqual([1, 2, 3])
  })

  it('缓存超过上限时按插入顺序裁剪', async () => {
    state.formData.project_id = 1
    for (let i = 0; i < TEST_POINT_CACHE_MAX; i++) {
      state.testPointCache.set(i + 1, { id: i + 1 } as never)
    }
    mockGetList.mockResolvedValueOnce({
      items: [{ id: 9999, module: 'M', point: 'P' }],
      total: TEST_POINT_CACHE_MAX + 1,
    })

    await actions.loadTestPoints(1, false, false)

    expect(state.testPointCache.size).toBe(TEST_POINT_CACHE_MAX)
    expect(state.testPointCache.has(1)).toBe(false)
    expect(state.testPointCache.has(9999)).toBe(true)
  })

  it('接口异常时不抛出，仅记录日志', async () => {
    state.formData.project_id = 1
    mockGetList.mockRejectedValueOnce(new Error('boom'))
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await expect(actions.loadTestPoints()).resolves.toBeUndefined()

    spy.mockRestore()
  })
})

describe('createTestPointActions — 选择与文案', () => {
  let state: GenerateState
  let actions: ReturnType<typeof createTestPointActions>

  beforeEach(() => {
    vi.clearAllMocks()
    state = createGenerateState()
    actions = createTestPointActions(state)
  })

  it('handleSourceFileChange 清空分页与选择', () => {
    state.formData.project_id = 1
    state.formData.test_point_ids = [1]
    state.testPoints.value = [{ id: 1 }] as never
    state.testPointAllIds.value = [1]
    state.testPointTotal.value = 1
    state.testPointCache.set(1, { id: 1 } as never)

    actions.handleSourceFileChange()

    expect(state.formData.test_point_ids).toEqual([])
    expect(state.testPoints.value).toEqual([])
    expect(state.testPointAllIds.value).toEqual([])
    expect(state.testPointTotal.value).toBe(0)
    expect(state.testPointPage.value).toBe(1)
    expect(state.testPointCache.size).toBe(0)
    expect(state.testPointSelectKey.value).toBe(1)
  })

  it('handleSourceFileChange 未选项目时不做处理', () => {
    actions.handleSourceFileChange()
    expect(state.testPointSelectKey.value).toBe(0)
  })

  it('全选/取消全选/单条增删', () => {
    state.testPointAllIds.value = [1, 2, 3]

    actions.selectAllTestPoints()
    expect(state.formData.test_point_ids).toEqual([1, 2, 3])

    actions.deselectAllTestPoints()
    expect(state.formData.test_point_ids).toEqual([])

    actions.addTestPoint(1)
    actions.addTestPoint(1)
    expect(state.formData.test_point_ids).toEqual([1])

    actions.removeTestPoint(1)
    actions.removeTestPoint(9)
    expect(state.formData.test_point_ids).toEqual([])
  })

  it('selectCurrentPageAll 仅追加当前页未选项', () => {
    state.testPoints.value = [{ id: 1 }, { id: 2 }] as never
    state.formData.test_point_ids = [2, 3]

    actions.selectCurrentPageAll()

    expect(state.formData.test_point_ids).toEqual([2, 3, 1])
  })

  it('getTestPointLabel：缓存优先、回退列表、缺失占位', () => {
    state.testPointCache.set(1, { id: 1, module: '登录', point: '成功' } as never)
    state.testPoints.value = [{ id: 2, module: '下单', point: '完成' }] as never

    expect(actions.getTestPointLabel(1)).toBe('登录 - 成功')
    expect(actions.getTestPointLabel(2)).toBe('下单 - 完成')
    expect(actions.getTestPointLabel(3)).toBe('测试点 #3')
  })

  it('goToTestPointPage 在加载中时跳过，结束后复位标记', async () => {
    state.formData.project_id = 1
    state.isLoadingMore.value = true
    await actions.goToTestPointPage(2)
    expect(mockGetList).not.toHaveBeenCalled()

    state.isLoadingMore.value = false
    mockGetList.mockResolvedValueOnce({ items: [], total: 0 })
    await actions.goToTestPointPage(2)

    expect(mockGetList).toHaveBeenCalledTimes(1)
    expect(state.isLoadingMore.value).toBe(false)
  })
})
