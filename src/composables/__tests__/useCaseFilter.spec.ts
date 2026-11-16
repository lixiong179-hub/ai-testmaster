import { describe, it, expect, vi } from 'vitest'
import { reactive, ref } from 'vue'
import { useCaseFilter, type PaginationState } from '../useCaseFilter'
import type { useCaseStore } from '@/store/case'
import type { TestCase } from '@/api/case'

function testCase(partial: Partial<TestCase> & { id: number }): TestCase {
  return {
    title: '',
    module: '',
    priority: 2,
    case_type: 'manual',
    ...partial,
  } as TestCase
}

const CASES: TestCase[] = [
  testCase({
    id: 1,
    title: '登录成功',
    module: '登录',
    priority: 1,
    case_type: 'manual',
    generate_status: 1,
  }),
  testCase({
    id: 2,
    title: '登录失败',
    module: '登录',
    priority: 2,
    case_type: 'ui_automation',
    generate_status: 2,
  }),
  testCase({
    id: 3,
    title: '下单支付',
    module: '订单',
    priority: 3,
    case_type: 'api_automation',
    generate_status: 1,
  }),
  testCase({
    id: 4,
    title: '订单取消',
    module: '订单',
    priority: 1,
    case_type: '功能',
    generate_status: 2,
  }),
  testCase({
    id: 5,
    title: '空模块用例',
    module: '',
    priority: 2,
    case_type: 'UI',
    generate_status: 1,
  }),
]

function setup(cases: TestCase[] = CASES, projectId: number | null = 9) {
  const caseStore = reactive({
    testCases: [...cases],
    fetchTestCases: vi.fn(),
  }) as unknown as ReturnType<typeof useCaseStore>
  const pagination = ref<PaginationState>({ currentPage: 3, pageSize: 20 })
  const selectedProjectId = ref<number | null>(projectId)

  const api = useCaseFilter({ caseStore, pagination, selectedProjectId })
  return { api, caseStore, pagination, selectedProjectId }
}

describe('useCaseFilter — 统计口径', () => {
  it('按 generate_status 统计成功/失败', () => {
    const { api } = setup()

    expect(api.successCount.value).toBe(3)
    expect(api.failedCount.value).toBe(2)
  })

  it('按 case_type 别名归并人工/UI/接口三类', () => {
    const { api } = setup()

    expect(api.manualCount.value).toBe(2)
    expect(api.uiCount.value).toBe(2)
    expect(api.apiCount.value).toBe(1)
  })

  it('按优先级 1/2/3 统计', () => {
    const { api } = setup()

    expect(api.highPriorityCount.value).toBe(2)
    expect(api.mediumPriorityCount.value).toBe(2)
    expect(api.lowPriorityCount.value).toBe(1)
  })

  it('统计随 store 数据变化而更新', () => {
    const { api, caseStore } = setup()

    caseStore.testCases.push(
      testCase({ id: 6, title: '新增', module: '报表', priority: 1, generate_status: 1 })
    )

    expect(api.successCount.value).toBe(4)
    expect(api.highPriorityCount.value).toBe(3)
  })

  it('模块列表去重、忽略空值并升序', () => {
    const { api } = setup()

    // Array.prototype.sort 默认按 UTF-16 码位升序：登(U+767B) < 订(U+8BA2)
    expect(api.modules.value).toEqual(['登录', '订单'])
  })
})

describe('useCaseFilter — 筛选结果', () => {
  it('默认返回全量', () => {
    const { api } = setup()

    expect(api.filteredTestCases.value).toHaveLength(5)
    expect(api.hasActiveFilter.value).toBe(false)
  })

  it('按需求文件过滤', () => {
    const cases = [
      { ...testCase({ id: 1, title: 'a' }), requirement_file_id: 11 },
      { ...testCase({ id: 2, title: 'b' }), requirement_file_id: 22 },
    ]
    const { api } = setup(cases)

    api.selectedRequirementFileId.value = 22

    expect(api.filteredTestCases.value.map((c) => c.id)).toEqual([2])
    expect(api.hasActiveFilter.value).toBe(true)
  })

  it('按生命周期过滤且缺省视为 active', () => {
    const cases = [
      testCase({ id: 1, title: 'a', lifecycle_status: 'archived' }),
      testCase({ id: 2, title: 'b' }),
      testCase({ id: 3, title: 'c', lifecycle_status: 'active' }),
    ]
    const { api } = setup(cases)

    api.filter.value.lifecycle_status = ['active']

    expect(api.filteredTestCases.value.map((c) => c.id)).toEqual([2, 3])
  })

  it('按模块 / 优先级 / 类型组合过滤', () => {
    const { api } = setup()

    api.filter.value.module = '订单'
    api.filter.value.priority = 1

    expect(api.filteredTestCases.value.map((c) => c.id)).toEqual([4])

    api.filter.value.module = ''
    api.filter.value.priority = null
    api.filter.value.case_type = 'ui_automation'

    expect(api.filteredTestCases.value.map((c) => c.id)).toEqual([2])
  })

  it('关键词匹配标题与编号且忽略大小写', () => {
    const cases = [
      testCase({ id: 1, title: 'Login Success', case_no: 'TC-001' }),
      testCase({ id: 2, title: '下单', case_no: 'TC-login-9' }),
      testCase({ id: 3, title: '无关', case_no: 'TC-003' }),
    ]
    const { api } = setup(cases)

    api.filter.value.keyword = 'LOGIN'

    expect(api.filteredTestCases.value.map((c) => c.id)).toEqual([1, 2])
  })

  it('各维度单独设置都会触发 hasActiveFilter', () => {
    const { api } = setup()

    api.filter.value.module = '订单'
    expect(api.hasActiveFilter.value).toBe(true)

    api.filter.value.module = ''
    api.filter.value.priority = 0
    expect(api.hasActiveFilter.value).toBe(true)
  })
})

describe('useCaseFilter — 筛选操作', () => {
  it('筛选变更重置到第一页', () => {
    const { api, pagination } = setup()

    api.handleFilterChange()

    expect(pagination.value.currentPage).toBe(1)
  })

  it('统计卡筛选 null 时清空全部条件', () => {
    const { api, pagination } = setup()
    api.filter.value = {
      module: '订单',
      priority: 1,
      case_type: 'manual',
      keyword: 'x',
      lifecycle_status: ['active'],
    }
    api.selectedRequirementFileId.value = 5

    api.applyStatsCardFilter(null)

    expect(api.filter.value).toEqual({
      module: '',
      priority: null,
      case_type: '',
      keyword: '',
      lifecycle_status: [],
    })
    expect(pagination.value.currentPage).toBe(1)
    // 统计卡只清筛选表单，不动需求文件筛选
    expect(api.selectedRequirementFileId.value).toBe(5)
  })

  it('统计卡筛选指定类型时保留其它条件', () => {
    const { api, pagination } = setup()
    api.filter.value = { ...api.filter.value, module: '订单', keyword: '支付' }

    api.applyStatsCardFilter('api_automation')

    expect(api.filter.value).toMatchObject({
      module: '订单',
      keyword: '支付',
      case_type: 'api_automation',
    })
    expect(pagination.value.currentPage).toBe(1)
  })

  it('resetFilter 清空全部条件并重拉当前项目用例', () => {
    const { api, caseStore, pagination } = setup()
    api.filter.value = { ...api.filter.value, module: '订单' }
    api.selectedRequirementFileId.value = 5

    api.resetFilter()

    expect(api.filter.value).toEqual({
      module: '',
      priority: null,
      case_type: '',
      keyword: '',
      lifecycle_status: [],
    })
    expect(api.selectedRequirementFileId.value).toBeNull()
    expect(pagination.value.currentPage).toBe(1)
    expect(caseStore.fetchTestCases).toHaveBeenCalledWith(9)
  })

  it('未选项目时 resetFilter 不触发请求', () => {
    const { api, caseStore } = setup(CASES, null)

    api.resetFilter()

    expect(caseStore.fetchTestCases).not.toHaveBeenCalled()
  })
})
