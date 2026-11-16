import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'
import type { TestPoint } from '@/types/testPoint'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  startAnalysis: vi.fn(),
  fetchTestPoints: vi.fn(),
  generateCases: vi.fn(),
  projectId: '7',
  analysisState: {
    status: 'idle',
    progress: 0,
    message: '',
    testPoints: [] as TestPoint[],
  },
  caseState: { generateStatus: 'idle' },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { projectId: mocks.projectId } }),
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/store/analysis', () => ({
  useAnalysisStore: () => ({
    get status() {
      return mocks.analysisState.status
    },
    get progress() {
      return mocks.analysisState.progress
    },
    get message() {
      return mocks.analysisState.message
    },
    get testPoints() {
      return mocks.analysisState.testPoints
    },
    startAnalysis: mocks.startAnalysis,
    fetchTestPoints: mocks.fetchTestPoints,
  }),
}))

vi.mock('@/store/case', () => ({
  useCaseStore: () =>
    reactive({
      get generateStatus() {
        return mocks.caseState.generateStatus
      },
      generateCases: mocks.generateCases,
    }),
}))

import AnalysisPage from '../AnalysisPage.vue'

function makePoint(id: number, module: string, priority = 1): TestPoint {
  return {
    id,
    project_id: 7,
    module,
    point: `测试点 ${id}`,
    priority,
    create_time: '2026-11-16 08:00:00',
  } as unknown as TestPoint
}

async function mountPage() {
  const wrapper = mount(AnalysisPage)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mockConfirm()
  mocks.projectId = '7'
  mocks.analysisState = { status: 'idle', progress: 0, message: '', testPoints: [] }
  mocks.caseState = { generateStatus: 'idle' }
  mocks.startAnalysis.mockResolvedValue(undefined)
  mocks.generateCases.mockResolvedValue(undefined)
})

describe('AnalysisPage — 初始化', () => {
  it('按路由项目 ID 拉取测试点', async () => {
    await mountPage()

    expect(mocks.fetchTestPoints).toHaveBeenCalledWith(7)
  })

  it('项目 ID 缺失时不拉取', async () => {
    mocks.projectId = ''

    await mountPage()

    expect(mocks.fetchTestPoints).not.toHaveBeenCalled()
  })

  it('渲染项目文件列表', async () => {
    const wrapper = await mountPage()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows.length).toBeGreaterThanOrEqual(2)
    expect(wrapper.text()).toContain('需求文档.docx')
    expect(wrapper.text()).toContain('登录页面原型.png')
  })
})

describe('AnalysisPage — 分析状态', () => {
  it('分析中按钮禁用、文案切换并展示进度条', async () => {
    mocks.analysisState = {
      status: 'analyzing',
      progress: 45,
      message: '正在解析文档',
      testPoints: [],
    }
    const wrapper = await mountPage()

    const startBtn = wrapper.findAll('.el-button')[0]
    expect(startBtn.text()).toBe('分析中...')
    expect(startBtn.attributes('disabled')).toBeDefined()

    const progress = wrapper.findComponent({ name: 'ElProgress' }).exists()
      ? wrapper.findComponent({ name: 'ElProgress' })
      : wrapper.findComponent({ name: 'ProgressBar' })
    expect(progress.exists()).toBe(true)
    expect(wrapper.text()).toContain('正在解析文档')
  })

  it('分析失败展示错误告警', async () => {
    mocks.analysisState = {
      status: 'failed',
      progress: 0,
      message: '文档解析失败',
      testPoints: [],
    }
    const wrapper = await mountPage()

    expect(wrapper.find('.el-alert').text()).toContain('文档解析失败')
  })

  it('分析成功但无测试点时展示空态', async () => {
    mocks.analysisState = { status: 'success', progress: 100, message: '', testPoints: [] }
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('未提取到测试点，请检查需求文档内容')
  })

  it('点击开始分析需二次确认后才调用接口', async () => {
    const wrapper = await mountPage()

    await wrapper.findAll('.el-button')[0].trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mocks.startAnalysis).toHaveBeenCalledWith(7)
  })

  it('取消确认时不发起分析', async () => {
    mockCancel()
    const wrapper = await mountPage()

    await wrapper.findAll('.el-button')[0].trigger('click')
    await flushPromises()

    expect(mocks.startAnalysis).not.toHaveBeenCalled()
  })
})

describe('AnalysisPage — 测试点结果', () => {
  it('按模块分组渲染折叠项、优先级标签与用例数', async () => {
    mocks.analysisState = {
      status: 'success',
      progress: 100,
      message: '',
      testPoints: [makePoint(1, '订单', 1), makePoint(2, '订单', 2), makePoint(3, '支付', 3)],
    }
    const wrapper = await mountPage()

    const titles = wrapper.findAll('.el-collapse-item__header').map((node) => node.text())
    expect(titles).toEqual(['订单 (2个测试点)', '支付 (1个测试点)'])

    const tags = wrapper.findAll('.priority-tag')
    expect(tags.map((node) => node.text())).toEqual(['高', '中', '低'])
    expect(tags[0].classes()).toContain('high')
    expect(tags[1].classes()).toContain('medium')
    expect(tags[2].classes()).toContain('low')
  })

  it('按模块筛选只保留命中的分组', async () => {
    mocks.analysisState = {
      status: 'success',
      progress: 100,
      message: '',
      testPoints: [makePoint(1, '订单'), makePoint(3, '支付')],
    }
    const wrapper = await mountPage()

    const moduleSelect = wrapper.findAllComponents({ name: 'ElSelect' })[0]
    moduleSelect.vm.$emit('update:modelValue', '支付')
    await flushPromises()

    const titles = wrapper.findAll('.el-collapse-item__header').map((node) => node.text())
    expect(titles).toEqual(['支付 (1个测试点)'])
  })

  it('按优先级筛选只保留命中测试点', async () => {
    mocks.analysisState = {
      status: 'success',
      progress: 100,
      message: '',
      testPoints: [makePoint(1, '订单', 1), makePoint(2, '订单', 3)],
    }
    const wrapper = await mountPage()

    wrapper.findAllComponents({ name: 'ElSelect' })[1].vm.$emit('update:modelValue', '3')
    await flushPromises()

    expect(wrapper.findAll('.priority-tag').map((node) => node.text())).toEqual(['低'])
  })
})

describe('AnalysisPage — 生成用例', () => {
  it('生成全部用例成功后提示并跳转', async () => {
    mocks.analysisState = {
      status: 'success',
      progress: 100,
      message: '',
      testPoints: [makePoint(1, '订单')],
    }
    mocks.caseState = { generateStatus: 'success' }
    const wrapper = await mountPage()

    const allBtn = wrapper.findAll('.el-button').find((n) => n.text().includes('生成所有测试用例'))!
    await allBtn.trigger('click')
    await flushPromises()

    expect(mocks.generateCases).toHaveBeenCalledWith(7, [1])
    expect(ElMessage.success).toHaveBeenCalledWith('测试用例生成成功')
    expect(mocks.push).toHaveBeenCalledWith({ path: '/home/case', query: { projectId: '7' } })
  })

  it('筛选后无测试点时拒绝生成', async () => {
    mocks.analysisState = {
      status: 'success',
      progress: 100,
      message: '',
      testPoints: [makePoint(1, '订单')],
    }
    const wrapper = await mountPage()

    wrapper.findAllComponents({ name: 'ElSelect' })[0].vm.$emit('update:modelValue', '不存在')
    await flushPromises()

    const allBtn = wrapper.findAll('.el-button').find((n) => n.text().includes('生成所有测试用例'))!
    await allBtn.trigger('click')
    await flushPromises()

    expect(ElMessage.warning).toHaveBeenCalledWith('当前没有可生成的测试点')
    expect(mocks.generateCases).not.toHaveBeenCalled()
  })

  it('未选中测试点时生成选中按钮禁用', async () => {
    mocks.analysisState = {
      status: 'success',
      progress: 100,
      message: '',
      testPoints: [makePoint(1, '订单')],
    }
    const wrapper = await mountPage()

    const selectedBtn = wrapper
      .findAll('.el-button')
      .find((n) => n.text().includes('生成选中测试用例'))!
    expect(selectedBtn.attributes('disabled')).toBeDefined()
    expect(selectedBtn.text()).toContain('(0)')
  })

  it('勾选测试点后按选中项生成', async () => {
    mocks.analysisState = {
      status: 'success',
      progress: 100,
      message: '',
      testPoints: [makePoint(1, '订单'), makePoint(2, '订单')],
    }
    mocks.caseState = { generateStatus: 'success' }
    const wrapper = await mountPage()

    const moduleTable = wrapper.findAllComponents({ name: 'ElTable' })[1]
    moduleTable.vm.$emit('selection-change', [makePoint(1, '订单')])
    await flushPromises()

    const selectedBtn = wrapper
      .findAll('.el-button')
      .find((n) => n.text().includes('生成选中测试用例'))!
    expect(selectedBtn.text()).toContain('(1)')

    await selectedBtn.trigger('click')
    await flushPromises()

    expect(mocks.generateCases).toHaveBeenCalledWith(7, [1])
  })

  it('生成失败（status 非 success）时不跳转', async () => {
    mocks.analysisState = {
      status: 'success',
      progress: 100,
      message: '',
      testPoints: [makePoint(1, '订单')],
    }
    mocks.caseState = { generateStatus: 'failed' }
    const wrapper = await mountPage()

    const allBtn = wrapper.findAll('.el-button').find((n) => n.text().includes('生成所有测试用例'))!
    await allBtn.trigger('click')
    await flushPromises()

    expect(mocks.push).not.toHaveBeenCalled()
  })
})
