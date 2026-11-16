import { describe, it, expect } from 'vitest'
import { formatDate, formatTime } from '../dateFormat'

const ISO = '2026-07-28T14:30:00'

describe('formatTime — 时间格式化', () => {
  it('空值返回默认占位符', () => {
    expect(formatTime(null)).toBe('—')
    expect(formatTime(undefined)).toBe('—')
    expect(formatTime('')).toBe('—')
  })

  it('支持自定义占位符', () => {
    expect(formatTime(null, '-')).toBe('-')
    expect(formatTime(undefined, 'N/A')).toBe('N/A')
  })

  it('合法 ISO 时间格式化为中文 24 小时制', () => {
    const result = formatTime(ISO)

    expect(result).toBe(new Date(ISO).toLocaleString('zh-CN', { hour12: false }))
    expect(result).toContain('2026')
    expect(result).not.toBe('—')
  })

  it('非法日期字符串原样返回', () => {
    expect(formatTime('not-a-date')).toBe('not-a-date')
    expect(formatTime('2026-13-45T00:00:00')).toBe('2026-13-45T00:00:00')
  })

  it('构造 Date 抛错时回退为原始值', () => {
    const weird = {
      toString() {
        throw new Error('boom')
      },
      valueOf() {
        throw new Error('boom')
      },
    }

    expect(formatTime(weird as never)).toBe(weird)
  })
})

describe('formatDate — 日期格式化', () => {
  it('空值返回默认占位符', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatDate(undefined)).toBe('—')
    expect(formatDate('')).toBe('—')
  })

  it('支持自定义占位符', () => {
    expect(formatDate(null, '')).toBe('')
  })

  it('合法 ISO 只输出日期部分', () => {
    const result = formatDate(ISO)

    expect(result).toBe(new Date(ISO).toLocaleDateString('zh-CN'))
    expect(result).toContain('2026')
    expect(result).not.toContain(':')
  })

  it('非法日期字符串原样返回', () => {
    expect(formatDate('bad')).toBe('bad')
  })

  it('构造 Date 抛错时回退为原始值', () => {
    const weird = {
      toString() {
        throw new Error('boom')
      },
      valueOf() {
        throw new Error('boom')
      },
    }

    expect(formatDate(weird as never)).toBe(weird)
  })
})
