import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick, reactive } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createComposableHost,
  deferred,
  mockCancel,
  mockConfirm,
  silenceElMessage,
} from '@/test-utils'
import type { TestData } from '@/api/testData'

const mocks = vi.hoisted(() => ({
  getByStepId: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  generate: vi.fn(),
  autoGenerate: vi.fn(),
}))

vi.mock('@/api/testData', () => ({
  testDataApi: {
    getByStepId: mocks.getByStepId,
    create: mocks.create,
    update: mocks.update,
    delete: mocks.remove,
    generate: mocks.generate,
    autoGenerate: mocks.autoGenerate,
  },
  dataTypeOptions: [
    { label: '文本', value: 'text' },
    { label: '数字', value: 'number' },
  ],
  generationRuleOptions: [
    { label: '随机生成', value: 'random' },
    { label: '固定值', value: 'fixed' },
  ],
  DataType: { TEXT: 'text' },
  GenerationRule: { RANDOM: 'random' },
}))

import { useTestDataEditor } from '../useTestDataEditor'

type Ctx = ReturnType<typeof useTestDataEditor>

let props: { stepId: number; stepAction?: string }
let emit: ReturnType<typeof vi.fn>
const host = createComposableHost<Ctx>(() => useTestDataEditor(props, emit))
let ctx: Ctx

async function mountHost(
  init: { stepId: number; stepAction?: string } = { stepId: 5, stepAction: '点击登录' }
) {
  props = reactive({ ...init })
  emit = vi.fn()
  await host.mount()
  ctx = host.ctx
}

function makeRow(over: Partial<TestData> = {}): TestData {
  return {
    id: 1,
    step_id: 5,
    field_name: 'username',
    field_type: 'text',
    data_value: null,
    generation_rule: 'random',
    rule_config: null,
    min_length: null,
    max_length: null,
    min_value: null,
    max_value: null,
    enum_values: null,
    description: '',
    is_required: true,
    sort_order: 0,
    ...over,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mockConfirm()
  mocks.getByStepId.mockResolvedValue({ step_id: 5, data_list: [makeRow()] })
  mocks.create.mockResolvedValue(makeRow({ id: 9, field_name: '新建字段' }))
  mocks.update.mockResolvedValue(makeRow({ field_name: '已更新' }))
  mocks.remove.mockResolvedValue({ success: true, message: 'ok' })
  mocks.generate.mockResolvedValue({ step_id: 5, generated_data: { username: 'alice' } })
  mocks.autoGenerate.mockResolvedValue({ success: true, count: 2, data_list: [] })
})

describe('useTestDataEditor — 加载', () => {
  it('挂载即按步骤拉取数据并回写更新事件', async () => {
    await mountHost()

    expect(mocks.getByStepId).toHaveBeenCalledWith(5)
    expect(ctx.testDataList.value).toHaveLength(1)
    expect(ctx.testDataList.value[0]).toMatchObject({ id: 1, isEditing: false })
    expect(emit).toHaveBeenCalledWith('update', ctx.testDataList.value)
    expect(ctx.loading.value).toBe(false)
  })

  it('stepId 为 0 时不请求', async () => {
    await mountHost({ stepId: 0 })

    expect(mocks.getByStepId).not.toHaveBeenCalled()
    expect(ctx.testDataList.value).toEqual([])
  })

  it('步骤切换时重新拉取并清空已生成数据', async () => {
    await mountHost()
    ctx.generatedData.value = { username: 'alice' }
    mocks.getByStepId.mockClear()

    props.stepId = 6
    await nextTick()
    await flushPromises()

    expect(mocks.getByStepId).toHaveBeenCalledWith(6)
    expect(ctx.generatedData.value).toEqual({})
  })

  it('加载失败时提示错误', async () => {
    mocks.getByStepId.mockRejectedValue(new Error('boom'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取测试数据失败')
    expect(ctx.loading.value).toBe(false)
  })
})

describe('useTestDataEditor — 行编辑', () => {
  it('新增行使用默认值并标记为新建', async () => {
    await mountHost()

    ctx.handleAdd()

    expect(ctx.testDataList.value).toHaveLength(2)
    expect(ctx.testDataList.value[1]).toMatchObject({
      id: 0,
      step_id: 5,
      field_name: '',
      field_type: 'text',
      generation_rule: 'random',
      is_required: true,
      sort_order: 1,
      isEditing: true,
      isNew: true,
    })
  })

  it('编辑行进入编辑态', async () => {
    await mountHost()

    ctx.handleEdit(ctx.testDataList.value[0])

    expect(ctx.testDataList.value[0].isEditing).toBe(true)
  })

  it('字段名为空时拒绝保存', async () => {
    await mountHost()
    const row = ctx.testDataList.value[0]
    row.field_name = ''

    await ctx.handleSave(row)

    expect(ElMessage.warning).toHaveBeenCalledWith('请输入字段名称')
    expect(mocks.create).not.toHaveBeenCalled()
    expect(mocks.update).not.toHaveBeenCalled()
  })

  it('新建行保存走创建接口', async () => {
    await mountHost()
    ctx.handleAdd()
    const row = ctx.testDataList.value[1]
    row.field_name = '新建字段'
    emit.mockClear()

    await ctx.handleSave(row)

    expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({ step_id: 5, field_name: '新建字段', field_type: 'text' })
    )
    expect(mocks.update).not.toHaveBeenCalled()
    expect(row.id).toBe(9)
    expect(row.isNew).toBe(false)
    expect(row.isEditing).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('创建成功')
    expect(emit).toHaveBeenCalledWith('update', ctx.testDataList.value)
  })

  it('已有行保存走更新接口', async () => {
    await mountHost()
    const row = ctx.testDataList.value[0]

    await ctx.handleSave(row)

    expect(mocks.update).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ field_name: 'username' })
    )
    expect(mocks.create).not.toHaveBeenCalled()
    expect(row.isEditing).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('更新成功')
  })

  it('保存失败时提示', async () => {
    mocks.create.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.handleAdd()
    const row = ctx.testDataList.value[1]
    row.field_name = '新建字段'

    await ctx.handleSave(row)

    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
  })

  it('取消新建行时移除该行', async () => {
    await mountHost()
    ctx.handleAdd()

    ctx.handleCancel(ctx.testDataList.value[1], 1)

    expect(ctx.testDataList.value).toHaveLength(1)
  })

  it('取消已有行时退出编辑态并重新拉取', async () => {
    await mountHost()
    const row = ctx.testDataList.value[0]
    row.isEditing = true
    mocks.getByStepId.mockClear()

    ctx.handleCancel(row, 0)
    await flushPromises()

    expect(row.isEditing).toBe(false)
    expect(mocks.getByStepId).toHaveBeenCalledTimes(1)
  })
})

describe('useTestDataEditor — 删除', () => {
  it('确认后删除并刷新', async () => {
    await mountHost()
    mocks.getByStepId.mockClear()

    await ctx.handleDelete(ctx.testDataList.value[0])

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mocks.remove).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(mocks.getByStepId).toHaveBeenCalledTimes(1)
  })

  it('取消删除时不提示错误', async () => {
    mockCancel()
    await mountHost()

    await ctx.handleDelete(ctx.testDataList.value[0])

    expect(mocks.remove).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('删除失败时提示', async () => {
    mocks.remove.mockRejectedValue(new Error('boom'))
    await mountHost()

    await ctx.handleDelete(ctx.testDataList.value[0])

    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })
})

describe('useTestDataEditor — 数据生成', () => {
  it('列表为空时提示无数据可生成', async () => {
    mocks.getByStepId.mockResolvedValue({ step_id: 5, data_list: [] })
    await mountHost()

    await ctx.handleGenerateAll()

    expect(ElMessage.warning).toHaveBeenCalledWith('没有测试数据可生成')
    expect(mocks.generate).not.toHaveBeenCalled()
  })

  it('全部生成成功后写入生成结果', async () => {
    await mountHost()

    await ctx.handleGenerateAll()

    expect(mocks.generate).toHaveBeenCalledWith(5)
    expect(ctx.generatedData.value).toEqual({ username: 'alice' })
    expect(ElMessage.success).toHaveBeenCalledWith('数据生成成功')
    expect(ctx.generating.value).toBe(false)
  })

  it('全部生成失败时提示', async () => {
    mocks.generate.mockRejectedValue(new Error('boom'))
    await mountHost()

    await ctx.handleGenerateAll()

    expect(ElMessage.error).toHaveBeenCalledWith('数据生成失败')
    expect(ctx.generating.value).toBe(false)
  })

  it('生成期间 generating 为 true', async () => {
    const pending = deferred<{ step_id: number; generated_data: Record<string, string> }>()
    mocks.generate.mockReturnValueOnce(pending.promise)
    await mountHost()

    const task = ctx.handleGenerateAll()
    expect(ctx.generating.value).toBe(true)

    pending.resolve({ step_id: 5, generated_data: {} })
    await task
    expect(ctx.generating.value).toBe(false)
  })

  it('缺少步骤操作描述时拒绝智能生成', async () => {
    await mountHost({ stepId: 5 })

    await ctx.handleAutoGenerate()

    expect(ElMessage.warning).toHaveBeenCalledWith('步骤操作描述为空，无法智能生成')
    expect(mocks.autoGenerate).not.toHaveBeenCalled()
  })

  it('智能生成有结果时刷新列表', async () => {
    await mountHost()
    mocks.getByStepId.mockClear()

    await ctx.handleAutoGenerate()

    expect(mocks.autoGenerate).toHaveBeenCalledWith(5, '点击登录')
    expect(ElMessage.success).toHaveBeenCalledWith('成功生成 2 个测试数据字段')
    expect(mocks.getByStepId).toHaveBeenCalledTimes(1)
    expect(ctx.autoGenerating.value).toBe(false)
  })

  it('智能生成无结果时给出提示且不刷新', async () => {
    mocks.autoGenerate.mockResolvedValue({ success: true, count: 0, data_list: [] })
    await mountHost()
    mocks.getByStepId.mockClear()

    await ctx.handleAutoGenerate()

    expect(ElMessage.info).toHaveBeenCalledWith('未识别到需要生成的测试数据')
    expect(mocks.getByStepId).not.toHaveBeenCalled()
  })

  it('智能生成失败时提示', async () => {
    mocks.autoGenerate.mockRejectedValue(new Error('boom'))
    await mountHost()

    await ctx.handleAutoGenerate()

    expect(ElMessage.error).toHaveBeenCalledWith('智能生成失败')
    expect(ctx.autoGenerating.value).toBe(false)
  })
})

describe('useTestDataEditor — 复制与展示映射', () => {
  it('复制生成结果到剪贴板', async () => {
    await mountHost()
    ctx.generatedData.value = { username: 'alice' }

    ctx.handleCopy()
    await flushPromises()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      JSON.stringify({ username: 'alice' }, null, 2)
    )
    expect(ElMessage.success).toHaveBeenCalledWith('已复制到剪贴板')
  })

  it('复制失败时提示', async () => {
    vi.mocked(navigator.clipboard.writeText).mockRejectedValueOnce(new Error('denied'))
    await mountHost()
    ctx.generatedData.value = { username: 'alice' }

    ctx.handleCopy()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('复制失败')
  })

  it('数据类型标签与标签色映射', async () => {
    await mountHost()

    expect(ctx.getDataTypeLabel('text')).toBe('文本')
    expect(ctx.getDataTypeLabel('unknown')).toBe('unknown')
    expect(ctx.getDataTypeTagType('email')).toBe('success')
    expect(ctx.getDataTypeTagType('number')).toBe('warning')
    expect(ctx.getDataTypeTagType('password')).toBe('danger')
    expect(ctx.getDataTypeTagType('unknown')).toBe('primary')
  })

  it('生成规则标签映射', async () => {
    await mountHost()

    expect(ctx.getGenerationRuleLabel('random')).toBe('随机生成')
    expect(ctx.getGenerationRuleLabel('custom')).toBe('custom')
  })
})
