import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

vi.mock('@/api/case', () => ({
  testCaseApi: {
    updateCase: vi.fn(),
    updateStepLocator: vi.fn(),
  },
}))

import { testCaseApi } from '@/api/case'
import { useCaseEdit } from '../useCaseEdit'
import type { TestCase } from '@/types/testCase'
import { silenceConsole, silenceElMessage } from '@/test-utils'

const updateCaseMock = vi.mocked(testCaseApi.updateCase)

function fullCase(): TestCase {
  return {
    id: 7,
    title: '登录成功',
    module: '登录',
    precondition: '已注册',
    expected_result: '进入首页',
    priority: 1,
    case_type: 'manual',
    test_category: '功能测试',
    steps: [{ step_number: 1, action: '输入账号', expected_result: '输入成功' }],
  } as unknown as TestCase
}

function setup(caseValue: TestCase | null = fullCase()) {
  const caseItem = ref<TestCase | null>(caseValue)
  const caseId = ref(7)
  const fetchCaseDetail = vi.fn().mockResolvedValue(undefined)

  const api = useCaseEdit(caseItem, caseId, fetchCaseDetail)
  return { api, caseItem, caseId, fetchCaseDetail }
}

describe('useCaseEdit — 表单初始化', () => {
  it('用例为空时不初始化', () => {
    const { api } = setup(null)

    api.initEditForm()

    expect(api.editForm.value.title).toBe('')
  })

  it('按当前用例填充表单并深拷贝步骤', () => {
    const { api, caseItem } = setup()

    api.initEditForm()

    expect(api.editForm.value).toMatchObject({
      title: '登录成功',
      module: '登录',
      precondition: '已注册',
      expected_result: '进入首页',
      priority: 1,
      case_type: 'manual',
      test_category: '功能测试',
    })
    expect(api.editForm.value.steps).toEqual([
      { step_number: 1, action: '输入账号', expected_result: '输入成功' },
    ])

    api.editForm.value.steps[0].action = '改坏了'
    expect(caseItem.value?.steps?.[0].action).toBe('输入账号')
  })

  it('缺省字段回退默认值（priority 为 2、空字符串、空步骤）', () => {
    const { api } = setup({ id: 1 } as unknown as TestCase)

    api.initEditForm()

    expect(api.editForm.value).toMatchObject({
      title: '',
      module: '',
      precondition: '',
      expected_result: '',
      priority: 2,
      case_type: '',
      test_category: '',
      steps: [],
    })
  })
})

describe('useCaseEdit — 编辑态切换', () => {
  it('toggleEdit 首次进入编辑并初始化表单', () => {
    const { api } = setup()

    api.toggleEdit()

    expect(api.isEditing.value).toBe(true)
    expect(api.editForm.value.title).toBe('登录成功')
  })

  it('toggleEdit 再次调用取消编辑并还原表单', () => {
    const { api } = setup()
    api.toggleEdit()
    api.editForm.value.title = '临时改动'

    api.toggleEdit()

    expect(api.isEditing.value).toBe(false)
    expect(api.editForm.value.title).toBe('登录成功')
  })

  it('cancelEdit 退出编辑并还原', () => {
    const { api } = setup()
    api.isEditing.value = true
    api.editForm.value.title = '临时改动'

    api.cancelEdit()

    expect(api.isEditing.value).toBe(false)
    expect(api.editForm.value.title).toBe('登录成功')
  })
})

describe('useCaseEdit — 保存', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    updateCaseMock.mockResolvedValue(undefined as never)
    silenceElMessage('warning')
    silenceElMessage('error')
    silenceElMessage('success')
    silenceConsole('error')
  })

  it('标题为空时拦截', async () => {
    const { api } = setup()
    api.editForm.value.title = '   '

    await api.saveEdit()

    expect(ElMessage.warning).toHaveBeenCalledWith('请输入用例标题')
    expect(updateCaseMock).not.toHaveBeenCalled()
  })

  it('步骤为空时拦截', async () => {
    const { api } = setup()
    api.editForm.value.title = '用例标题'
    api.editForm.value.steps = []

    await api.saveEdit()

    expect(ElMessage.warning).toHaveBeenCalledWith('请至少添加一个测试步骤')
    expect(updateCaseMock).not.toHaveBeenCalled()
  })

  it('保存成功后退出编辑并重新拉取详情', async () => {
    const { api, fetchCaseDetail } = setup()
    api.isEditing.value = true
    api.initEditForm()

    await api.saveEdit()

    expect(updateCaseMock).toHaveBeenCalledWith(7, {
      title: '登录成功',
      module: '登录',
      precondition: '已注册',
      expected_result: '进入首页',
      priority: 1,
      case_type: 'manual',
      test_category: '功能测试',
      steps: [{ step_number: 1, action: '输入账号', expected_result: '输入成功' }],
    })
    expect(ElMessage.success).toHaveBeenCalledWith('保存成功')
    expect(api.isEditing.value).toBe(false)
    expect(fetchCaseDetail).toHaveBeenCalledTimes(1)
    expect(api.saving.value).toBe(false)
  })

  it('优先展示后端 detail', async () => {
    updateCaseMock.mockRejectedValue({ response: { data: { detail: '用例已被删除' } } })
    const { api } = setup()
    api.editForm.value.title = '用例标题'
    api.editForm.value.steps = [{ action: 'a', expected_result: 'b' }]

    await api.saveEdit()

    expect(ElMessage.error).toHaveBeenCalledWith('用例已被删除')
    expect(api.saving.value).toBe(false)
  })

  it('无 detail 时回退 error.message', async () => {
    updateCaseMock.mockRejectedValue(new Error('网络中断'))
    const { api } = setup()
    api.editForm.value.title = '用例标题'
    api.editForm.value.steps = [{ action: 'a', expected_result: 'b' }]

    await api.saveEdit()

    expect(ElMessage.error).toHaveBeenCalledWith('网络中断')
  })

  it('既无 detail 也无 message 时使用兜底文案', async () => {
    updateCaseMock.mockRejectedValue({})
    const { api } = setup()
    api.editForm.value.title = '用例标题'
    api.editForm.value.steps = [{ action: 'a', expected_result: 'b' }]

    await api.saveEdit()

    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
  })
})
