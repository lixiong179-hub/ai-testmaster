import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { mockTestCaseApi, mockBatchGenerateStream } = vi.hoisted(() => ({
  mockTestCaseApi: {
    getCaseList: vi.fn(),
    deleteCase: vi.fn(),
    batchDeleteCases: vi.fn(),
    batchRestoreCases: vi.fn(),
    updateCase: vi.fn(),
    createCase: vi.fn(),
  },
  mockBatchGenerateStream: vi.fn(),
}))

vi.mock('@/api/case', () => ({ testCaseApi: mockTestCaseApi }))
vi.mock('@/api/testPoint', () => ({
  testPointApi: { batchGenerateStream: mockBatchGenerateStream },
}))

import { useCaseStore } from '../case'
import type { TestCase } from '@/api/case'

function makeCase(overrides: Partial<TestCase> = {}): TestCase {
  return {
    id: 1,
    project_id: 10,
    module: '登录',
    title: '登录成功',
    priority: 1,
    generate_status: 1,
    ...overrides,
  } as TestCase
}

function pageResponse(items: TestCase[], total: number) {
  return { data: { items, total } }
}

describe('useCaseStore — getters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('testCasesByModule 按模块分组', () => {
    const store = useCaseStore()
    store.testCases = [
      makeCase({ id: 1, module: '登录' }),
      makeCase({ id: 2, module: '登录' }),
      makeCase({ id: 3, module: '下单' }),
    ]

    const grouped = store.testCasesByModule

    expect(Object.keys(grouped).sort()).toEqual(['下单', '登录'])
    expect(grouped['登录']).toHaveLength(2)
  })

  it('testCasesByPriority 预置 1/2/3 并对未知优先级补键', () => {
    const store = useCaseStore()
    store.testCases = [
      makeCase({ id: 1, priority: 1 }),
      makeCase({ id: 2, priority: 3 }),
      makeCase({ id: 3, priority: 9 as never }),
    ]

    const grouped = store.testCasesByPriority

    expect(grouped[1]).toHaveLength(1)
    expect(grouped[2]).toHaveLength(0)
    expect(grouped[3]).toHaveLength(1)
    expect(grouped[9]).toHaveLength(1)
  })

  it('testCasesByStatus 跳过未定义状态', () => {
    const store = useCaseStore()
    store.testCases = [
      makeCase({ id: 1, generate_status: 0 }),
      makeCase({ id: 2, generate_status: 2 }),
      makeCase({ id: 3, generate_status: undefined }),
    ]

    const grouped = store.testCasesByStatus

    expect(grouped[0]).toHaveLength(1)
    expect(grouped[1]).toHaveLength(0)
    expect(grouped[2]).toHaveLength(1)
  })
})

describe('useCaseStore — generateCases', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('逐个消费进度事件后置 success 并刷新列表', async () => {
    const store = useCaseStore()
    mockBatchGenerateStream.mockResolvedValue(
      (async function* () {
        yield { progress: 50, message: '生成中' }
        yield { progress: 100, message: '完成' }
      })()
    )
    mockTestCaseApi.getCaseList.mockResolvedValue(pageResponse([makeCase()], 1))

    await store.generateCases(10, [1, 2])

    expect(store.currentProjectId).toBe(10)
    expect(store.generateProgress).toBe(100)
    expect(store.generateStatus).toBe('success')
    expect(store.generateMessage).toBe('生成完成')
    expect(mockTestCaseApi.getCaseList).toHaveBeenCalled()
  })

  it('未指定测试点时给出自动加载提示', async () => {
    const store = useCaseStore()
    mockBatchGenerateStream.mockResolvedValue(
      (async function* () {
        yield { progress: 100, message: '完成' }
      })()
    )
    mockTestCaseApi.getCaseList.mockResolvedValue(pageResponse([], 0))

    await store.generateCases(10, [Number.NaN as number])

    expect(mockBatchGenerateStream).toHaveBeenCalledWith({ project_id: 10, test_point_ids: [] })
  })

  it('命中「没有找到测试点」警告时置 failed', async () => {
    const store = useCaseStore()
    mockBatchGenerateStream.mockResolvedValue(
      (async function* () {
        yield { progress: 10, status: 'warning', message: '没有找到测试点' }
      })()
    )

    await store.generateCases(10, [1])

    expect(store.generateStatus).toBe('failed')
    expect(store.generateMessage).toBe('没有找到测试点')
    expect(mockTestCaseApi.getCaseList).not.toHaveBeenCalled()
  })

  it('事件 status=error 时同样置 failed', async () => {
    const store = useCaseStore()
    mockBatchGenerateStream.mockResolvedValue(
      (async function* () {
        yield { progress: 10, status: 'error', message: '模型异常' }
      })()
    )

    await store.generateCases(10, [1])

    expect(store.generateStatus).toBe('failed')
    expect(store.generateMessage).toBe('模型异常')
  })

  it('抛出异常时置 failed 并提示配置问题', async () => {
    const store = useCaseStore()
    mockBatchGenerateStream.mockRejectedValue(new Error('boom'))

    await store.generateCases(10, [1])

    expect(store.generateStatus).toBe('failed')
    expect(store.generateMessage).toBe('生成失败，请检查 DeepSeek 配置')
  })
})

describe('useCaseStore — retryFailedCases', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('无 caseIds 时提示未提供重试接口', async () => {
    const store = useCaseStore()
    await store.retryFailedCases(10)
    expect(store.generateMessage).toBe('当前后端未提供重试生成接口')
    expect(store.generateProgress).toBe(100)
  })

  it('有 caseIds 时提示按失败用例重试接口缺失', async () => {
    const store = useCaseStore()
    await store.retryFailedCases(10, [1, 2])
    expect(store.generateMessage).toBe('当前后端未提供按失败用例重试生成接口')
  })
})

describe('useCaseStore — fetchTestCases', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('不足一页即停止，并累计全部用例', async () => {
    const store = useCaseStore()
    mockTestCaseApi.getCaseList.mockResolvedValueOnce(pageResponse([makeCase({ id: 1 })], 1))

    await store.fetchTestCases(10)

    expect(mockTestCaseApi.getCaseList).toHaveBeenCalledTimes(1)
    expect(store.testCases).toHaveLength(1)
    expect(store.currentProjectId).toBe(10)
  })

  it('满页且未达 total 时继续翻页', async () => {
    const store = useCaseStore()
    const firstPage = Array.from({ length: 100 }, (_, i) => makeCase({ id: i + 1 }))
    mockTestCaseApi.getCaseList
      .mockResolvedValueOnce(pageResponse(firstPage, 101))
      .mockResolvedValueOnce(pageResponse([makeCase({ id: 101 })], 101))

    await store.fetchTestCases(10)

    expect(mockTestCaseApi.getCaseList).toHaveBeenCalledTimes(2)
    expect(store.testCases).toHaveLength(101)
  })

  it('查询参数透传到接口', async () => {
    const store = useCaseStore()
    mockTestCaseApi.getCaseList.mockResolvedValueOnce(pageResponse([], 0))

    await store.fetchTestCases(10, { module: '登录', priority: 1, generate_status: 1 })

    expect(mockTestCaseApi.getCaseList).toHaveBeenCalledWith(
      expect.objectContaining({ project_id: 10, module: '登录', priority: 1, generate_status: 1 })
    )
  })

  it('异常时清空列表', async () => {
    const store = useCaseStore()
    store.testCases = [makeCase()]
    mockTestCaseApi.getCaseList.mockRejectedValueOnce(new Error('boom'))

    await store.fetchTestCases(10)

    expect(store.testCases).toEqual([])
  })
})

describe('useCaseStore — 增删改复制', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('deleteTestCase 成功时从列表移除并返回 true', async () => {
    const store = useCaseStore()
    store.currentProjectId = 10
    store.testCases = [makeCase({ id: 1 }), makeCase({ id: 2 })]
    mockTestCaseApi.deleteCase.mockResolvedValueOnce(undefined)

    const ok = await store.deleteTestCase(1)

    expect(ok).toBe(true)
    expect(mockTestCaseApi.deleteCase).toHaveBeenCalledWith(1, 10)
    expect(store.testCases.map((c) => c.id)).toEqual([2])
  })

  it('deleteTestCase 失败时返回 false 且保留列表', async () => {
    const store = useCaseStore()
    store.testCases = [makeCase({ id: 1 })]
    mockTestCaseApi.deleteCase.mockRejectedValueOnce(new Error('boom'))

    const ok = await store.deleteTestCase(1)

    expect(ok).toBe(false)
    expect(store.testCases).toHaveLength(1)
  })

  it('batchDeleteTestCases 成功时移除命中项', async () => {
    const store = useCaseStore()
    store.currentProjectId = 10
    store.testCases = [makeCase({ id: 1 }), makeCase({ id: 2 }), makeCase({ id: 3 })]
    mockTestCaseApi.batchDeleteCases.mockResolvedValueOnce({ deleted: 2 })

    const result = await store.batchDeleteTestCases([1, 3])

    expect(result).toEqual({ deleted: 2 })
    expect(store.testCases.map((c) => c.id)).toEqual([2])
  })

  it('batchDeleteTestCases 失败时向上抛出', async () => {
    const store = useCaseStore()
    mockTestCaseApi.batchDeleteCases.mockRejectedValueOnce(new Error('500'))

    await expect(store.batchDeleteTestCases([1])).rejects.toThrow('500')
  })

  it('batchRestoreTestCases 成功后重新拉取列表', async () => {
    const store = useCaseStore()
    store.currentProjectId = 10
    mockTestCaseApi.batchRestoreCases.mockResolvedValueOnce({ restored: 1 })
    mockTestCaseApi.getCaseList.mockResolvedValueOnce(pageResponse([makeCase({ id: 5 })], 1))

    const result = await store.batchRestoreTestCases([5])

    expect(result).toEqual({ restored: 1 })
    expect(mockTestCaseApi.getCaseList).toHaveBeenCalled()
    expect(store.testCases.map((c) => c.id)).toEqual([5])
  })

  it('updateTestCase 更新后刷新列表', async () => {
    const store = useCaseStore()
    store.currentProjectId = 10
    mockTestCaseApi.updateCase.mockResolvedValueOnce({ id: 1 })
    mockTestCaseApi.getCaseList.mockResolvedValueOnce(pageResponse([makeCase({ id: 1 })], 1))

    const response = await store.updateTestCase(1, { title: '新标题' })

    expect(response).toEqual({ id: 1 })
    expect(mockTestCaseApi.updateCase).toHaveBeenCalledWith(1, { title: '新标题' })
    expect(store.testCases).toHaveLength(1)
  })

  it('copyTestCase 用例不存在时抛错', async () => {
    const store = useCaseStore()
    await expect(store.copyTestCase(99)).rejects.toThrow('用例不存在')
  })

  it('copyTestCase 复制时剔除 id/case_no 等系统字段', async () => {
    const store = useCaseStore()
    store.currentProjectId = 10
    store.testCases = [
      makeCase({
        id: 1,
        case_no: 'CASE-1',
        create_time: '2026-01-01',
        generate_status: 1,
        title: '标题',
        module: 'M',
        priority: 1,
        case_type: '功能测试',
        precondition: 'P',
        steps: [] as never,
        expected_result: 'E',
      } as never),
    ]
    mockTestCaseApi.createCase.mockResolvedValueOnce({ id: 2 })
    mockTestCaseApi.getCaseList.mockResolvedValueOnce(pageResponse([], 0))

    await store.copyTestCase(1)

    expect(mockTestCaseApi.createCase).toHaveBeenCalledWith({
      project_id: 10,
      title: '标题',
      module: 'M',
      priority: 1,
      case_type: '功能测试',
      precondition: 'P',
      steps: [],
      expected_result: 'E',
    })
  })

  it('resetGenerateState 复位进度与状态', () => {
    const store = useCaseStore()
    store.generateProgress = 80
    store.generateStatus = 'failed'
    store.generateMessage = 'boom'

    store.resetGenerateState()

    expect(store.generateProgress).toBe(0)
    expect(store.generateStatus).toBe('idle')
    expect(store.generateMessage).toBe('')
  })
})
