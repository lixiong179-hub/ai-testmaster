import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage } from 'element-plus'

const mocks = vi.hoisted(() => ({
  getIterations: vi.fn(),
  createIteration: vi.fn(),
  updateIteration: vi.fn(),
  deleteIteration: vi.fn(),
}))

vi.mock('@/api/iteration', () => {
  const api = {
    getIterations: mocks.getIterations,
    createIteration: mocks.createIteration,
    updateIteration: mocks.updateIteration,
    deleteIteration: mocks.deleteIteration,
  }
  return { iterationApi: api, default: api }
})

import { createFormInstanceMock, silenceConsole, silenceElMessage } from '@/test-utils'
import { useIterationForm } from '../useIterationForm'

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  silenceConsole('error')

  mocks.createIteration.mockResolvedValue({ code: 200 })
  mocks.updateIteration.mockResolvedValue({ code: 200 })
})

describe('useIterationForm — 表单状态', () => {
  it('初始值与规则', () => {
    const form = useIterationForm()

    expect(form.iterationFormData).toEqual({
      id: null,
      project_id: null,
      name: '',
      version: 'v1.0',
      description: '',
      status: 'draft',
      start_date: '',
      end_date: '',
    })
    expect(form.iterationFormRules.name[0].required).toBe(true)
    expect(form.iterationDialogVisible.value).toBe(false)
    expect(form.iterationDialogMode.value).toBe('add')
  })

  it('resetIterationForm 恢复默认值', () => {
    const form = useIterationForm()
    form.iterationFormData.id = 3
    form.iterationFormData.name = 'x'
    form.iterationFormData.status = 'active'

    form.resetIterationForm()

    expect(form.iterationFormData.id).toBeNull()
    expect(form.iterationFormData.name).toBe('')
    expect(form.iterationFormData.version).toBe('v1.0')
    expect(form.iterationFormData.status).toBe('draft')
  })

  it('新增迭代缺少项目时提示', () => {
    const form = useIterationForm()

    form.handleAddIteration(0)

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
    expect(form.iterationDialogVisible.value).toBe(false)
  })

  it('新增迭代带入项目 ID', () => {
    const form = useIterationForm()

    form.handleAddIteration(7)

    expect(form.iterationDialogMode.value).toBe('add')
    expect(form.iterationFormData.project_id).toBe(7)
    expect(form.iterationDialogVisible.value).toBe(true)
  })

  it('编辑迭代回填字段并截断日期', () => {
    const form = useIterationForm()

    form.handleEditIteration({
      id: 3,
      project_id: 7,
      name: '迭代A',
      version: 'v2.0',
      description: 'desc',
      status: 'active',
      start_date: '2026-11-13T00:00:00',
      end_date: '2026-12-01T00:00:00',
    } as never)

    expect(form.iterationDialogMode.value).toBe('edit')
    expect(form.iterationFormData.id).toBe(3)
    expect(form.iterationFormData.name).toBe('迭代A')
    expect(form.iterationFormData.start_date).toBe('2026-11-13')
    expect(form.iterationFormData.end_date).toBe('2026-12-01')
    expect(form.iterationDialogVisible.value).toBe(true)
  })

  it('编辑迭代无描述与日期时回填空值', () => {
    const form = useIterationForm()

    form.handleEditIteration({
      id: 3,
      project_id: 7,
      name: '迭代A',
      version: 'v2.0',
      status: 'draft',
    } as never)

    expect(form.iterationFormData.description).toBe('')
    expect(form.iterationFormData.start_date).toBe('')
    expect(form.iterationFormData.end_date).toBe('')
  })
})

describe('useIterationForm — 错误提示', () => {
  it.each([
    [
      'UniqueConstraint 命中',
      { response: { data: { detail: 'UniqueConstraint failed' } } },
      '操作失败：数据已存在，请检查是否重复',
    ],
    [
      '中文已存在',
      { response: { data: { detail: '名称已存在' } } },
      '操作失败：数据已存在，请检查是否重复',
    ],
    ['403', { response: { data: { detail: '403 Forbidden' } } }, '操作失败：您没有权限执行此操作'],
    ['中文权限', { response: { data: { detail: '缺少权限' } } }, '操作失败：您没有权限执行此操作'],
    ['404', { response: { data: { detail: '404 Not Found' } } }, '操作失败：请求的资源不存在'],
    ['中文不存在', { response: { data: { detail: '资源不存在' } } }, '操作失败：请求的资源不存在'],
    ['其它 detail', { response: { data: { detail: 'boom' } } }, '操作失败，请稍后重试或联系管理员'],
    ['无 detail', new Error('network'), '操作失败'],
  ])('%s 时给出对应文案', (_, error, expected) => {
    const form = useIterationForm()

    form.showError('操作', error)

    expect(ElMessage.error).toHaveBeenCalledWith(expected)
    expect(console.error).toHaveBeenCalled()
  })
})

describe('useIterationForm — 提交', () => {
  it('表单实例缺失时提示刷新', async () => {
    const form = useIterationForm()

    const result = await form.handleIterationSubmit()

    expect(result).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('表单初始化失败，请刷新页面重试')
    expect(mocks.createIteration).not.toHaveBeenCalled()
  })

  it('校验不通过时中断提交', async () => {
    const form = useIterationForm()
    form.iterationFormRef.value = createFormInstanceMock({ valid: false }) as never
    form.iterationFormData.project_id = 7
    form.iterationFormData.name = '迭代A'

    const result = await form.handleIterationSubmit()

    expect(result).toBe(false)
    expect(mocks.createIteration).not.toHaveBeenCalled()
    expect(form.submitting.value).toBe(false)
  })

  it('传入外部表单实例时跳过内置校验', async () => {
    const form = useIterationForm()
    const externalForm = createFormInstanceMock()
    form.iterationFormData.project_id = 7
    form.iterationFormData.name = '迭代A'

    await form.handleIterationSubmit(externalForm as never)

    expect(externalForm.validate).not.toHaveBeenCalled()
    expect(mocks.createIteration).toHaveBeenCalled()
  })

  it('新增迭代提交成功', async () => {
    const form = useIterationForm()
    form.iterationFormRef.value = createFormInstanceMock() as never
    form.handleAddIteration(7)
    form.iterationFormData.name = '迭代A'
    form.iterationFormData.description = ''
    form.iterationFormData.start_date = ''

    const result = await form.handleIterationSubmit()

    expect(result).toBe(true)
    expect(mocks.createIteration).toHaveBeenCalledWith({
      project_id: 7,
      name: '迭代A',
      version: 'v1.0',
      description: undefined,
      start_date: undefined,
      end_date: undefined,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('迭代 "迭代A" 创建成功')
    expect(form.iterationDialogVisible.value).toBe(false)
    expect(form.submitting.value).toBe(false)
  })

  it('新增迭代缺少项目 ID 时拦截', async () => {
    const form = useIterationForm()
    form.iterationFormRef.value = createFormInstanceMock() as never
    form.iterationFormData.name = '迭代A'

    const result = await form.handleIterationSubmit()

    expect(result).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('项目ID缺失，请刷新页面重试')
    expect(mocks.createIteration).not.toHaveBeenCalled()
  })

  it('编辑迭代提交成功', async () => {
    const form = useIterationForm()
    form.iterationFormRef.value = createFormInstanceMock() as never
    form.handleEditIteration({ id: 3, project_id: 7, name: '旧名', version: 'v1.0' } as never)
    form.iterationFormData.name = '新名'
    form.iterationFormData.description = '说明'
    form.iterationFormData.start_date = '2026-11-13'

    const result = await form.handleIterationSubmit()

    expect(result).toBe(true)
    expect(mocks.updateIteration).toHaveBeenCalledWith(3, {
      name: '新名',
      version: 'v1.0',
      description: '说明',
      start_date: '2026-11-13',
      end_date: undefined,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('迭代 "新名" 更新成功')
    expect(mocks.createIteration).not.toHaveBeenCalled()
  })

  it('提交失败走错误提示并返回 false', async () => {
    mocks.createIteration.mockRejectedValue({ response: { data: { detail: 'UniqueConstraint' } } })
    const form = useIterationForm()
    form.iterationFormRef.value = createFormInstanceMock() as never
    form.iterationFormData.project_id = 7
    form.iterationFormData.name = '迭代A'

    const result = await form.handleIterationSubmit()

    expect(result).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('创建迭代失败：数据已存在，请检查是否重复')
    expect(form.submitting.value).toBe(false)
    expect(form.iterationDialogVisible.value).toBe(false)
  })

  it('更新失败提示更新迭代失败', async () => {
    mocks.updateIteration.mockRejectedValue({ response: { data: { detail: 'boom' } } })
    const form = useIterationForm()
    form.iterationFormRef.value = createFormInstanceMock() as never
    form.handleEditIteration({ id: 3, project_id: 7, name: 'a', version: 'v1.0' } as never)

    const result = await form.handleIterationSubmit()

    expect(result).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('更新迭代失败，请稍后重试或联系管理员')
  })
})
