import { describe, it, expect, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { createGenerateState, type GenerateState } from '../state'
import { createGenerateComputed, type GenerateComputed } from '../computed'
import type { UIPrototypeProject } from '@/api/uiPrototype'
import type { TestPoint } from '@/api/testPoint'

function makePrototype(overrides: Partial<Record<string, unknown>> = {}): UIPrototypeProject {
  return {
    id: 1,
    name: '登录页原型',
    description: '登录流程',
    parse_status: 'completed',
    parsed_count: 0,
    screen_count: 0,
    ...overrides,
  } as unknown as UIPrototypeProject
}

function makePoint(overrides: Partial<Record<string, unknown>> = {}): TestPoint {
  return {
    id: 1,
    module: '登录',
    function: '登录',
    point: '登录成功',
    priority: 1,
    ...overrides,
  } as unknown as TestPoint
}

describe('createGenerateComputed — 上下文与选择派生', () => {
  let state: GenerateState
  let c: GenerateComputed

  beforeEach(() => {
    state = createGenerateState()
    c = createGenerateComputed(state)
  })

  it('selectedUiPrototypeProject：未选择/选中不存在/正常命中', () => {
    expect(c.selectedUiPrototypeProject.value).toBeNull()

    state.selectedUiPrototypeProjectId.value = 99
    expect(c.selectedUiPrototypeProject.value).toBeNull()

    state.uiPrototypeProjects.value = [makePrototype({ id: 3 })]
    state.selectedUiPrototypeProjectId.value = 3
    expect(c.selectedUiPrototypeProject.value?.id).toBe(3)
  })

  it('flowSortModuleInfo：无选中回退空串，有选中回退空串字段', () => {
    expect(c.flowSortModuleInfo.value).toEqual({ name: '', description: '' })

    state.uiPrototypeProjects.value = [makePrototype({ id: 2, name: '', description: undefined })]
    state.selectedUiPrototypeProjectId.value = 2
    expect(c.flowSortModuleInfo.value).toEqual({ name: '', description: '' })
  })

  it('screenPreviewStatusType：parse_status 映射四种标签类型', () => {
    const cases: Array<[string, string]> = [
      ['completed', 'success'],
      ['partial', 'warning'],
      ['failed', 'danger'],
      ['pending', 'info'],
    ]
    for (const [status, expected] of cases) {
      state.uiPrototypeProjects.value = [makePrototype({ id: 1, parse_status: status })]
      state.selectedUiPrototypeProjectId.value = 1
      expect(c.screenPreviewStatusType.value).toBe(expected)
    }

    state.selectedUiPrototypeProjectId.value = ''
    expect(c.screenPreviewStatusType.value).toBe('info')
  })

  it('screenPreviewStatusText：五种文案（含分母回退到已加载屏幕数）', () => {
    expect(c.screenPreviewStatusText.value).toBe('未选择版本')

    state.uiPrototypeProjects.value = [
      makePrototype({ id: 1, parse_status: 'completed' }),
      makePrototype({ id: 2, parse_status: 'partial', parsed_count: 3, screen_count: 0 }),
      makePrototype({ id: 3, parse_status: 'failed' }),
      makePrototype({ id: 4, parse_status: 'pending' }),
    ]

    state.selectedUiPrototypeProjectId.value = 1
    expect(c.screenPreviewStatusText.value).toBe('全部已解析')

    state.uiScreens.value = [{ id: 11 }, { id: 12 }] as never
    state.selectedUiPrototypeProjectId.value = 2
    expect(c.screenPreviewStatusText.value).toBe('部分解析 3/2')

    state.selectedUiPrototypeProjectId.value = 3
    expect(c.screenPreviewStatusText.value).toBe('解析失败')

    state.selectedUiPrototypeProjectId.value = 4
    expect(c.screenPreviewStatusText.value).toBe('待解析')
  })

  it('viewingCase：空列表为 null，越界回退首条，命中取当前索引', () => {
    expect(c.viewingCase.value).toBeNull()

    state.generatedCases.value = [{ title: 'A' } as never, { title: 'B' } as never]
    state.currentCaseIndex.value = -1
    expect(c.viewingCase.value).toEqual({ title: 'A' })

    state.currentCaseIndex.value = 5
    expect(c.viewingCase.value).toEqual({ title: 'A' })

    state.currentCaseIndex.value = 1
    expect(c.viewingCase.value).toEqual({ title: 'B' })
  })

  it('selectedTestPointsForDisplay：最多 5 条，优先 testPoints，其次 formData，最后占位', () => {
    state.testPoints.value = [makePoint({ id: 1, module: 'M1' })]
    state.formData.test_points_data = [
      makePoint({ id: 2, module: 'M2' }) as never,
      { id: 3, module: 'M3', function: 'F3', point: 'P3', priority: 2 } as never,
    ]
    state.formData.test_point_ids = [1, 2, 3, 4, 5, 6]

    const list = c.selectedTestPointsForDisplay.value
    expect(list).toHaveLength(5)
    expect(list[0]).toMatchObject({ id: 1, module: 'M1' })
    expect(list[1]).toMatchObject({ id: 2, module: 'M2' })
    expect(list[2]).toMatchObject({ id: 3, module: 'M3' })
    expect(list[3]).toEqual({ id: 4, module: '?', function: '?', point: '未知测试点', priority: 2 })
    expect(list[4]).toMatchObject({ id: 5 })
  })

  it('contextQuality：历史用例数按「已选 > 用户清空 > 项目用例」三级回退', () => {
    state.formData.requirement_file_ids = [1]
    state.formData.test_point_ids = [1]
    state.formData.ui_screen_ids = [1]

    state.projectCases.value = [{ id: 1 }, { id: 2 }] as never
    expect(c.contextQuality.value.historyCaseCount).toBe(2)

    state._historyCaseUserCleared.value = true
    expect(c.contextQuality.value.historyCaseCount).toBe(0)

    state.selectedHistoryCaseIds.value = [7, 8, 9]
    expect(c.contextQuality.value.historyCaseCount).toBe(3)
    expect(c.contextQuality.value.mode).toBe('new_full_generation')
  })

  it('canGenerate：任一上下文来源非空即可生成', () => {
    expect(c.canGenerate.value).toBe(false)

    state.formData.ui_file_ids = [1]
    expect(c.canGenerate.value).toBe(true)
  })

  it('generateButtonLabel：测试点 > 需求 > 屏幕 > 历史用例 > 接口用例 > 开始', () => {
    expect(c.generateButtonLabel.value).toBe('开始')

    state.formData.case_type = 'api_automation'
    expect(c.generateButtonLabel.value).toBe('接口用例')

    state.projectCases.value = [{ id: 1 }] as never
    expect(c.generateButtonLabel.value).toBe('1 条历史用例')

    state.formData.ui_screen_ids = [1, 2]
    expect(c.generateButtonLabel.value).toBe('2 个屏幕')

    state.formData.requirement_file_ids = [1, 2, 3]
    expect(c.generateButtonLabel.value).toBe('3 份需求')

    state.formData.test_point_ids = [1, 2, 3, 4]
    expect(c.generateButtonLabel.value).toBe('4 个测试用例')
  })

  it('progressStatus：完成优先，其次异常，否则空', () => {
    expect(c.progressStatus.value).toBe('')

    state.errorMessage.value = '失败'
    expect(c.progressStatus.value).toBe('exception')

    state.progress.value = 100
    expect(c.progressStatus.value).toBe('success')
  })

  it('全选三态：allSelected 要求非空且全选中', () => {
    expect(c.allSelected.value).toBe(false)

    state.generatedCases.value = [{ title: 'A' }, { title: 'B' }] as never
    expect(c.allSelected.value).toBe(false)

    state.selectedCaseIndices.value = new Set([0])
    expect(c.allSelected.value).toBe(false)
    expect(c.hasSelected.value).toBe(true)
    expect(c.selectedCount.value).toBe(1)

    state.selectedCaseIndices.value = new Set([0, 1])
    expect(c.allSelected.value).toBe(true)
    expect(c.selectedCount.value).toBe(2)
  })

  it('切换 currentCaseIndex 时自动退出结果编辑态', async () => {
    state.isEditingResult.value = true
    state.currentCaseIndex.value = 2

    await nextTick()

    expect(state.isEditingResult.value).toBe(false)
  })
})
