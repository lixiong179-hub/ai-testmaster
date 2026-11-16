import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage } from 'element-plus'
import { createComposableHost, silenceElMessage } from '@/test-utils'
import type { TestCase } from '@/types/testCase'

const mocks = vi.hoisted(() => ({
  getSupplementData: vi.fn(),
  supplementCase: vi.fn(),
}))

vi.mock('@/api/case', () => ({
  caseApi: {
    getSupplementData: mocks.getSupplementData,
    supplementCase: mocks.supplementCase,
  },
}))

import { useSupplementForm } from '../useSupplementForm'

type Ctx = ReturnType<typeof useSupplementForm>

const CASE_ID = 11
const PROJECT_ID = 22

const host = createComposableHost<Ctx>(() => useSupplementForm(CASE_ID, PROJECT_ID))
let ctx: Ctx

function makeCase(overrides: Partial<TestCase> = {}): TestCase {
  return {
    id: CASE_ID,
    case_no: 'CASE-001',
    project_id: PROJECT_ID,
    module: '登录',
    title: '正常登录',
    priority: 1,
    case_type: 'manual',
    ...overrides,
  }
}

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mocks.getSupplementData.mockResolvedValue({
    test_case: makeCase(),
    inferred_capabilities: [
      { name: '能力A', description: '描述A' },
      { name: '能力B', description: '描述B' },
    ],
    questions: [{ question: '问题A' }, { question: '问题B' }],
  })
  mocks.supplementCase.mockResolvedValue({
    change_summary: [{ field: 'precondition', old_value: '', new_value: '已登录' }],
  })
})

describe('useSupplementForm — 初始化加载', () => {
  it('挂载后按 caseId 拉取补充数据并映射为可编辑状态', async () => {
    await mountHost()

    expect(mocks.getSupplementData).toHaveBeenCalledWith(CASE_ID)
    expect(ctx.originalCase.value).toEqual(makeCase())
    expect(ctx.inferredCapabilities.value).toEqual([
      { name: '能力A', description: '描述A', selected: false },
      { name: '能力B', description: '描述B', selected: false },
    ])
    expect(ctx.questions.value).toEqual([
      { question: '问题A', answer: '' },
      { question: '问题B', answer: '' },
    ])
    expect(ctx.loading.value).toBe(false)
  })

  it('响应缺少能力与问题时置为空数组', async () => {
    mocks.getSupplementData.mockResolvedValue({ test_case: makeCase() })
    await mountHost()

    expect(ctx.inferredCapabilities.value).toEqual([])
    expect(ctx.questions.value).toEqual([])
    expect(ctx.hasInferredCapabilities.value).toBe(false)
  })

  it('加载失败时提示错误详情并复位 loading', async () => {
    mocks.getSupplementData.mockRejectedValue(new Error('接口超时'))
    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('接口超时')
    expect(ctx.loading.value).toBe(false)
  })

  it('加载失败且非 Error 时使用兜底文案', async () => {
    mocks.getSupplementData.mockRejectedValue('boom')
    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('加载补充数据失败')
  })

  it('可手动重新拉取数据', async () => {
    await mountHost()
    mocks.getSupplementData.mockClear()

    await ctx.fetchSupplementData()

    expect(mocks.getSupplementData).toHaveBeenCalledWith(CASE_ID)
  })
})

describe('useSupplementForm — 推断能力选择', () => {
  it('toggleInferredCapability 切换单项选中状态', async () => {
    await mountHost()

    ctx.toggleInferredCapability(0)
    expect(ctx.inferredCapabilities.value[0].selected).toBe(true)
    expect(ctx.selectedInferredCount.value).toBe(1)

    ctx.toggleInferredCapability(0)
    expect(ctx.inferredCapabilities.value[0].selected).toBe(false)
    expect(ctx.selectedInferredCount.value).toBe(0)
  })

  it('selectAllInferred 全选、deselectAllInferred 全不选', async () => {
    await mountHost()

    ctx.selectAllInferred()
    expect(ctx.selectedInferredCount.value).toBe(2)

    ctx.deselectAllInferred()
    expect(ctx.selectedInferredCount.value).toBe(0)
  })

  it('hasInferredCapabilities 仅在存在推断能力时为真', async () => {
    await mountHost()
    expect(ctx.hasInferredCapabilities.value).toBe(true)

    ctx.reset()
    expect(ctx.hasInferredCapabilities.value).toBe(false)
  })
})

describe('useSupplementForm — 自定义能力', () => {
  it('addCustomCapability 追加空行，removeCustomCapability 按下标删除', async () => {
    await mountHost()

    ctx.addCustomCapability()
    ctx.addCustomCapability()
    expect(ctx.customCapabilities.value).toHaveLength(2)

    ctx.customCapabilities.value[0].name = '自定义能力'
    ctx.removeCustomCapability(0)
    expect(ctx.customCapabilities.value).toHaveLength(1)
    expect(ctx.customCapabilities.value[0].name).toBe('')
  })

  it('hasCustomCapabilities 忽略名称为空白的能力', async () => {
    await mountHost()
    ctx.addCustomCapability()
    expect(ctx.hasCustomCapabilities.value).toBe(false)

    ctx.customCapabilities.value[0].name = '   '
    expect(ctx.hasCustomCapabilities.value).toBe(false)

    ctx.customCapabilities.value[0].name = ' 新能力 '
    expect(ctx.hasCustomCapabilities.value).toBe(true)
  })
})

describe('useSupplementForm — 问题回答', () => {
  it('hasQuestions 忽略未回答的问题', async () => {
    await mountHost()
    expect(ctx.hasQuestions.value).toBe(false)

    ctx.questions.value[0].answer = '   '
    expect(ctx.hasQuestions.value).toBe(false)

    ctx.questions.value[1].answer = '是'
    expect(ctx.hasQuestions.value).toBe(true)
  })
})

describe('useSupplementForm — 可提交判定', () => {
  it('没有任何补充内容时不可提交', async () => {
    await mountHost()

    expect(ctx.canSubmit.value).toBe(false)
  })

  it('选中推断能力后可提交', async () => {
    await mountHost()

    ctx.toggleInferredCapability(1)

    expect(ctx.canSubmit.value).toBe(true)
  })

  it('填写自定义能力名称后可提交', async () => {
    await mountHost()
    ctx.addCustomCapability()
    ctx.customCapabilities.value[0].name = '自定义'

    expect(ctx.canSubmit.value).toBe(true)
  })

  it('回答问题后可提交', async () => {
    await mountHost()
    ctx.questions.value[1].answer = '需要先登录'

    expect(ctx.canSubmit.value).toBe(true)
  })
})

describe('useSupplementForm — 提交', () => {
  it('不可提交时仅提示，不调用接口', async () => {
    await mountHost()

    await ctx.handleSubmit()

    expect(ElMessage.warning).toHaveBeenCalledWith('请至少选择一项补充内容')
    expect(mocks.supplementCase).not.toHaveBeenCalled()
    expect(ctx.saving.value).toBe(false)
  })

  it('提交成功后写入结果与变更摘要并提示', async () => {
    await mountHost()
    ctx.toggleInferredCapability(0)
    ctx.addCustomCapability()
    ctx.customCapabilities.value[0] = { name: '自定义能力', description: '说明' }
    ctx.questions.value[0].answer = '需要前置登录'

    await ctx.handleSubmit()

    expect(mocks.supplementCase).toHaveBeenCalledWith(CASE_ID, {
      project_id: PROJECT_ID,
      inferred_capabilities: [{ name: '能力A', description: '描述A' }],
      custom_capabilities: [{ name: '自定义能力', description: '说明' }],
      questions: [{ question: '问题A', answer: '需要前置登录' }],
    })
    expect(ctx.showResult.value).toBe(true)
    expect(ctx.changeSummary.value).toEqual([
      { field: 'precondition', old_value: '', new_value: '已登录' },
    ])
    expect(ctx.supplementResult.value).toEqual({
      change_summary: [{ field: 'precondition', old_value: '', new_value: '已登录' }],
    })
    expect(ElMessage.success).toHaveBeenCalledWith('补充完成')
    expect(ctx.saving.value).toBe(false)
  })

  it('提交时过滤空白自定义能力与未回答的问题', async () => {
    await mountHost()
    ctx.toggleInferredCapability(0)
    ctx.addCustomCapability()
    ctx.customCapabilities.value[0].name = '   '

    await ctx.handleSubmit()

    expect(mocks.supplementCase).toHaveBeenCalledWith(CASE_ID, {
      project_id: PROJECT_ID,
      inferred_capabilities: [{ name: '能力A', description: '描述A' }],
      custom_capabilities: [],
      questions: [],
    })
  })

  it('提交响应缺少 change_summary 时摘要为空数组', async () => {
    mocks.supplementCase.mockResolvedValue({})
    await mountHost()
    ctx.toggleInferredCapability(0)

    await ctx.handleSubmit()

    expect(ctx.changeSummary.value).toEqual([])
    expect(ctx.showResult.value).toBe(true)
  })

  it('提交失败时提示错误详情并复位 saving', async () => {
    mocks.supplementCase.mockRejectedValue(new Error('保存失败'))
    await mountHost()
    ctx.toggleInferredCapability(0)

    await ctx.handleSubmit()

    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
    expect(ctx.showResult.value).toBe(false)
    expect(ctx.saving.value).toBe(false)
  })

  it('提交失败且非 Error 时使用兜底文案', async () => {
    mocks.supplementCase.mockRejectedValue(undefined)
    await mountHost()
    ctx.toggleInferredCapability(0)

    await ctx.handleSubmit()

    expect(ElMessage.error).toHaveBeenCalledWith('补充失败')
  })
})

describe('useSupplementForm — 重置', () => {
  it('reset 清空能力、问题、结果并回到推断页签', async () => {
    await mountHost()
    ctx.activeTab.value = 'custom'
    ctx.toggleInferredCapability(0)
    ctx.addCustomCapability()
    ctx.questions.value[0].answer = '有'
    ctx.showResult.value = true
    ctx.changeSummary.value = [{ field: 'f', old_value: 'a', new_value: 'b' }]

    ctx.reset()

    expect(ctx.inferredCapabilities.value).toEqual([])
    expect(ctx.customCapabilities.value).toEqual([])
    expect(ctx.questions.value).toEqual([])
    expect(ctx.supplementResult.value).toBeNull()
    expect(ctx.showResult.value).toBe(false)
    expect(ctx.changeSummary.value).toEqual([])
    expect(ctx.activeTab.value).toBe('inferred')
    expect(ctx.canSubmit.value).toBe(false)
  })
})
