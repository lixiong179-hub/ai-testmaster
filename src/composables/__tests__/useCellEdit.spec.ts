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
import { useCellEdit } from '../useCellEdit'
import type { TechnicalView } from '@/api/testCaseView'
import { silenceConsole, silenceElMessage } from '@/test-utils'

const updateCaseMock = vi.mocked(testCaseApi.updateCase)
const updateLocatorMock = vi.mocked(testCaseApi.updateStepLocator)

function view(): TechnicalView {
  return {
    steps: [
      {
        step_number: 1,
        step_id: 11,
        action: '点击登录',
        expected_result: '跳转首页',
        locator: { css_selector: '#login', xpath: '//button' },
      },
      {
        step_number: 2,
        action: '输入账号',
        expected_result: '输入成功',
        locator: { css_selector: '#user', xpath: '//input' },
      },
    ],
  } as unknown as TechnicalView
}

function setup(issueTypeValue = 'case_issue') {
  const caseId = ref(7)
  const technicalViewData = ref<TechnicalView | null>(view())
  const issueType = ref(issueTypeValue)

  const api = useCellEdit(caseId, technicalViewData, issueType)
  return { api, caseId, technicalViewData, issueType }
}

describe('useCellEdit — 编辑态', () => {
  it('Bug 问题禁止编辑', () => {
    const { api } = setup('product_bug')

    api.startCellEdit(0, 'action', '点击登录')

    expect(api.editingCell.value).toBeNull()
  })

  it('开始编辑记录单元格与初值', () => {
    const { api } = setup()

    api.startCellEdit(1, 'xpath', '//input')

    expect(api.editingCell.value).toEqual({ stepIndex: 1, field: 'xpath' })
    expect(api.editingValue.value).toBe('//input')
  })

  it('空值初值回退空字符串', () => {
    const { api } = setup()

    api.startCellEdit(0, 'action', undefined)

    expect(api.editingValue.value).toBe('')
  })

  it('取消编辑清空状态', () => {
    const { api } = setup()
    api.startCellEdit(0, 'action', 'x')

    api.cancelCellEdit()

    expect(api.editingCell.value).toBeNull()
    expect(api.editingValue.value).toBe('')
  })
})

describe('useCellEdit — 保存', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    updateCaseMock.mockResolvedValue(undefined as never)
    updateLocatorMock.mockResolvedValue(undefined as never)
    silenceElMessage('warning')
    silenceElMessage('error')
    silenceElMessage('success')
    silenceConsole('error')
  })

  it('无编辑中单元格时不请求', async () => {
    const { api } = setup()

    await api.saveCellEdit()

    expect(updateCaseMock).not.toHaveBeenCalled()
  })

  it('无技术视图数据时不请求', async () => {
    const { api, technicalViewData } = setup()
    technicalViewData.value = null
    api.startCellEdit(0, 'action', 'x')

    await api.saveCellEdit()

    expect(updateCaseMock).not.toHaveBeenCalled()
  })

  it('步骤越界时不请求', async () => {
    const { api } = setup()
    api.startCellEdit(9, 'action', 'x')

    await api.saveCellEdit()

    expect(updateCaseMock).not.toHaveBeenCalled()
  })

  it('操作/预期结果为空时拦截', async () => {
    const { api } = setup()
    api.startCellEdit(0, 'action', '   ')

    await api.saveCellEdit()

    expect(ElMessage.warning).toHaveBeenCalledWith('内容不能为空')
    expect(updateCaseMock).not.toHaveBeenCalled()
  })

  it('定位器允许清空', async () => {
    const { api } = setup()
    api.startCellEdit(0, 'xpath', '')

    await api.saveCellEdit()

    expect(updateLocatorMock).toHaveBeenCalledWith(7, 11, { xpath: '' })
    expect(ElMessage.success).toHaveBeenCalledWith('保存成功')
  })

  it('保存操作文本：整表提交并同步 description', async () => {
    const { api, technicalViewData } = setup()
    api.startCellEdit(0, 'action', '点击登录按钮')

    await api.saveCellEdit()

    expect(updateCaseMock).toHaveBeenCalledWith(7, {
      steps: [
        { step_number: 1, action: '点击登录按钮', expected_result: '跳转首页' },
        { step_number: 2, action: '输入账号', expected_result: '输入成功' },
      ],
    })
    const step = technicalViewData.value!.steps[0]
    expect(step.action).toBe('点击登录按钮')
    expect(step.description).toBe('点击登录按钮')
    expect(api.editingCell.value).toBeNull()
    expect(api.cellSaving.value).toBe(false)
  })

  it('保存预期结果只替换该字段', async () => {
    const { api, technicalViewData } = setup()
    api.startCellEdit(1, 'expected_result', '输入成功并高亮')

    await api.saveCellEdit()

    expect(updateCaseMock).toHaveBeenCalledWith(7, {
      steps: [
        { step_number: 1, action: '点击登录', expected_result: '跳转首页' },
        { step_number: 2, action: '输入账号', expected_result: '输入成功并高亮' },
      ],
    })
    expect(technicalViewData.value!.steps[1].expected_result).toBe('输入成功并高亮')
  })

  it('保存 css_selector 走定位器接口并同步本地', async () => {
    const { api, technicalViewData } = setup()
    api.startCellEdit(0, 'css_selector', '#submit')

    await api.saveCellEdit()

    expect(updateLocatorMock).toHaveBeenCalledWith(7, 11, { css_selector: '#submit' })
    expect(technicalViewData.value!.steps[0].locator?.css_selector).toBe('#submit')
    expect(updateCaseMock).not.toHaveBeenCalled()
  })

  it('缺少 step_id 时以 step_number 作为定位器ID', async () => {
    const { api, technicalViewData } = setup()
    delete (technicalViewData.value!.steps[0] as { step_id?: number }).step_id
    api.startCellEdit(0, 'xpath', '//new')

    await api.saveCellEdit()

    expect(updateLocatorMock).toHaveBeenCalledWith(7, 1, { xpath: '//new' })
    expect(technicalViewData.value!.steps[0].locator?.xpath).toBe('//new')
  })

  it('保存失败优先展示后端 detail', async () => {
    updateCaseMock.mockRejectedValue({ response: { data: { detail: '用例已锁定' } } })
    const { api } = setup()
    api.startCellEdit(0, 'action', 'x')

    await api.saveCellEdit()

    expect(ElMessage.error).toHaveBeenCalledWith('用例已锁定')
    expect(api.cellSaving.value).toBe(false)
    // 失败时保留编辑态，便于用户重试
    expect(api.editingCell.value).toEqual({ stepIndex: 0, field: 'action' })
  })

  it('无 detail 时使用兜底文案', async () => {
    updateCaseMock.mockRejectedValue(new Error('boom'))
    const { api } = setup()
    api.startCellEdit(0, 'action', 'x')

    await api.saveCellEdit()

    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
  })
})
