import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import type { SmartPreviewCase } from '@/store/smartGeneration'

vi.mock('@/utils/request', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  const message = Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    close: vi.fn(),
    closeAll: vi.fn(),
  })
  return { ...actual, ElMessage: message }
})

import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import { useSmartGenerationStore } from '@/store/smartGeneration'
import SmartGenerateDialogs from '../SmartGenerateDialogs.vue'

const messageMock = ElMessage as unknown as ReturnType<typeof vi.fn> & {
  success: ReturnType<typeof vi.fn>
  error: ReturnType<typeof vi.fn>
  warning: ReturnType<typeof vi.fn>
}

const requestGet = request.get as unknown as ReturnType<typeof vi.fn>

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: {
    modelValue: { type: Boolean, default: false },
    title: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'close'],
  template: `
    <div v-if="modelValue" class="el-dialog">
      <div class="el-dialog__header">{{ title }}</div>
      <slot />
      <div class="el-dialog__footer"><slot name="footer" /></div>
    </div>
  `,
})

type Store = ReturnType<typeof useSmartGenerationStore>
let store: Store

function makeCase(overrides: Partial<SmartPreviewCase> = {}): SmartPreviewCase {
  return {
    client_id: 'c1',
    source_test_point_id: null,
    requirement_file_id: null,
    title: '原标题',
    module: '登录',
    precondition: '已注册',
    steps: [{ step: 1, action: '打开首页', expected_result: '展示首页' }],
    expected_result: '登录成功',
    priority: 1,
    case_type: 'manual',
    case_category: null,
    quality_status: 'passed',
    quality_issues: [],
    selected_for_save: true,
    dirty: false,
    regenerating: false,
    source_refs: {},
    ...overrides,
  }
}

interface DialogProps {
  editVisible?: boolean
  saveResultVisible?: boolean
  systemCaseVisible?: boolean
  editingCase?: SmartPreviewCase | null
  editingClientId?: string
  saveMode?: 'draft' | 'formal' | 'passed_only'
}

function mountDialogs(overrides: DialogProps = {}) {
  return mount(SmartGenerateDialogs, {
    props: {
      editVisible: false,
      saveResultVisible: false,
      systemCaseVisible: false,
      editingCase: null,
      editingClientId: '',
      saveMode: 'draft',
      ...overrides,
    },
    global: { stubs: { ElDialog: ElDialogStub } },
  })
}

function dialogByTitle(wrapper: ReturnType<typeof mount>, title: string) {
  return wrapper.findAll('.el-dialog').find((el) => el.text().includes(title))
}

function findButton(
  scope: { findAll: (selector: string) => Array<{ text: () => string }> },
  text: string
) {
  return scope.findAll('button').find((btn) => btn.text().includes(text)) as
    | { trigger: (event: string) => Promise<void> }
    | undefined
}

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  store = useSmartGenerationStore()
  store.selectedProjectId = 9
  store.uiUploadDialogVisible = false
  store.uiUploading = false
  store.previewCases = [makeCase()]
  store.saveResult = null
  store.saveError = ''
  store.batchCost = null
  requestGet.mockResolvedValue({
    data: {
      items: [
        { id: 1, title: '系统用例一', module: '登录', case_type: 'manual' },
        { id: 2, title: '系统用例二', module: '支付', case_type: 'api_automation' },
      ],
    },
  })
})

describe('SmartGenerateDialogs — 编辑用例', () => {
  it('打开时按传入用例生成本地副本并渲染字段', () => {
    const editingCase = makeCase()
    const wrapper = mountDialogs({ editVisible: true, editingCase, editingClientId: 'c1' })

    const dialog = dialogByTitle(wrapper, '编辑用例')!
    expect(dialog.find('input').element.value).toBe('原标题')
    // 前置条件/预期结果是 textarea，值不体现在 text() 中
    expect(dialog.find('textarea').element.value).toBe('已注册')
    expect((dialog.findAll('input[placeholder="操作"]')[0].element as HTMLInputElement).value).toBe(
      '打开首页'
    )
    expect(
      (dialog.findAll('input[placeholder="预期结果"]')[0].element as HTMLInputElement).value
    ).toBe('展示首页')
  })

  it('保存修改写回 store 预览用例并标记 dirty', async () => {
    const editingCase = makeCase()
    const wrapper = mountDialogs({ editVisible: true, editingCase, editingClientId: 'c1' })
    const recalcSpy = vi.spyOn(store, 'recalcQualitySummary')

    const dialog = dialogByTitle(wrapper, '编辑用例')!
    await dialog.find('input').setValue('新标题')
    await findButton(dialog, '保存修改')!.trigger('click')
    await nextTick()

    expect(store.previewCases[0].title).toBe('新标题')
    expect(store.previewCases[0].dirty).toBe(true)
    expect(recalcSpy).toHaveBeenCalledTimes(1)
    expect(messageMock.success).toHaveBeenCalledWith('修改已保存到预览')
    expect(wrapper.emitted('update:editVisible')).toEqual([[false]])
  })

  it('编辑不影响父组件传入的原对象', async () => {
    const editingCase = makeCase()
    const wrapper = mountDialogs({ editVisible: true, editingCase, editingClientId: 'c1' })

    await dialogByTitle(wrapper, '编辑用例')!.find('input').setValue('仅本地修改')

    expect(editingCase.title).toBe('原标题')
  })

  it('添加与删除步骤调整行数', async () => {
    const wrapper = mountDialogs({
      editVisible: true,
      editingCase: makeCase(),
      editingClientId: 'c1',
    })
    const dialog = dialogByTitle(wrapper, '编辑用例')!

    await findButton(dialog, '添加步骤')!.trigger('click')
    expect(dialog.findAll('input[placeholder="操作"]')).toHaveLength(2)

    await findButton(dialog, '删除')!.trigger('click')
    expect(dialog.findAll('input[placeholder="操作"]')).toHaveLength(1)
  })

  it('编辑步骤字段后保存生效', async () => {
    const wrapper = mountDialogs({
      editVisible: true,
      editingCase: makeCase(),
      editingClientId: 'c1',
    })
    const dialog = dialogByTitle(wrapper, '编辑用例')!

    await dialog.findAll('input[placeholder="操作"]')[0].setValue('点击登录')
    await findButton(dialog, '保存修改')!.trigger('click')
    await nextTick()

    expect(store.previewCases[0].steps[0].action).toBe('点击登录')
  })

  it('取消不写回 store', async () => {
    const wrapper = mountDialogs({
      editVisible: true,
      editingCase: makeCase(),
      editingClientId: 'c1',
    })
    const dialog = dialogByTitle(wrapper, '编辑用例')!

    await dialog.find('input').setValue('不保存的标题')
    await findButton(dialog, '取消')!.trigger('click')

    expect(store.previewCases[0].title).toBe('原标题')
    expect(wrapper.emitted('update:editVisible')).toEqual([[false]])
  })

  it('找不到对应 client_id 时只关闭弹窗', async () => {
    const wrapper = mountDialogs({
      editVisible: true,
      editingCase: makeCase(),
      editingClientId: 'not-exist',
    })

    await findButton(dialogByTitle(wrapper, '编辑用例')!, '保存修改')!.trigger('click')

    expect(store.previewCases[0].title).toBe('原标题')
    expect(messageMock.success).toHaveBeenCalledWith('修改已保存到预览')
    expect(wrapper.emitted('update:editVisible')).toEqual([[false]])
  })
})

describe('SmartGenerateDialogs — 保存结果', () => {
  it('全部成功时展示成功标题、数量与成本换算', () => {
    store.saveResult = {
      status: 'saved',
      saved_count: 3,
      failed_count: 0,
      failures: [],
    } as never
    store.batchCost = {
      totalCalls: 8,
      totalPromptTokens: 9000,
      totalCompletionTokens: 3345,
      totalTokens: 12345,
      totalCostUsd: 0.17,
    } as never
    const wrapper = mountDialogs({ saveResultVisible: true })

    const dialog = dialogByTitle(wrapper, '保存结果')!
    expect(dialog.text()).toContain('保存成功')
    expect(dialog.text()).toContain('3')
    expect(dialog.text()).toContain((12345).toLocaleString())
    expect(dialog.text()).toContain('¥1.23')
    expect(dialog.text()).toContain('$0.1700')
  })

  it('部分成功时展示部分成功标题', () => {
    store.saveResult = {
      status: 'partial_saved',
      saved_count: 2,
      failed_count: 1,
      failures: [],
    } as never
    const wrapper = mountDialogs({ saveResultVisible: true })

    expect(dialogByTitle(wrapper, '保存结果')!.text()).toContain('部分保存成功')
  })

  it('全部失败时展示失败标题与失败明细', () => {
    store.saveResult = {
      status: 'failed',
      saved_count: 0,
      failed_count: 1,
      failures: [{ title: '用例甲', reason: '服务异常' }],
    } as never
    const wrapper = mountDialogs({ saveResultVisible: true })

    const dialog = dialogByTitle(wrapper, '保存结果')!
    expect(dialog.text()).toContain('保存失败')
    expect(dialog.text()).toContain('用例甲')
    expect(dialog.text()).toContain('服务异常')
  })

  it('成本未加载时展示占位图标而非数字', () => {
    store.saveResult = {
      status: 'saved',
      saved_count: 1,
      failed_count: 0,
      failures: [],
    } as never
    const wrapper = mountDialogs({ saveResultVisible: true })

    const dialog = dialogByTitle(wrapper, '保存结果')!
    expect(dialog.find('.spin-icon').exists()).toBe(true)
    expect(dialog.text()).not.toContain('¥')
  })

  it('无保存结果但存在错误时展示错误态并可重试', async () => {
    store.saveError = '网关超时'
    const wrapper = mountDialogs({ saveResultVisible: true })

    const dialog = dialogByTitle(wrapper, '保存结果')!
    expect(dialog.text()).toContain('保存失败')
    expect(dialog.text()).toContain('网关超时')

    await findButton(dialog, '重试')!.trigger('click')
    expect(wrapper.emitted('save')).toBeTruthy()
  })

  it('底部按钮分别关闭弹窗、跳转用例列表与重新生成', async () => {
    const wrapper = mountDialogs({ saveResultVisible: true })
    const dialog = dialogByTitle(wrapper, '保存结果')!

    await findButton(dialog, '关闭')!.trigger('click')
    expect(wrapper.emitted('update:saveResultVisible')).toEqual([[false]])

    await findButton(dialog, '查看已保存用例')!.trigger('click')
    expect(wrapper.emitted('go-to-case-list')).toBeTruthy()

    await findButton(dialog, '重新生成')!.trigger('click')
    expect(wrapper.emitted('reset')).toBeTruthy()
  })
})

describe('SmartGenerateDialogs — UI 上传', () => {
  it('按 store 状态展示上传弹窗，取消后关闭', async () => {
    const wrapper = mountDialogs()
    store.uiUploadDialogVisible = true
    await nextTick()

    const dialog = dialogByTitle(wrapper, '上传 UI 页面')
    expect(dialog).toBeTruthy()

    await findButton(dialog!, '取消')!.trigger('click')
    expect(store.uiUploadDialogVisible).toBe(false)
  })

  it('未选择文件时提示且不上传', async () => {
    const wrapper = mountDialogs()
    store.uiUploadDialogVisible = true
    await nextTick()

    await findButton(dialogByTitle(wrapper, '上传 UI 页面')!, '上传并解析')!.trigger('click')

    expect(messageMock.warning).toHaveBeenCalledWith('请选择要上传的文件')
    expect(messageMock.success).not.toHaveBeenCalled()
  })

  it('选择文件后上传并关闭弹窗', async () => {
    const uploadSpy = vi.spyOn(store, 'uploadUIScreens').mockResolvedValue(undefined)
    const wrapper = mountDialogs()
    store.uiUploadDialogVisible = true
    await nextTick()

    const dialog = dialogByTitle(wrapper, '上传 UI 页面')!
    const upload = dialog.findComponent({ name: 'ElUpload' })
    const files = [{ raw: new File(['a'], 'a.png') }, { raw: new File(['b'], 'b.png') }]
    ;(upload.props('onChange') as (file: unknown, list: unknown[]) => void)(files[0], files)
    await nextTick()

    await findButton(dialog, '上传并解析')!.trigger('click')
    await flushPromises()

    expect(uploadSpy).toHaveBeenCalledWith([files[0].raw, files[1].raw])
    expect(store.uiUploadDialogVisible).toBe(false)
    expect(messageMock.success).toHaveBeenCalledWith('上传成功，正在后台解析')
  })
})

describe('SmartGenerateDialogs — 系统用例导入', () => {
  it('打开弹窗时按当前项目拉取系统用例', async () => {
    const wrapper = mountDialogs()

    await wrapper.setProps({ systemCaseVisible: true })
    await flushPromises()

    expect(requestGet).toHaveBeenCalledWith('/api/v1/test-case/?project_id=9&page=1&page_size=200')
    const dialog = dialogByTitle(wrapper, '从系统用例导入')!
    const rows = dialog.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('系统用例一')
  })

  it('未选项目时不发起请求且列表为空', async () => {
    store.selectedProjectId = ''
    const wrapper = mountDialogs()

    await wrapper.setProps({ systemCaseVisible: true })
    await flushPromises()

    expect(requestGet).not.toHaveBeenCalled()
    expect(dialogByTitle(wrapper, '从系统用例导入')!.findAll('.el-table__row')).toHaveLength(0)
  })

  it('请求失败时静默降级为空列表', async () => {
    requestGet.mockRejectedValue(new Error('网络错误'))
    const wrapper = mountDialogs()

    await wrapper.setProps({ systemCaseVisible: true })
    await flushPromises()

    expect(dialogByTitle(wrapper, '从系统用例导入')!.findAll('.el-table__row')).toHaveLength(0)
    expect(messageMock.error).not.toHaveBeenCalled()
  })

  it('未选中用例时导入按钮禁用，选中后展示数量', async () => {
    const wrapper = mountDialogs()
    await wrapper.setProps({ systemCaseVisible: true })
    await flushPromises()

    const dialog = dialogByTitle(wrapper, '从系统用例导入')!
    const importBtn = () =>
      dialog
        .findAllComponents({ name: 'ElButton' })
        .find((btn: VueWrapper) => btn.text().includes('导入选中'))

    expect(importBtn()!.props('disabled')).toBe(true)

    dialog.findComponent({ name: 'ElTable' }).vm.$emit('selection-change', [{ id: 1 }, { id: 2 }])
    await nextTick()

    expect(importBtn()!.props('disabled')).toBe(false)
    expect(importBtn()!.text()).toContain('导入选中 (2)')
  })

  it('导入成功后提示并关闭弹窗', async () => {
    const importSpy = vi.spyOn(store, 'importSystemCasesAsHistory').mockResolvedValue(undefined)
    const wrapper = mountDialogs()
    await wrapper.setProps({ systemCaseVisible: true })
    await flushPromises()

    const dialog = dialogByTitle(wrapper, '从系统用例导入')!
    dialog.findComponent({ name: 'ElTable' }).vm.$emit('selection-change', [{ id: 1 }, { id: 2 }])
    await nextTick()

    await findButton(dialog, '导入选中')!.trigger('click')
    await flushPromises()

    expect(importSpy).toHaveBeenCalledWith([1, 2])
    expect(messageMock.success).toHaveBeenCalledWith('系统用例导入成功')
    expect(wrapper.emitted('update:systemCaseVisible')).toEqual([[false]])
  })

  it('导入异常时提示接口错误详情', async () => {
    vi.spyOn(store, 'importSystemCasesAsHistory').mockRejectedValue(new Error('导入服务不可用'))
    const wrapper = mountDialogs()
    await wrapper.setProps({ systemCaseVisible: true })
    await flushPromises()

    const dialog = dialogByTitle(wrapper, '从系统用例导入')!
    dialog.findComponent({ name: 'ElTable' }).vm.$emit('selection-change', [{ id: 1 }])
    await nextTick()

    await findButton(dialog, '导入选中')!.trigger('click')
    await flushPromises()

    expect(messageMock.error).toHaveBeenCalledWith('导入服务不可用')
  })
})
