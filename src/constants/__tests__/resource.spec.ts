import { describe, it, expect } from 'vitest'
import {
  LIFECYCLE_STATUS_OPTIONS,
  LIFECYCLE_STATUS_TAG_MAP,
  getLifecycleStatusLabel,
  getLifecycleStatusTagType,
} from '../resource'

describe('lifecycle status constants', () => {
  it('应覆盖后端 7 个生命周期状态', () => {
    const values = LIFECYCLE_STATUS_OPTIONS.map((o) => o.value)
    expect(values).toEqual([
      'draft',
      'active',
      'pending_review',
      'needs_modify',
      'locator_broken',
      'deprecated',
      'archived',
    ])
  })

  it('不应包含已废弃的 reviewed 值', () => {
    const values = LIFECYCLE_STATUS_OPTIONS.map((o) => o.value)
    expect(values).not.toContain('reviewed')
  })

  it('每个状态都应有对应的 Tag 颜色映射', () => {
    for (const opt of LIFECYCLE_STATUS_OPTIONS) {
      expect(LIFECYCLE_STATUS_TAG_MAP[opt.value]).toBeDefined()
    }
  })

  describe('getLifecycleStatusLabel', () => {
    it('已知状态返回中文文案', () => {
      expect(getLifecycleStatusLabel('draft')).toBe('草稿')
      expect(getLifecycleStatusLabel('pending_review')).toBe('待审核')
      expect(getLifecycleStatusLabel('locator_broken')).toBe('定位失效')
    })

    it('空值返回占位符', () => {
      expect(getLifecycleStatusLabel(undefined)).toBe('-')
      expect(getLifecycleStatusLabel(null)).toBe('-')
      expect(getLifecycleStatusLabel('')).toBe('-')
    })

    it('未知状态回退为原始值', () => {
      expect(getLifecycleStatusLabel('unknown_state')).toBe('unknown_state')
    })
  })

  describe('getLifecycleStatusTagType', () => {
    it('已知状态返回对应 Tag 类型', () => {
      expect(getLifecycleStatusTagType('active')).toBe('success')
      expect(getLifecycleStatusTagType('pending_review')).toBe('warning')
      expect(getLifecycleStatusTagType('needs_modify')).toBe('danger')
    })

    it('空值或未知状态返回 info', () => {
      expect(getLifecycleStatusTagType(undefined)).toBe('info')
      expect(getLifecycleStatusTagType(null)).toBe('info')
      expect(getLifecycleStatusTagType('unknown')).toBe('info')
    })
  })
})
