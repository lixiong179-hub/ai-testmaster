import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import EvidenceRefsPanel from '../EvidenceRefsPanel.vue'
import type { ContextStats, EvidenceRefs, ServerWarning } from '@/store/generate/types'

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElTooltipStub = defineComponent({
  name: 'ElTooltip',
  props: { content: { type: String, default: '' } },
  template: '<span class="el-tooltip" :data-content="content"><slot /></span>',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}</div>',
})

const stubs = {
  ElIcon: ElIconStub,
  ElTag: ElTagStub,
  ElTooltip: ElTooltipStub,
  ElEmpty: ElEmptyStub,
}

function refs(overrides: Partial<EvidenceRefs> = {}): EvidenceRefs {
  return {
    requirements: [],
    requirement_files: [],
    ui_screens: [],
    history_cases: [],
    ...overrides,
  } as unknown as EvidenceRefs
}

function mountPanel(evidenceRefs: EvidenceRefs) {
  return mount(EvidenceRefsPanel, {
    props: {
      contextStats: null as ContextStats | null,
      warnings: [] as ServerWarning[],
      evidenceRefs,
    },
    global: { stubs },
  })
}

const sectionLabels = (wrapper: ReturnType<typeof mountPanel>) =>
  wrapper.findAll('.section-label').map((l) => l.text().replace(/\s+/g, ''))

describe('EvidenceRefsPanel — 需求依据', () => {
  it('合并 requirements 与 requirement_files 并统计条数', () => {
    const wrapper = mountPanel(
      refs({
        requirements: [{ id: 1, title: '登录需求', req_no: 'REQ-1' }],
        requirement_files: [{ id: 2, name: '需求文档A' }],
      } as unknown as Partial<EvidenceRefs>)
    )

    expect(sectionLabels(wrapper)).toEqual(['需求依据2条'])
    const items = wrapper.findAll('.evidence-item')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('登录需求')
    expect(items[0].text()).toContain('REQ-1')
    expect(items[1].text()).toContain('需求文档A')
    // 无编号时不渲染编号标签
    expect(items[1].findAll('.el-tag')).toHaveLength(0)
  })

  it('标题回退链 title → name → screen_name → #id，编号回退链 req_no → no → case_no → code', () => {
    const wrapper = mountPanel(
      refs({
        requirements: [{ id: 5, screen_name: '页面名', code: 'C-5' }, { id: 6 }],
      } as unknown as Partial<EvidenceRefs>)
    )

    const items = wrapper.findAll('.evidence-item')
    expect(items[0].text()).toContain('页面名')
    expect(items[0].text()).toContain('C-5')
    expect(items[1].text()).toContain('#6')
  })
})

describe('EvidenceRefsPanel — UI 依据', () => {
  it('按置信度映射标签类型', () => {
    const wrapper = mountPanel(
      refs({
        ui_screens: [
          { id: 1, screen_name: '登录页', confidence: 'explicit' },
          { id: 2, screen_name: '首页', confidence: 'matched' },
          { id: 3, name: '列表页', confidence: 'adjacent' },
        ],
      } as unknown as Partial<EvidenceRefs>)
    )

    expect(sectionLabels(wrapper)).toEqual(['UI依据3条'])
    const tags = wrapper.findAll('.evidence-item .el-tag')
    expect(tags.map((t) => t.text())).toEqual([
      '置信度 explicit',
      '置信度 matched',
      '置信度 adjacent',
    ])
    expect(tags.map((t) => t.attributes('data-type'))).toEqual(['success', 'warning', 'info'])
    expect(wrapper.text()).toContain('列表页')
  })

  it('数值置信度与 match_score 转为字符串，缺失则不渲染标签', () => {
    const wrapper = mountPanel(
      refs({
        ui_screens: [
          { id: 1, screen_name: 'A', confidence: 0.9 },
          { id: 2, screen_name: 'B', match_score: 12 },
          { id: 3, screen_name: 'C' },
        ],
      } as unknown as Partial<EvidenceRefs>)
    )

    const tags = wrapper.findAll('.evidence-item .el-tag')
    expect(tags.map((t) => t.text())).toEqual(['置信度 0.9', '置信度 12'])
    expect(tags[0].attributes('data-type')).toBe('info')
  })

  it('名称回退 prototype_name 与 页面 #id', () => {
    const wrapper = mountPanel(
      refs({
        ui_screens: [{ id: 7, prototype_name: '原型页' }, { id: 8 }],
      } as unknown as Partial<EvidenceRefs>)
    )

    const items = wrapper.findAll('.evidence-item')
    expect(items[0].text()).toContain('原型页')
    expect(items[1].text()).toContain('页面 #8')
  })
})

describe('EvidenceRefsPanel — 历史参考', () => {
  it('标题回退、相似度百分比与可信度标签', () => {
    const wrapper = mountPanel(
      refs({
        history_cases: [
          {
            id: 1,
            design_tag: '标签A',
            similarity: 0.86,
            trust_level: 'high',
            staleness_reason: '',
          },
          { id: 2, case_no: 'TC-2', similarity: 0.62, trust_level: 'medium', staleness_reason: '' },
          { id: 3, similarity: 0.3, trust_level: 'low', staleness_reason: '' },
        ],
      } as unknown as Partial<EvidenceRefs>)
    )

    const items = wrapper.findAll('.history-case-item')
    expect(items.map((i) => i.text().replace(/\s+/g, ' ').trim())).toEqual([
      '标签A 相似度 86% 高可信',
      'TC-2 相似度 62% 中可信',
      '用例 #3 相似度 30% 低可信',
    ])

    const types = items.map((i) => i.findAll('.el-tag').map((t) => t.attributes('data-type')))
    expect(types[0]).toEqual(['success', 'success'])
    expect(types[1]).toEqual(['warning', 'warning'])
    expect(types[2]).toEqual(['danger', 'danger'])
  })

  it('相似度缺失时不渲染相似度标签，未知可信度回退原文', () => {
    const wrapper = mountPanel(
      refs({
        history_cases: [{ id: 9, case_no: 'TC-9', trust_level: 'unknown' }],
      } as unknown as Partial<EvidenceRefs>)
    )

    const item = wrapper.find('.history-case-item')
    const tags = item.findAll('.el-tag')
    expect(tags).toHaveLength(1)
    expect(tags[0].text()).toBe('unknown')
    expect(tags[0].attributes('data-type')).toBe('warning')
  })

  it('存在过期原因时展示提示图标', () => {
    const wrapper = mountPanel(
      refs({
        history_cases: [
          { id: 1, case_no: 'TC-1', trust_level: 'high', staleness_reason: '需求已变更' },
        ],
      } as unknown as Partial<EvidenceRefs>)
    )

    const tooltip = wrapper.find('.staleness-icon')
    expect(tooltip.exists()).toBe(true)
    expect(wrapper.find('.el-tooltip').attributes('data-content')).toBe('需求已变更')
  })

  it('无过期原因时不展示提示图标', () => {
    const wrapper = mountPanel(
      refs({
        history_cases: [{ id: 1, case_no: 'TC-1', trust_level: 'high', staleness_reason: '' }],
      })
    )

    expect(wrapper.find('.staleness-icon').exists()).toBe(false)
  })
})

describe('EvidenceRefsPanel — 空态', () => {
  it('三类数据均为空时展示空态', () => {
    const wrapper = mountPanel(refs())

    expect(wrapper.findAll('.evidence-section')).toHaveLength(0)
    expect(wrapper.find('.el-empty').text()).toBe('暂无证据引用数据')
  })

  it('仅某一类有数据时只渲染该类区块', () => {
    const wrapper = mountPanel(
      refs({ ui_screens: [{ id: 1, screen_name: '登录页' }] } as unknown as Partial<EvidenceRefs>)
    )

    expect(sectionLabels(wrapper)).toEqual(['UI依据1条'])
    expect(wrapper.find('.el-empty').exists()).toBe(false)
  })
})
