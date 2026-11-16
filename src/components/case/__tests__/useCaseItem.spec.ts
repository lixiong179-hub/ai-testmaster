import { describe, it, expect } from 'vitest'
import type { TestCase } from '@/types/testCase'
import { useCaseItem } from '../useCaseItem'

function makeCase(overrides: Partial<TestCase> = {}): TestCase {
  return {
    id: 1,
    case_no: 'CASE-001',
    project_id: 1,
    module: '登录',
    title: '正常登录',
    priority: 1,
    case_type: 'manual',
    ...overrides,
  }
}

function setup(overrides: Partial<TestCase> = {}) {
  return useCaseItem({ caseItem: makeCase(overrides) })
}

describe('useCaseItem — 生命周期标签', () => {
  it('未设置、active、archived 时不展示标签', () => {
    expect(setup({ lifecycle_status: undefined }).lifecycleTag.value).toBeNull()
    expect(setup({ lifecycle_status: 'active' }).lifecycleTag.value).toBeNull()
    expect(setup({ lifecycle_status: 'archived' }).lifecycleTag.value).toBeNull()
  })

  it.each([
    ['draft', '草稿', 'info'],
    ['pending_review', '评审中', 'primary'],
    ['needs_modify', '待修改', 'warning'],
    ['locator_broken', '待重录', 'danger'],
    ['deprecated', '已弃用', 'info'],
  ])('状态 %s 映射为 %s / %s', (status, label, type) => {
    expect(setup({ lifecycle_status: status }).lifecycleTag.value).toEqual({ label, type })
  })

  it('未知状态不展示标签', () => {
    expect(setup({ lifecycle_status: 'unknown_status' }).lifecycleTag.value).toBeNull()
  })
})

describe('useCaseItem — 用例类型', () => {
  it.each([
    ['ui_automation', 'UI自动化', 'success'],
    ['UI', 'UI自动化', 'success'],
    ['manual', '手工测试', 'info'],
    ['功能', '手工测试', 'info'],
    ['功能测试', '手工测试', 'info'],
    ['functional', '手工测试', 'info'],
    ['api_automation', 'API自动化', 'primary'],
    ['API', 'API自动化', 'primary'],
    ['接口', 'API自动化', 'primary'],
    ['performance', '性能测试', 'warning'],
    ['security', '安全测试', 'danger'],
  ])('类型 %s 映射为 %s / %s', (caseType, label, tagType) => {
    const ctx = setup({ case_type: caseType })
    expect(ctx.caseTypeLabel.value).toBe(label)
    expect(ctx.caseTypeTagType.value).toBe(tagType)
  })

  it('未知类型原样展示标签且标签色回退 info', () => {
    const ctx = setup({ case_type: '自定义类型' })
    expect(ctx.caseTypeLabel.value).toBe('自定义类型')
    expect(ctx.caseTypeTagType.value).toBe('info')
  })

  it('类型为空时标签为空字符串', () => {
    const ctx = setup({ case_type: '' })
    expect(ctx.caseTypeLabel.value).toBe('')
    expect(ctx.caseTypeTagType.value).toBe('info')
  })
})

describe('useCaseItem — 优先级与状态文案', () => {
  it.each([
    [1, '高'],
    [2, '中'],
    [3, '低'],
  ])('优先级 %s 展示 %s', (priority, text) => {
    expect(setup({ priority }).priorityText(priority)).toBe(text)
  })

  it('优先级缺失或越界时回退「中」', () => {
    const ctx = setup()
    expect(ctx.priorityText(undefined)).toBe('中')
    expect(ctx.priorityText(9)).toBe('中')
  })

  it.each([
    [0, '生成中', 'status-processing'],
    [1, '生成成功', 'status-success'],
    [2, '生成失败', 'status-failed'],
  ])('生成状态 %s 展示 %s / %s', (status, text, cls) => {
    const ctx = setup()
    expect(ctx.statusText(status)).toBe(text)
    expect(ctx.statusClass(status)).toBe(cls)
  })

  it('生成状态缺失按「生成中」处理，越界展示「未知」且无样式类', () => {
    const ctx = setup()
    expect(ctx.statusText(undefined)).toBe('生成中')
    expect(ctx.statusClass(undefined)).toBe('status-processing')
    expect(ctx.statusText(9)).toBe('未知')
    expect(ctx.statusClass(9)).toBe('')
  })
})

describe('useCaseItem — 时间格式化', () => {
  it('时间缺失时返回空字符串', () => {
    expect(setup().formatTime(undefined)).toBe('')
    expect(setup().formatTime('')).toBe('')
  })

  it('合法时间按本地格式输出', () => {
    const iso = '2026-06-27T10:00:00'
    expect(setup().formatTime(iso)).toBe(new Date(iso).toLocaleString())
  })
})
