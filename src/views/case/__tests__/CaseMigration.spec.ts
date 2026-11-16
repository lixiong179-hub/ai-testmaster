import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import type { MigrationPreviewItem, MigrationPreviewResponse } from '@/api/caseMigration'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  getProjects: vi.fn(),
  getCaseList: vi.fn(),
  getUIPrototypeProjectList: vi.fn(),
  getUIScreenList: vi.fn(),
  importExcel: vi.fn(),
  previewBatch: vi.fn(),
  commitBatch: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/api/project', () => ({
  default: { getProjects: mocks.getProjects },
}))

vi.mock('@/api/case', () => ({
  caseApi: { getList: mocks.getCaseList },
}))

vi.mock('@/api/uiPrototype', () => ({
  uiPrototypeApi: {
    getUIPrototypeProjectList: mocks.getUIPrototypeProjectList,
    getUIScreenList: mocks.getUIScreenList,
  },
}))

// 保留 summarizeUiSpecs / caseOptionLabel 的真实实现，仅替换网络方法
vi.mock('@/api/caseMigration', async () => {
  const actual = await vi.importActual<typeof import('@/api/caseMigration')>('@/api/caseMigration')
  return {
    ...actual,
    caseMigrationApi: {
      importExcel: mocks.importExcel,
      previewBatch: mocks.previewBatch,
      commitBatch: mocks.commitBatch,
    },
  }
})

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
import CaseMigration from '../CaseMigration.vue'

const messageMock = ElMessage as unknown as ReturnType<typeof vi.fn> & {
  success: ReturnType<typeof vi.fn>
  warning: ReturnType<typeof vi.fn>
}

function makePreviewItem(overrides: Partial<MigrationPreviewItem> = {}): MigrationPreviewItem {
  return {
    batch_id: 'batch-1',
    source_case_id: 11,
    migration_type: 'cloned',
    confidence: 0.876,
    preview_cases: [{ title: '迁移后的用例A' }],
    step_changes: [],
    warnings: [],
    errors: [],
    ...overrides,
  }
}

function makePreview(overrides: Partial<MigrationPreviewResponse> = {}): MigrationPreviewResponse {
  return {
    batch_id: 'batch-1',
    source_device: 'tablet',
    target_device: 'phone',
    summary: {
      total: 1,
      success: 1,
      failed: 0,
      cloned: 1,
      adapted: 0,
      split: 0,
      new: 0,
      deprecated: 0,
    },
    items: [makePreviewItem()],
    ...overrides,
  }
}

function mountPage() {
  return mount(CaseMigration)
}

function selectByPlaceholder(wrapper: ReturnType<typeof mount>, placeholder: string) {
  const select = wrapper
    .findAllComponents({ name: 'ElSelect' })
    .find((item) => item.props('placeholder') === placeholder)
  if (!select) throw new Error(`未找到 placeholder=${placeholder} 的 el-select`)
  return select
}

function deviceSelects(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'ElSelect' })
    .filter((item) => item.classes().includes('device-select'))
}

async function emitSelect(wrapper: ReturnType<typeof mount>, placeholder: string, value: unknown) {
  const select = selectByPlaceholder(wrapper, placeholder)
  select.vm.$emit('update:modelValue', value)
  select.vm.$emit('change', value)
  await flushPromises()
}

async function chooseUploadFile(wrapper: ReturnType<typeof mount>, file: File | null) {
  const upload = wrapper.findComponent({ name: 'ElUpload' })
  const onChange = upload.props('onChange') as (f: { raw: File | null }) => void
  const onRemove = upload.props('onRemove') as () => void
  if (file) onChange({ raw: file })
  else onRemove()
  await nextTick()
}

function findButton(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAll('button').find((btn) => btn.text().includes(text))
}

/** 走完一遍前置选择，让「生成迁移预览」可点击 */
async function fillReadyState(wrapper: ReturnType<typeof mount>) {
  await emitSelect(wrapper, '选择旧端项目', 1)
  await emitSelect(wrapper, '选择要迁移的旧端用例', [11, 12])
  await emitSelect(wrapper, '选择新端项目', 2)
  await emitSelect(wrapper, '选择已解析的新端UI原型', 21)
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getProjects.mockResolvedValue({
    data: {
      items: [
        { id: 1, name: '旧端项目' },
        { id: 2, name: '新端项目' },
      ],
    },
  })
  mocks.getCaseList.mockResolvedValue({
    items: [
      { id: 11, case_no: 'OLD-1', title: '旧用例一' },
      { id: 12, case_no: 'OLD-2', title: '旧用例二' },
    ],
  })
  mocks.getUIPrototypeProjectList.mockResolvedValue([
    { id: 21, name: '新端原型', screen_count: 3, parsed_count: 2 },
  ])
  mocks.getUIScreenList.mockResolvedValue({
    data: {
      items: [
        { id: 1, screen_name: '首页', parse_status: 'completed', summary: '首页摘要' },
        { id: 2, screen_name: '详情页', parse_status: 'completed', summary: '' },
        { id: 3, screen_name: '待解析页', parse_status: 'pending' },
      ],
    },
  })
  mocks.importExcel.mockResolvedValue({ imported_count: 1, imported_case_ids: [13] })
  mocks.previewBatch.mockResolvedValue(makePreview())
  mocks.commitBatch.mockResolvedValue({
    success: true,
    batch_id: 'batch-1',
    created_case_ids: [101, 102],
    errors: [],
  })
})

describe('CaseMigration — 初始化与导航', () => {
  it('挂载后拉取项目列表', async () => {
    mountPage()
    await flushPromises()

    expect(mocks.getProjects).toHaveBeenCalledWith({ page: 1, page_size: 200 })
  })

  it('默认设备为平板迁移到手机', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const [source, target] = deviceSelects(wrapper)
    expect(source.props('modelValue')).toBe('tablet')
    expect(target.props('modelValue')).toBe('phone')
  })

  it('点击返回用例列表跳转用例页', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await findButton(wrapper, '返回用例列表')!.trigger('click')

    expect(mocks.push).toHaveBeenCalledWith('/home/case')
  })
})

describe('CaseMigration — 来源用例加载', () => {
  it('选择源项目后按项目拉取源用例', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await emitSelect(wrapper, '选择旧端项目', 1)

    expect(mocks.getCaseList).toHaveBeenCalledWith(1, { page: 1, page_size: 200 })
  })

  it('未选择源项目时不拉取源用例', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await emitSelect(wrapper, '选择旧端项目', undefined)

    expect(mocks.getCaseList).not.toHaveBeenCalled()
  })

  it('未选择文件或项目时「导入为迁移源」禁用，选择后可点击', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const importBtn = () =>
      wrapper
        .findAllComponents({ name: 'ElButton' })
        .find((b) => b.text().includes('导入为迁移源'))!
    expect(importBtn().props('disabled')).toBe(true)

    await emitSelect(wrapper, '选择旧端项目', 1)
    await chooseUploadFile(wrapper, new File(['x'], 'old.xlsx'))
    expect(importBtn().props('disabled')).toBe(false)

    await chooseUploadFile(wrapper, null)
    expect(importBtn().props('disabled')).toBe(true)
  })

  it('导入 Excel 后合并去重源用例、刷新列表并提示数量', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await emitSelect(wrapper, '选择旧端项目', 1)
    await emitSelect(wrapper, '选择要迁移的旧端用例', [11])
    const file = new File(['x'], 'old.xlsx')
    await chooseUploadFile(wrapper, file)
    mocks.getCaseList.mockClear()

    await findButton(wrapper, '导入为迁移源')!.trigger('click')
    await flushPromises()

    expect(mocks.importExcel).toHaveBeenCalledWith({
      file,
      projectId: 1,
      targetDevice: 'tablet',
    })
    expect(mocks.getCaseList).toHaveBeenCalledTimes(1)
    expect(messageMock.success).toHaveBeenCalledWith('导入 1 条源用例')
  })
})

describe('CaseMigration — 目标 UI 原型', () => {
  it('选择目标项目后拉取 UI 原型列表并清空已选原型', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await emitSelect(wrapper, '选择新端项目', 2)

    expect(mocks.getUIPrototypeProjectList).toHaveBeenCalledWith(2)
  })

  it('未选择目标项目时不拉取 UI 原型', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await emitSelect(wrapper, '选择新端项目', undefined)

    expect(mocks.getUIPrototypeProjectList).not.toHaveBeenCalled()
  })

  it('选择 UI 原型后只统计已解析页面并展示标签', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await emitSelect(wrapper, '选择新端项目', 2)

    await emitSelect(wrapper, '选择已解析的新端UI原型', 21)

    expect(mocks.getUIScreenList).toHaveBeenCalledWith(2, 21)
    expect(wrapper.find('.inline-tag').text()).toBe('已解析 2 个页面')
  })

  it('没有已完成页面时不展示解析标签', async () => {
    mocks.getUIScreenList.mockResolvedValue({
      data: { items: [{ id: 3, screen_name: '待解析页', parse_status: 'pending' }] },
    })
    const wrapper = mountPage()
    await flushPromises()
    await emitSelect(wrapper, '选择新端项目', 2)

    await emitSelect(wrapper, '选择已解析的新端UI原型', 21)

    expect(wrapper.find('.inline-tag').exists()).toBe(false)
  })
})

describe('CaseMigration — 预览生成条件', () => {
  it('条件不满足时「生成迁移预览」禁用，满足后启用', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const previewBtn = () =>
      wrapper
        .findAllComponents({ name: 'ElButton' })
        .find((b) => b.text().includes('生成迁移预览'))!

    expect(previewBtn().props('disabled')).toBe(true)

    await fillReadyState(wrapper)

    expect(previewBtn().props('disabled')).toBe(false)
  })

  it('源设备与目标设备相同时不满足预览条件', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await fillReadyState(wrapper)

    const [, target] = deviceSelects(wrapper)
    target.vm.$emit('update:modelValue', 'tablet')
    await nextTick()

    const previewBtn = wrapper
      .findAllComponents({ name: 'ElButton' })
      .find((b) => b.text().includes('生成迁移预览'))!
    expect(previewBtn.props('disabled')).toBe(true)
  })

  it('未选择源用例时不满足预览条件', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await emitSelect(wrapper, '选择新端项目', 2)
    await emitSelect(wrapper, '选择已解析的新端UI原型', 21)

    const previewBtn = wrapper
      .findAllComponents({ name: 'ElButton' })
      .find((b) => b.text().includes('生成迁移预览'))!
    expect(previewBtn.props('disabled')).toBe(true)
  })
})

describe('CaseMigration — 预览与入库', () => {
  it('点击生成预览时按当前选择组装请求并提示成功', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await fillReadyState(wrapper)

    await findButton(wrapper, '生成迁移预览')!.trigger('click')
    await flushPromises()

    expect(mocks.previewBatch).toHaveBeenCalledWith({
      sourceCaseIds: [11, 12],
      sourceDevice: 'tablet',
      targetDevice: 'phone',
      targetProjectId: 2,
      targetUiSpecs: '1. 首页: 首页摘要\n2. 详情页: 无摘要',
    })
    expect(messageMock.success).toHaveBeenCalledWith('迁移预览已生成')
  })

  it('渲染预览卡片：批次号、统计与迁移类型', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await fillReadyState(wrapper)
    await findButton(wrapper, '生成迁移预览')!.trigger('click')
    await flushPromises()

    const card = wrapper.findAll('.step-card')[1]
    expect(card.text()).toContain('batch-1')
    expect(card.find('.summary-row').text()).toContain('总数')
    expect(card.text()).toContain('直接复用')
    expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
  })

  it('预览表格展示置信度百分比、产出用例与错误信息', async () => {
    mocks.previewBatch.mockResolvedValue(
      makePreview({
        items: [
          makePreviewItem({
            migration_type: 'split',
            confidence: 0.876,
            preview_cases: [{ title: '拆分后的用例A' }, { title: '拆分后的用例B' }],
            errors: ['缺少前置条件'],
          }),
          makePreviewItem({
            source_case_id: 12,
            migration_type: 'deprecated',
            confidence: 0,
            preview_cases: [],
            warnings: ['页面已下线'],
          }),
        ],
        summary: {
          total: 2,
          success: 1,
          failed: 1,
          cloned: 0,
          adapted: 0,
          split: 1,
          new: 0,
          deprecated: 1,
        },
      })
    )
    const wrapper = mountPage()
    await flushPromises()
    await fillReadyState(wrapper)
    await findButton(wrapper, '生成迁移预览')!.trigger('click')
    await flushPromises()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('拆分')
    expect(rows[0].text()).toContain('88%')
    expect(rows[0].text()).toContain('拆分后的用例A')
    expect(rows[0].text()).toContain('缺少前置条件')
    expect(rows[1].text()).toContain('废弃')
    expect(rows[1].text()).toContain('无新增用例')
    expect(rows[1].text()).toContain('页面已下线')
  })

  it('无错误与警告时问题列展示占位符', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await fillReadyState(wrapper)
    await findButton(wrapper, '生成迁移预览')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.el-table__row').text()).toContain('—')
  })

  it('确认入库成功后提示创建数量', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await fillReadyState(wrapper)
    await findButton(wrapper, '生成迁移预览')!.trigger('click')
    await flushPromises()

    await findButton(wrapper, '确认入库为草稿用例')!.trigger('click')
    await flushPromises()

    expect(mocks.commitBatch).toHaveBeenCalledWith({
      batchId: 'batch-1',
      targetProjectId: 2,
      targetDevice: 'phone',
      items: makePreview().items,
    })
    expect(messageMock.success).toHaveBeenCalledWith('已创建 2 条草稿用例')
  })

  it('入库返回部分错误时给出警告文案', async () => {
    mocks.commitBatch.mockResolvedValue({
      success: false,
      batch_id: 'batch-1',
      created_case_ids: [101],
      errors: ['用例 12 迁移失败'],
    })
    const wrapper = mountPage()
    await flushPromises()
    await fillReadyState(wrapper)
    await findButton(wrapper, '生成迁移预览')!.trigger('click')
    await flushPromises()

    await findButton(wrapper, '确认入库为草稿用例')!.trigger('click')
    await flushPromises()

    expect(messageMock.warning).toHaveBeenCalledWith('已创建 1 条，部分失败')
  })

  it('未生成预览时不渲染入库区域', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(findButton(wrapper, '确认入库为草稿用例')).toBeFalsy()
    expect(wrapper.findAll('.step-card')).toHaveLength(1)
  })
})
