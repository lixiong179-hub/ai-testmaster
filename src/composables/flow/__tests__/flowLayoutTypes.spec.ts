import { describe, it, expect } from 'vitest'
import {
  DEFAULT_LAYOUT_OPTIONS,
  COMPACT_OPTIONS,
  SWIMLANE_OPTIONS,
  LAYOUT_MODE_LABELS,
  type LayoutOptions,
  type LayoutMode,
} from '../flowLayoutTypes'

const LAYOUT_KEYS: Array<keyof LayoutOptions> = [
  'mainGapX',
  'branchGapY',
  'mainStartY',
  'branchStartY',
  'typeGapY',
  'nestedIndentX',
  'childrenHorizontalGap',
  'maxChildrenPerColumn',
  'maxMainPerRow',
]

const LAYOUT_MODES: LayoutMode[] = [
  'standard',
  'compact',
  'type-layered',
  'focused-path',
  'swimlane',
]

describe('flowLayoutTypes — 默认布局参数', () => {
  it('默认参数覆盖全部字段且非负', () => {
    expect(Object.keys(DEFAULT_LAYOUT_OPTIONS).sort()).toEqual([...LAYOUT_KEYS].sort())
    LAYOUT_KEYS.forEach((key) => {
      const value = DEFAULT_LAYOUT_OPTIONS[key]
      expect(typeof value).toBe('number')
      expect(Number.isFinite(value)).toBe(true)
      expect(value).toBeGreaterThanOrEqual(0)
    })
  })

  it('除起始偏移外其余参数均为正数', () => {
    LAYOUT_KEYS.filter((key) => key !== 'mainStartY').forEach((key) => {
      expect(DEFAULT_LAYOUT_OPTIONS[key]).toBeGreaterThan(0)
    })
  })

  it('默认参数与既有画布基线一致', () => {
    expect(DEFAULT_LAYOUT_OPTIONS).toMatchObject({
      mainGapX: 280,
      branchGapY: 200,
      mainStartY: 0,
      branchStartY: 200,
      typeGapY: 60,
      nestedIndentX: 60,
      childrenHorizontalGap: 280,
      maxChildrenPerColumn: 4,
      maxMainPerRow: 8,
    })
  })
})

describe('flowLayoutTypes — 紧凑与泳道预设', () => {
  it('紧凑预设只使用合法字段', () => {
    Object.keys(COMPACT_OPTIONS).forEach((key) => {
      expect(LAYOUT_KEYS).toContain(key as keyof LayoutOptions)
    })
    expect(Object.keys(COMPACT_OPTIONS).length).toBeGreaterThan(0)
  })

  it('紧凑预设的间距与列容量均小于默认值', () => {
    expect(COMPACT_OPTIONS.mainGapX!).toBeLessThan(DEFAULT_LAYOUT_OPTIONS.mainGapX)
    expect(COMPACT_OPTIONS.branchGapY!).toBeLessThan(DEFAULT_LAYOUT_OPTIONS.branchGapY)
    expect(COMPACT_OPTIONS.branchStartY!).toBeLessThan(DEFAULT_LAYOUT_OPTIONS.branchStartY)
    expect(COMPACT_OPTIONS.typeGapY!).toBeLessThan(DEFAULT_LAYOUT_OPTIONS.typeGapY)
    expect(COMPACT_OPTIONS.maxChildrenPerColumn!).toBeGreaterThan(
      DEFAULT_LAYOUT_OPTIONS.maxChildrenPerColumn
    )
  })

  it('泳道预设只使用合法字段且单行列数更保守', () => {
    Object.keys(SWIMLANE_OPTIONS).forEach((key) => {
      expect(LAYOUT_KEYS).toContain(key as keyof LayoutOptions)
    })
    expect(SWIMLANE_OPTIONS.maxMainPerRow!).toBeLessThan(DEFAULT_LAYOUT_OPTIONS.maxMainPerRow)
    expect(SWIMLANE_OPTIONS.maxChildrenPerColumn!).toBe(DEFAULT_LAYOUT_OPTIONS.maxChildrenPerColumn)
  })

  it('三个预设互不共享引用', () => {
    expect(COMPACT_OPTIONS).not.toBe(DEFAULT_LAYOUT_OPTIONS)
    expect(SWIMLANE_OPTIONS).not.toBe(DEFAULT_LAYOUT_OPTIONS)
    expect(COMPACT_OPTIONS.maxMainPerRow).toBeUndefined()
  })
})

describe('flowLayoutTypes — 布局模式标签', () => {
  it('标签表覆盖全部布局模式', () => {
    expect(Object.keys(LAYOUT_MODE_LABELS).sort()).toEqual([...LAYOUT_MODES].sort())
  })

  it('每个模式都有非空中文文案', () => {
    LAYOUT_MODES.forEach((mode) => {
      expect(LAYOUT_MODE_LABELS[mode].trim().length).toBeGreaterThan(0)
    })
    expect(LAYOUT_MODE_LABELS['focused-path']).toBe('仅整理当前路径')
    expect(LAYOUT_MODE_LABELS.swimlane).toBe('泳道布局')
  })
})
