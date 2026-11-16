import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import ContextHealthPanel from '../ContextHealthPanel.vue'

const ElProgressStub = defineComponent({
  name: 'ElProgress',
  props: {
    percentage: { type: Number, default: 0 },
    color: { type: String, default: '' },
    width: { type: Number, default: 0 },
    strokeWidth: { type: Number, default: 0 },
  },
  template:
    '<div class="el-progress" :data-percentage="percentage" :data-color="color"><slot /></div>',
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

const ElAlertStub = defineComponent({
  name: 'ElAlert',
  props: { type: { type: String, default: 'info' }, title: { type: String, default: '' } },
  template:
    '<div class="el-alert" :data-type="type"><span class="alert-title"><slot name="title">{{ title }}</slot></span><slot /></div>',
})

const stubs = {
  ElProgress: ElProgressStub,
  ElTag: ElTagStub,
  ElIcon: ElIconStub,
  ElAlert: ElAlertStub,
}

type Warning = { code: string; message: string; detail?: Record<string, unknown> }

function setup(
  options: {
    score?: number
    stats?: Record<string, unknown> | null
    warnings?: Warning[]
    evidenceRefs?: Record<string, unknown> | null
  } = {}
) {
  const contextStats =
    options.stats === undefined
      ? {
          completeness_score: options.score ?? 90,
          strategy: 'full_context',
          requirement_strategy: 'keyword_trim',
          ui_strategy: 'screen_match',
          missing_core_context: [],
          low_confidence_reasons: [],
        }
      : options.stats

  const wrapper = mount(ContextHealthPanel, {
    props: {
      contextStats: contextStats as never,
      warnings: (options.warnings ?? []) as never,
      evidenceRefs: (options.evidenceRefs ?? null) as never,
    },
    global: { stubs },
  })
  return { wrapper }
}

describe('ContextHealthPanel — 评分', () => {
  it.each([
    [90, '上下文充分，可正常生成', '#67c23a'],
    [80, '上下文充分，可正常生成', '#67c23a'],
    [60, '上下文部分缺失，生成质量可能受影响', '#e6a23c'],
    [50, '上下文部分缺失，生成质量可能受影响', '#e6a23c'],
    [30, '上下文严重不足，建议补齐后再生成', '#f56c6c'],
    [0, '上下文严重不足，建议补齐后再生成', '#f56c6c'],
  ])('评分 %s 展示对应文案与颜色', (score, desc, color) => {
    const { wrapper } = setup({ score })

    expect(wrapper.find('.score-desc').text()).toBe(desc)
    expect(wrapper.find('.score-value').text()).toBe(String(score))
    expect(wrapper.find('.score-value').attributes('style')).toContain(`color: ${color}`)
    expect(wrapper.find('.el-progress').attributes('data-percentage')).toBe(String(score))
    expect(wrapper.find('.el-progress').attributes('data-color')).toBe(color)
  })

  it('缺少统计数据时评分为 0', () => {
    const { wrapper } = setup({ stats: null })

    expect(wrapper.find('.score-value').text()).toBe('0')
    expect(wrapper.find('.score-meta').exists()).toBe(false)
  })
})

describe('ContextHealthPanel — 策略标签', () => {
  it('展示策略、需求策略与 UI 策略', () => {
    const { wrapper } = setup()

    expect(wrapper.findAll('.score-meta .el-tag').map((t) => t.text())).toEqual([
      '策略: full_context',
      '需求策略: keyword_trim',
      'UI策略: screen_match',
    ])
  })

  it('仅展示已提供的策略字段', () => {
    const { wrapper } = setup({
      stats: { completeness_score: 70, strategy: 'lite' },
    })

    expect(wrapper.findAll('.score-meta .el-tag').map((t) => t.text())).toEqual(['策略: lite'])
  })
})

describe('ContextHealthPanel — 缺失与低置信度', () => {
  it('渲染缺失核心上下文与低置信度原因', () => {
    const { wrapper } = setup({
      stats: {
        completeness_score: 55,
        strategy: 'lite',
        missing_core_context: ['需求文档', 'UI 原型'],
        low_confidence_reasons: ['仅命中关键词'],
      },
    })

    const section = wrapper.find('.missing-context-section')
    expect(section.exists()).toBe(true)
    const groups = wrapper.findAll('.missing-tags')
    expect(groups[0].find('.tag-group-label').text()).toBe('缺失核心上下文:')
    expect(groups[0].findAll('.el-tag').map((t) => t.text())).toEqual(['需求文档', 'UI 原型'])
    expect(groups[0].findAll('.el-tag')[0].attributes('data-type')).toBe('danger')
    expect(groups[1].find('.tag-group-label').text()).toBe('低置信度原因:')
    expect(groups[1].findAll('.el-tag').map((t) => t.text())).toEqual(['仅命中关键词'])
    expect(groups[1].findAll('.el-tag')[0].attributes('data-type')).toBe('warning')
  })

  it('无缺失时整块不渲染', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.missing-context-section').exists()).toBe(false)
  })
})

describe('ContextHealthPanel — 后端警告分组', () => {
  it('按 code 分入阻断/风险/提示三组并计数', () => {
    const { wrapper } = setup({
      score: 70,
      warnings: [
        { code: 'REQUIREMENT_NOT_FOUND', message: '需求不存在' },
        { code: 'UI_NO_MATCH', message: 'UI 未匹配' },
        { code: 'HISTORY_LOW_TRUST_FILTERED', message: '历史用例过滤' },
        { code: 'SOMETHING_ELSE', message: '其它提示' },
      ],
    })

    const headers = wrapper.findAll('.warning-group-header span').map((n) => n.text())
    expect(headers).toEqual(['阻断类 (1)', '风险类 (2)', '提示类 (1)'])

    const groups = wrapper.findAll('.warning-group')
    expect(groups[0].findAll('.el-alert').map((a) => a.attributes('data-type'))).toEqual(['error'])
    expect(groups[1].findAll('.el-alert').map((a) => a.attributes('data-type'))).toEqual([
      'warning',
      'warning',
    ])
    expect(groups[2].findAll('.el-alert').map((a) => a.attributes('data-type'))).toEqual(['info'])
  })

  it('CONTEXT_COMPLETENESS_LOW 在低分时归为阻断类', () => {
    const { wrapper } = setup({
      score: 40,
      warnings: [{ code: 'CONTEXT_COMPLETENESS_LOW', message: '上下文不足' }],
    })

    expect(wrapper.find('.warning-group-header span').text()).toBe('阻断类 (1)')
  })

  it('CONTEXT_COMPLETENESS_LOW 在及格分时归为风险类', () => {
    const { wrapper } = setup({
      score: 60,
      warnings: [{ code: 'CONTEXT_COMPLETENESS_LOW', message: '上下文不足' }],
    })

    expect(wrapper.find('.warning-group-header span').text()).toBe('风险类 (1)')
  })

  it('警告标题与明细字段一并展示', () => {
    const { wrapper } = setup({
      score: 70,
      warnings: [
        {
          code: 'UI_REQUIRED_ELEMENT_MISSING',
          message: '缺少必需元素',
          detail: { element: '登录按钮', screen: '首页' },
        },
      ],
    })

    const alert = wrapper.find('.el-alert')
    expect(alert.find('.alert-title').text()).toBe('缺少必需元素')
    expect(alert.findAll('.warning-detail span').map((s) => s.text().trim())).toEqual([
      'element: 登录按钮',
      'screen: 首页',
    ])
  })

  it('无警告时不渲染警告区', () => {
    const { wrapper } = setup({ warnings: [] })

    expect(wrapper.find('.warnings-section').exists()).toBe(false)
  })
})
