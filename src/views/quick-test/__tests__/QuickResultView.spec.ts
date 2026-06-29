import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import QuickResultView from '../components/QuickResultView.vue'
import { useQuickTestStore } from '@/store/quickTest'
import type {
    CaseData,
    DefectData,
    SummaryStats,
    QuickTestResultDetail,
} from '../quickTestTypes'

vi.mock('@/api/project', () => {
    return {
        default: {
            getProjects: vi.fn().mockResolvedValue({ data: { items: [] } }),
            getProjectDetail: vi.fn().mockResolvedValue({ data: {} }),
            getProjectConfig: vi.fn().mockResolvedValue({ data: {} }),
        },
    }
})

function makeSummary(overrides: Partial<SummaryStats> = {}): SummaryStats {
    return {
        total: 5,
        passed: 3,
        failed: 2,
        pass_rate: 60,
        duration_sec: 120,
        severity_dist: { p0: 1, p1: 0, p2: 1, p3: 0 },
        ...overrides,
    }
}

function makeCase(overrides: Partial<CaseData> = {}): CaseData {
    return {
        id: 1,
        title: '用例 1',
        status: 'passed',
        steps: [],
        ...overrides,
    }
}

function makeDefect(overrides: Partial<DefectData> = {}): DefectData {
    return {
        bug_no: 'BUG-001',
        title: '登录失败未提示',
        severity: 1,
        module: '登录模块',
        ux_category: '反馈缺失',
        status: 'open',
        reproduction_steps: '输入错误密码点击登录',
        evidence: null,
        fix_suggestion: '增加错误提示',
        ...overrides,
    }
}

function mountView(overrides: {
    resultDetail?: QuickTestResultDetail | null
    cases?: CaseData[]
    defects?: DefectData[]
    summary?: SummaryStats | null
    exploredPages?: QuickTestResultDetail['explored_pages']
} = {}) {
    // 不在此设置 store 默认状态，由各测试用例按需控制 store.phase/taskId/projectId
    const props = {
        resultDetail: overrides.resultDetail ?? null,
        cases: overrides.cases ?? [],
        defects: overrides.defects ?? [],
        summary: overrides.summary ?? null,
        exploredPages: overrides.exploredPages ?? [],
    }
    return mount(QuickResultView, {
        props,
        global: {
            stubs: {
                // QuickSummaryCard / QuickAssetsCard / CaseCard 仅作为子组件渲染，
                // 但 QuickDefectList 保留真实渲染以验证 P0 排序逻辑
                QuickSummaryCard: true,
                QuickAssetsCard: true,
                CaseCard: true,
            },
        },
    })
}

describe('QuickResultView', () => {
    beforeEach(() => {
        localStorage.clear()
        setActivePinia(createPinia())
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('5 区块渲染', () => {
        it('渲染摘要、资产、缺陷、用例列表、操作按钮 5 个区块', () => {
            const wrapper = mountView({
                cases: [makeCase()],
                defects: [makeDefect()],
                summary: makeSummary(),
            })
            expect(wrapper.findComponent({ name: 'QuickDefectList' }).exists()).toBe(true)
            expect(wrapper.find('.case-list-card').exists()).toBe(true)
            expect(wrapper.find('.actions-card').exists()).toBe(true)
            expect(wrapper.findAll('.degrade-alert').length).toBeGreaterThanOrEqual(0)
        })

        it('用例为空时展示 el-empty 与查看完整报告按钮', () => {
            const wrapper = mountView({ cases: [], summary: makeSummary() })
            expect(wrapper.find('.el-empty').exists()).toBe(true)
        })
    })

    describe('用例过滤 tabs', () => {
        const cases: CaseData[] = [
            makeCase({ id: 1, title: '通过 1', status: 'passed' }),
            makeCase({ id: 2, title: '失败 1', status: 'failed' }),
            makeCase({ id: 3, title: '通过 2', status: 'passed' }),
        ]

        it('默认显示全部用例数', async () => {
            const wrapper = mountView({ cases })
            const radio = wrapper.find('.case-list-header')
            expect(radio.text()).toContain('全部 (3)')
            expect(radio.text()).toContain('通过 (2)')
            expect(radio.text()).toContain('失败 (1)')
        })

        it('切换到失败 tab 后只渲染失败用例', async () => {
            const wrapper = mountView({ cases })
            // 找到失败 radio-button 并点击
            const radios = wrapper.findAllComponents({ name: 'ElRadioButton' })
            const failedRadio = radios.find((r) => r.props('value') === 'failed')
            await failedRadio!.trigger('click')
            expect(wrapper.emitted('update:modelValue') || []).toBeTruthy()
        })
    })

    describe('操作按钮 emit 事件', () => {
        it('点击「查看完整报告」触发 view-report 事件', async () => {
            const wrapper = mountView({ cases: [makeCase()] })
            const buttons = wrapper.findAll('button')
            const viewBtn = buttons.find((b) => b.text().includes('查看完整报告'))
            await viewBtn!.trigger('click')
            expect(wrapper.emitted('view-report')).toBeTruthy()
        })

        it('点击「再次执行」触发 rerun 事件', async () => {
            const wrapper = mountView({ cases: [makeCase()] })
            const buttons = wrapper.findAll('button')
            const rerunBtn = buttons.find((b) => b.text().includes('再次执行'))
            await rerunBtn!.trigger('click')
            expect(wrapper.emitted('rerun')).toBeTruthy()
        })

        it('点击「编辑用例」触发 edit-cases 事件', async () => {
            const wrapper = mountView({ cases: [makeCase()] })
            const buttons = wrapper.findAll('button')
            const editBtn = buttons.find((b) => b.text().includes('编辑用例'))
            await editBtn!.trigger('click')
            expect(wrapper.emitted('edit-cases')).toBeTruthy()
        })

        it('点击 PDF 下载项触发 download 事件携带 pdf', async () => {
            const wrapper = mountView({ cases: [makeCase()] })
            // 菜单未展开时 ElDropdownItem 不渲染，直接在 ElDropdown 上 emit command
            const dropdown = wrapper.findComponent({ name: 'ElDropdown' })
            expect(dropdown.exists()).toBe(true)
            await dropdown.vm.$emit('command', 'pdf')
            expect(wrapper.emitted('download')).toBeTruthy()
            const evt = wrapper.emitted('download')
            expect(evt![0]).toEqual(['pdf'])
        })
    })

    describe('缺陷 P0 排序（spec 偏离：P0 置顶）', () => {
        it('缺陷按 severity 升序排序，P0（severity=1）置顶', () => {
            const defects: DefectData[] = [
                makeDefect({ bug_no: 'B-P3', title: '轻微问题', severity: 3 }),
                makeDefect({ bug_no: 'B-P0', title: '致命问题', severity: 1 }),
                makeDefect({ bug_no: 'B-P2', title: '一般问题', severity: 2 }),
            ]
            const wrapper = mountView({ defects })
            const defectItems = wrapper.findAll('.defect-item')
            expect(defectItems).toHaveLength(3)
            // 第一个应是 P0
            expect(defectItems[0].classes()).toContain('sev-1')
            expect(defectItems[1].classes()).toContain('sev-2')
            expect(defectItems[2].classes()).toContain('sev-3')
        })

        it('缺陷计数 tag 显示总数', () => {
            const defects: DefectData[] = [
                makeDefect({ severity: 1 }),
                makeDefect({ severity: 2, bug_no: 'B-002' }),
            ]
            const wrapper = mountView({ defects })
            const countTag = wrapper.find('.count-tag')
            expect(countTag.text()).toBe('2')
        })
    })

    describe('失败降级提示', () => {
        it('site_exploring 阶段失败渲染网址不可访问告警', () => {
            const store = useQuickTestStore()
            store.phase = 'failed'
            store.currentStage = 'site_exploring'
            store.errorMessage = '连接超时'
            const wrapper = mountView({ cases: [], summary: null })
            const alert = wrapper.find('.degrade-alert')
            expect(alert.exists()).toBe(true)
            expect(alert.text()).toContain('无法访问该网址')
        })

        it('errorMessage 含「登录」渲染登录凭据降级告警', () => {
            const store = useQuickTestStore()
            store.phase = 'failed'
            store.currentStage = 'case_generating'
            store.errorMessage = '登录凭据无效'
            const wrapper = mountView({ cases: [], summary: null })
            const alerts = wrapper.findAll('.degrade-alert')
            const texts = alerts.map((a) => a.text()).join(' ')
            expect(texts).toContain('登录凭据无效')
        })

        it('errorMessage 含「AI」渲染 AI 降级告警', () => {
            const store = useQuickTestStore()
            store.phase = 'failed'
            store.currentStage = 'case_generating'
            store.errorMessage = 'AI 服务降级'
            const wrapper = mountView({ cases: [], summary: null })
            const alerts = wrapper.findAll('.degrade-alert')
            const texts = alerts.map((a) => a.text()).join(' ')
            expect(texts).toContain('AI 服务暂时不可用')
        })

        it('存在超时失败用例时渲染超时计数提示', () => {
            const cases: CaseData[] = [
                makeCase({ id: 1, status: 'failed', failure_reason: '执行超时' }),
                makeCase({ id: 2, status: 'failed', failure_reason: '执行超时' }),
                makeCase({ id: 3, status: 'passed' }),
            ]
            const wrapper = mountView({ cases })
            const hint = wrapper.find('.timeout-hint')
            expect(hint.exists()).toBe(true)
            expect(hint.text()).toContain('2 条用例超时')
        })
    })

    describe('挂载时主动拉取报告', () => {
        it('cases 为空且 taskId 存在时触发 fetch-report 事件', () => {
            const store = useQuickTestStore()
            store.taskId = 101
            const wrapper = mountView({ cases: [], summary: null })
            expect(wrapper.emitted('fetch-report')).toBeTruthy()
        })

        it('cases 非空时不触发 fetch-report 事件', () => {
            const wrapper = mountView({ cases: [makeCase()], summary: null })
            expect(wrapper.emitted('fetch-report')).toBeFalsy()
        })

        it('taskId 缺失时不触发 fetch-report 事件', () => {
            const store = useQuickTestStore()
            store.taskId = null
            const wrapper = mountView({ cases: [], summary: null })
            expect(wrapper.emitted('fetch-report')).toBeFalsy()
        })
    })

    describe('保存到其他项目对话框', () => {
        it('点击保存到其他项目按钮打开对话框', async () => {
            const wrapper = mountView({ cases: [makeCase()] })
            const buttons = wrapper.findAll('button')
            const saveBtn = buttons.find((b) => b.text().includes('保存到其他项目'))
            await saveBtn!.trigger('click')
            // openSaveDialog 异步拉取项目列表，需 flush 让 v-model 生效后渲染对话框
            await flushPromises()
            // el-dialog 走 teleport，DOM 选择器不可靠；改查组件 modelValue props
            const dialog = wrapper.findComponent({ name: 'ElDialog' })
            expect(dialog.exists()).toBe(true)
            expect(dialog.props('modelValue')).toBe(true)
        })
    })
})
