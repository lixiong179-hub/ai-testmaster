import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, reactive } from 'vue'
import { ElMessage } from 'element-plus'

const mocks = vi.hoisted(() => ({
  store: {} as Record<string, unknown>,
  matchScreenName: vi.fn(),
}))

vi.mock('@/store/useGenerateStore', () => ({
  useGenerateStore: () => mocks.store,
}))

vi.mock('@/composables/useTestPointLink', () => ({
  useTestPointLink: () => ({ matchScreenName: mocks.matchScreenName }),
}))

import ContextScreenPreview from '../ContextScreenPreview.vue'

const ElFormItemStub = defineComponent({
  name: 'ElFormItem',
  props: { label: { type: String, default: '' } },
  template: '<div class="el-form-item" :data-label="label"><slot /></div>',
})

const ElAlertStub = defineComponent({
  name: 'ElAlert',
  props: {
    title: { type: String, default: '' },
    type: { type: String, default: 'info' },
    closable: { type: Boolean, default: false },
  },
  emits: ['close'],
  template: `<div class="el-alert" :data-type="type"><span class="alert-title">{{ title }}</span>
    <i v-if="closable" class="alert-close" @click="$emit('close')"></i></div>`,
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: 'primary' }, effect: { type: String, default: 'light' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}</div>',
})

const FlowSortEditorStub = defineComponent({
  name: 'FlowSortEditor',
  props: {
    screens: { type: Array, default: () => [] },
    screenImageUrls: { type: Object, default: () => ({}) },
    moduleInfo: { type: Object, default: () => ({}) },
  },
  emits: ['update:sort-data', 'preview-screen', 'test-point-link'],
  setup(_props, { expose }) {
    expose({
      getFlowSortSubmitData: () => ({ flow_sort_data: { order: [1, 2] } }),
      getFlowValidationIssues: () => ({ errors: ['e1'], warnings: ['w1'] }),
    })
    return () => h('div', { class: 'flow-sort-editor-stub' })
  },
})

const stubs = {
  ElFormItem: ElFormItemStub,
  ElAlert: ElAlertStub,
  ElTag: ElTagStub,
  ElIcon: ElIconStub,
  ElEmpty: ElEmptyStub,
  FlowSortEditor: FlowSortEditorStub,
}

type Screen = { id: number; screen_name?: string; original_file_path?: string }

type StoreOverrides = {
  selectedProjectId?: number | null
  project?: Record<string, unknown> | null
  showParseWarning?: boolean
  screens?: Screen[]
  imageUrls?: Record<number, string>
  testPoints?: Array<Record<string, unknown>>
  statusType?: string
  statusText?: string
}

function setup(overrides: StoreOverrides = {}) {
  const screens = overrides.screens ?? [
    { id: 1, screen_name: '登录页' },
    { id: 2, screen_name: '首页' },
  ]
  const store = reactive({
    selectedUiPrototypeProjectId:
      overrides.selectedProjectId === undefined ? 5 : overrides.selectedProjectId,
    selectedUiPrototypeProject:
      overrides.project === undefined
        ? { id: 5, name: '原型V1', parse_status: 'completed', screen_count: 2, parsed_count: 2 }
        : overrides.project,
    showParseWarning: overrides.showParseWarning ?? true,
    uiScreens: screens,
    screenImageUrls: overrides.imageUrls ?? {},
    testPoints: overrides.testPoints ?? [],
    screenPreviewStatusType: overrides.statusType ?? 'success',
    screenPreviewStatusText: overrides.statusText ?? '已解析',
    flowSortModuleInfo: { module: '登录' },
    handleFlowSortUpdate: vi.fn(),
    loadScreenImages: vi.fn().mockImplementation(async () => {
      store.screenImageUrls[2] = 'blob:reloaded'
    }),
  })
  mocks.store = store

  const wrapper = mount(ContextScreenPreview, { global: { stubs } })
  return { store, wrapper }
}

function emitFromEditor(
  wrapper: ReturnType<typeof setup>['wrapper'],
  event: string,
  payload?: unknown
) {
  wrapper.findComponent(FlowSortEditorStub).vm.$emit(event, payload)
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({}) as never)
  mocks.matchScreenName.mockImplementation(
    (tp: { module?: string; point?: string }, name: string) =>
      (tp.point ?? '').includes('登录') && name.includes('登录')
  )
})

describe('ContextScreenPreview — 渲染条件', () => {
  it('未选择 UI 原型项目时不渲染', () => {
    const { wrapper } = setup({ selectedProjectId: null })

    expect(wrapper.find('.el-form-item').exists()).toBe(false)
  })

  it('解析未完成且允许提示时展示警告文案', () => {
    const { wrapper } = setup({
      project: { id: 5, name: '原型V1', parse_status: 'partial', screen_count: 4, parsed_count: 2 },
    })

    const alert = wrapper.find('.el-alert')
    expect(alert.attributes('data-type')).toBe('warning')
    expect(alert.find('.alert-title').text()).toBe(
      '该UI原型图部分解析（2/4），未解析的屏幕将无法获取详细元素信息'
    )
  })

  it('未解析时展示默认警告，关闭后写回 store', async () => {
    const { store, wrapper } = setup({
      project: { id: 5, name: '原型V1', parse_status: 'pending', screen_count: 2, parsed_count: 0 },
    })

    expect(wrapper.find('.alert-title').text()).toContain('该UI原型图尚未解析')
    await wrapper.find('.alert-close').trigger('click')

    expect(store.showParseWarning).toBe(false)
  })

  it('已解析或关闭提示后不展示警告', () => {
    expect(setup().wrapper.find('.el-alert').exists()).toBe(false)
    expect(
      setup({ showParseWarning: false, project: { parse_status: 'pending' } })
        .wrapper.find('.el-alert')
        .exists()
    ).toBe(false)
  })

  it('无屏幕时展示空态', () => {
    const { wrapper } = setup({ screens: [] })

    expect(wrapper.find('.el-empty').text()).toBe('该版本暂无屏幕')
    expect(wrapper.find('.flow-sort-editor-stub').exists()).toBe(false)
  })
})

describe('ContextScreenPreview — 概览区', () => {
  it('展示原型名称、屏幕数量与解析状态标签', () => {
    const { wrapper } = setup({ statusType: 'warning', statusText: '部分解析' })

    expect(wrapper.find('.preview-overview-name').text()).toBe('原型V1')
    const tags = wrapper.findAll('.preview-overview-title .el-tag')
    expect(tags.map((t) => t.text())).toEqual(['共 2 个屏幕', '部分解析'])
    expect(tags[1].attributes('data-type')).toBe('warning')
  })

  it('缺少项目名称时回退为当前UI版本', () => {
    const { wrapper } = setup({ project: null })

    expect(wrapper.find('.preview-overview-name').text()).toBe('当前UI版本')
  })

  it('提示区展示两种操作说明', () => {
    const { wrapper } = setup()

    expect(wrapper.findAll('.preview-tip-item span').map((s) => s.text())).toEqual([
      '点击预览',
      '拖拽调整顺序',
    ])
  })

  it('编辑器接收屏幕、图片与模块信息', () => {
    const { wrapper } = setup({ imageUrls: { 1: 'blob:1' } })

    const editor = wrapper.findComponent(FlowSortEditorStub)
    expect(editor.props('screens')).toHaveLength(2)
    expect(editor.props('screenImageUrls')).toEqual({ 1: 'blob:1' })
    expect(editor.props('moduleInfo')).toEqual({ module: '登录' })
  })
})

describe('ContextScreenPreview — 编辑器事件', () => {
  it('排序更新透传 store', () => {
    const { store, wrapper } = setup()
    const payload = { order: [2, 1] }

    emitFromEditor(wrapper, 'update:sort-data', payload)

    expect(store.handleFlowSortUpdate).toHaveBeenCalledWith(payload)
  })

  it('优先使用已缓存图片预览', async () => {
    const { wrapper } = setup({ imageUrls: { 1: 'blob:cached' } })

    emitFromEditor(wrapper, 'preview-screen', { screen_id: 1, screen_name: '登录页' })
    await flushPromises()

    expect(wrapper.emitted('preview-screen')).toEqual([['blob:cached']])
  })

  it('无缓存但存在原图时重新加载后预览', async () => {
    const { store, wrapper } = setup({
      screens: [{ id: 2, screen_name: '首页', original_file_path: '/a.png' }],
    })

    emitFromEditor(wrapper, 'preview-screen', { screen_id: 2, screen_name: '首页' })
    await flushPromises()

    expect(store.loadScreenImages).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('preview-screen')).toEqual([['blob:reloaded']])
  })

  it('无任何图片时给出提示', async () => {
    const { wrapper } = setup({ screens: [{ id: 3, screen_name: '设置页' }] })

    emitFromEditor(wrapper, 'preview-screen', { screen_id: 3, screen_name: '设置页' })
    await flushPromises()

    expect(ElMessage.warning).toHaveBeenCalledWith('该屏幕暂无可预览图片')
    expect(wrapper.emitted('preview-screen')).toBeUndefined()
  })

  it('屏幕不在列表中时使用事件携带的图片地址', async () => {
    const { wrapper } = setup()

    emitFromEditor(wrapper, 'preview-screen', {
      screen_id: 9,
      screen_name: '未知',
      image_url: 'blob:x',
    })
    await flushPromises()

    expect(wrapper.emitted('preview-screen')).toEqual([['blob:x']])
  })
})

describe('ContextScreenPreview — 测试点联动', () => {
  it('无屏幕或无测试点时返回空数组', () => {
    const noPoints = setup({ screens: [{ id: 1, screen_name: '登录页' }], testPoints: [] }).wrapper
    emitFromEditor(noPoints, 'test-point-link', [1])
    expect(noPoints.emitted('test-point-link')).toEqual([[[]]])

    const emptyIds = setup({ testPoints: [{ id: 1, point: '登录' }] }).wrapper
    emitFromEditor(emptyIds, 'test-point-link', [])
    expect(emptyIds.emitted('test-point-link')).toEqual([[[]]])
  })

  it('按屏幕名匹配测试点并去重', () => {
    const { wrapper } = setup({
      screens: [
        { id: 1, screen_name: '登录页' },
        { id: 2, screen_name: '首页' },
      ],
      testPoints: [
        { id: 10, module: '登录', point: '登录成功' },
        { id: 10, module: '登录', point: '登录失败' },
        { id: 11, module: '支付', point: '支付成功' },
      ],
    })

    emitFromEditor(wrapper, 'test-point-link', [1, 2])

    expect(wrapper.emitted('test-point-link')).toEqual([[[10]]])
  })

  it('屏幕未匹配到名称时返回空数组', () => {
    const { wrapper } = setup({
      screens: [{ id: 1, screen_name: '登录页' }],
      testPoints: [{ id: 10, point: '其它' }],
    })

    emitFromEditor(wrapper, 'test-point-link', [99])

    expect(wrapper.emitted('test-point-link')).toEqual([[[]]])
  })
})

describe('ContextScreenPreview — 暴露方法', () => {
  it('getFlowSortEditorRef 返回编辑器实例', () => {
    const { wrapper } = setup()

    const editorRef = (
      wrapper.vm as unknown as {
        getFlowSortEditorRef: () => { getFlowValidationIssues?: () => unknown } | null
      }
    ).getFlowSortEditorRef()

    expect(editorRef).not.toBeNull()
    expect(editorRef!.getFlowValidationIssues?.()).toEqual({ errors: ['e1'], warnings: ['w1'] })
  })
})
