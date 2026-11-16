import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { createComposableHost, mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  getProjects: vi.fn(),
  getQualityRules: vi.fn(),
  updateQualityRule: vi.fn(),
}))

vi.mock('@/api/project', () => ({
  ProjectAPI: { getProjects: mocks.getProjects },
  default: { getProjects: mocks.getProjects },
}))

vi.mock('@/api/qualityRule', () => ({
  qualityRuleApi: {
    getQualityRules: mocks.getQualityRules,
    updateQualityRule: mocks.updateQualityRule,
  },
}))

import { useQualityRule } from '../useQualityRule'

type Ctx = ReturnType<typeof useQualityRule>
type Rule = Ctx['rules']['value'][number]

const host = createComposableHost<Ctx>(() => useQualityRule())
let ctx: Ctx

function makeRule(overrides: Partial<Rule> = {}): Rule {
  return {
    rule_key: 'min_case_count',
    rule_value: 10,
    default_value: 10,
    value_type: 'number',
    description: '最少用例数',
    ...overrides,
  } as Rule
}

function makeFormRef(valid = true) {
  return {
    validate: vi.fn((cb: (v: boolean) => void) => {
      cb(valid)
      return Promise.resolve(valid)
    }),
    resetFields: vi.fn(),
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
  mockConfirm()
  mocks.getProjects.mockResolvedValue({ data: { items: [{ id: 9, name: '项目A' }] } })
  mocks.getQualityRules.mockResolvedValue({ data: [makeRule()] })
  mocks.updateQualityRule.mockResolvedValue({ data: {} })
})

describe('useQualityRule — 初始化加载', () => {
  it('挂载后拉取项目、自动选中首个项目并加载规则', async () => {
    await mountHost()

    expect(mocks.getProjects).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(ctx.selectedProjectId.value).toBe(9)
    expect(mocks.getQualityRules).toHaveBeenCalledWith(9)
    expect(ctx.rules.value).toHaveLength(1)
    expect(ctx.loading.value).toBe(false)
  })

  it('没有项目时不选中也不加载规则', async () => {
    mocks.getProjects.mockResolvedValue({ data: { items: [] } })

    await mountHost()

    expect(ctx.selectedProjectId.value).toBeNull()
    expect(mocks.getQualityRules).not.toHaveBeenCalled()
  })

  it('项目加载失败时提示 Error 信息', async () => {
    mocks.getProjects.mockRejectedValue(new Error('项目服务异常'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('项目服务异常')
  })

  it('项目加载失败且非 Error 时使用兜底文案', async () => {
    mocks.getProjects.mockRejectedValue(undefined)

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取项目列表失败')
  })

  it('规则接口返回非数组时置为空数组', async () => {
    mocks.getQualityRules.mockResolvedValue({ data: null })

    await mountHost()

    expect(ctx.rules.value).toEqual([])
  })

  it('规则加载失败时提示 Error 信息并复位 loading', async () => {
    mocks.getQualityRules.mockRejectedValue(new Error('规则服务异常'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('规则服务异常')
    expect(ctx.loading.value).toBe(false)
  })

  it('规则加载失败且非 Error 时使用兜底文案', async () => {
    mocks.getQualityRules.mockRejectedValue('boom')

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取质量规则失败')
  })

  it('切换项目后重新加载规则', async () => {
    await mountHost()
    mocks.getQualityRules.mockClear()
    ctx.selectedProjectId.value = 10

    ctx.handleProjectChange()
    await flushPromises()

    expect(mocks.getQualityRules).toHaveBeenCalledWith(10)
  })

  it('未选项目时加载规则会清空列表且不请求', async () => {
    await mountHost()
    ctx.selectedProjectId.value = null
    mocks.getQualityRules.mockClear()

    ctx.handleProjectChange()
    await flushPromises()

    expect(ctx.rules.value).toEqual([])
    expect(mocks.getQualityRules).not.toHaveBeenCalled()
  })
})

describe('useQualityRule — 值展示与编辑回填', () => {
  it('保存时按规则类型提交对应值', async () => {
    await mountHost()
    ctx.formRef.value = makeFormRef()

    ctx.openEditDialog(makeRule({ value_type: 'boolean', rule_value: true }) as never)
    await ctx.saveRule()
    await flushPromises()
    expect(mocks.updateQualityRule).toHaveBeenLastCalledWith(9, {
      rule_key: 'min_case_count',
      rule_value: true,
    })

    ctx.openEditDialog(makeRule({ value_type: 'number', rule_value: 42 }) as never)
    await ctx.saveRule()
    await flushPromises()
    expect(mocks.updateQualityRule).toHaveBeenLastCalledWith(9, {
      rule_key: 'min_case_count',
      rule_value: 42,
    })

    ctx.openEditDialog(makeRule({ value_type: 'enum', rule_value: 'strict' }) as never)
    await ctx.saveRule()
    await flushPromises()
    expect(mocks.updateQualityRule).toHaveBeenLastCalledWith(9, {
      rule_key: 'min_case_count',
      rule_value: 'strict',
    })
  })

  it('formatRuleValue 布尔转是/否，其余转字符串', async () => {
    await mountHost()

    expect(ctx.formatRuleValue(true)).toBe('是')
    expect(ctx.formatRuleValue(false)).toBe('否')
    expect(ctx.formatRuleValue(12)).toBe('12')
    expect(ctx.formatRuleValue('strict')).toBe('strict')
  })

  it('isDefaultValue 比较当前值与默认值', async () => {
    await mountHost()

    expect(ctx.isDefaultValue(makeRule({ rule_value: 10, default_value: 10 }))).toBe(true)
    expect(ctx.isDefaultValue(makeRule({ rule_value: 5, default_value: 10 }))).toBe(false)
  })

  it('打开编辑弹窗按类型填充表单', async () => {
    await mountHost()

    ctx.openEditDialog(makeRule({ value_type: 'boolean', rule_value: true }) as never)
    expect(ctx.formData.rule_key).toBe('min_case_count')
    expect(ctx.formData.rule_value_bool).toBe(true)
    expect(ctx.dialogVisible.value).toBe(true)

    ctx.openEditDialog(makeRule({ value_type: 'number', rule_value: 7 }) as never)
    expect(ctx.formData.rule_value_num).toBe(7)

    ctx.openEditDialog(makeRule({ value_type: 'enum', rule_value: 'strict' }) as never)
    expect(ctx.formData.rule_value_str).toBe('strict')
  })
})

describe('useQualityRule — 保存', () => {
  it('表单实例未就绪时直接返回', async () => {
    await mountHost()

    await ctx.saveRule()

    expect(mocks.updateQualityRule).not.toHaveBeenCalled()
  })

  it('校验失败时不提交', async () => {
    await mountHost()
    ctx.formRef.value = makeFormRef(false)

    await ctx.saveRule()

    expect(mocks.updateQualityRule).not.toHaveBeenCalled()
  })

  it('未选项目时不提交', async () => {
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.selectedProjectId.value = null

    await ctx.saveRule()
    await flushPromises()

    expect(mocks.updateQualityRule).not.toHaveBeenCalled()
  })

  it('保存成功后关闭弹窗并刷新', async () => {
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.openEditDialog(makeRule({ value_type: 'number', rule_value: 20 }) as never)
    mocks.getQualityRules.mockClear()

    await ctx.saveRule()
    await flushPromises()

    expect(mocks.updateQualityRule).toHaveBeenCalledWith(9, {
      rule_key: 'min_case_count',
      rule_value: 20,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('规则更新成功')
    expect(ctx.dialogVisible.value).toBe(false)
    expect(mocks.getQualityRules).toHaveBeenCalledTimes(1)
  })

  it('保存失败时提示 Error 信息', async () => {
    mocks.updateQualityRule.mockRejectedValue(new Error('规则值非法'))
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.openEditDialog(makeRule() as never)

    await ctx.saveRule()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('规则值非法')
  })

  it('保存失败且非 Error 时使用兜底文案', async () => {
    mocks.updateQualityRule.mockRejectedValue(undefined)
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.openEditDialog(makeRule() as never)

    await ctx.saveRule()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('更新规则失败')
  })
})

describe('useQualityRule — 恢复默认值', () => {
  it('确认后按默认值提交并刷新', async () => {
    await mountHost()
    mocks.getQualityRules.mockClear()

    ctx.resetToDefault(makeRule({ rule_value: 5, default_value: 10 }))
    await flushPromises()

    expect(mocks.updateQualityRule).toHaveBeenCalledWith(9, {
      rule_key: 'min_case_count',
      rule_value: 10,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('已恢复默认值')
    expect(mocks.getQualityRules).toHaveBeenCalledTimes(1)
  })

  it('取消恢复默认时不调用接口', async () => {
    await mountHost()
    mockCancel()

    ctx.resetToDefault(makeRule())
    await flushPromises()

    expect(mocks.updateQualityRule).not.toHaveBeenCalled()
  })

  it('未选项目时确认后不提交', async () => {
    await mountHost()
    ctx.selectedProjectId.value = null

    ctx.resetToDefault(makeRule())
    await flushPromises()

    expect(mocks.updateQualityRule).not.toHaveBeenCalled()
  })

  it('恢复失败时提示 Error 信息', async () => {
    mocks.updateQualityRule.mockRejectedValue(new Error('恢复失败原因'))
    await mountHost()

    ctx.resetToDefault(makeRule())
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('恢复失败原因')
  })

  it('恢复失败且非 Error 时使用兜底文案', async () => {
    mocks.updateQualityRule.mockRejectedValue('boom')
    await mountHost()

    ctx.resetToDefault(makeRule())
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('恢复默认值失败')
  })
})
