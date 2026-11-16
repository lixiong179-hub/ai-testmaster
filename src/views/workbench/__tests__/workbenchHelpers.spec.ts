import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  REVIEW_ITERATION_SCAN_LIMIT,
  TREND_DAYS,
  buildDateRange,
  computePassRate,
  extractTaskItems,
  extractTotal,
} from '../workbenchHelpers'

function task(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    task_name: '任务A',
    status: 2,
    success_count: 8,
    fail_count: 2,
    total_count: 10,
    create_time: '2026-11-13T10:00:00',
    ...overrides,
  }
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-13T12:00:00Z'))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('workbenchHelpers — 常量', () => {
  it('趋势天数与扫描上限', () => {
    expect(TREND_DAYS).toBe(7)
    expect(REVIEW_ITERATION_SCAN_LIMIT).toBe(10)
  })
})

describe('buildDateRange', () => {
  it('构造最近 7 天的闭区间', () => {
    expect(buildDateRange(7)).toEqual({
      start_date: '2026-11-07',
      end_date: '2026-11-13',
    })
  })

  it('只取 1 天时首尾相同', () => {
    expect(buildDateRange(1)).toEqual({
      start_date: '2026-11-13',
      end_date: '2026-11-13',
    })
  })

  it('跨月边界正确回退', () => {
    vi.setSystemTime(new Date('2026-12-02T12:00:00Z'))

    expect(buildDateRange(5)).toEqual({
      start_date: '2026-11-28',
      end_date: '2026-12-02',
    })
  })
})

describe('extractTaskItems', () => {
  it('兼容 data.items 形态', () => {
    expect(extractTaskItems({ data: { items: [task()] } })).toHaveLength(1)
  })

  it('兼容平铺 items 形态', () => {
    expect(extractTaskItems({ items: [task(), task({ id: 2 })] })).toHaveLength(2)
  })

  it('data.items 优先于平铺 items', () => {
    const result = extractTaskItems({ data: { items: [task()] }, items: [] })

    expect(result).toHaveLength(1)
  })

  it('异常响应返回空数组', () => {
    expect(extractTaskItems(undefined)).toEqual([])
    expect(extractTaskItems({})).toEqual([])
    expect(extractTaskItems({ data: {} })).toEqual([])
  })
})

describe('extractTotal', () => {
  it('兼容 data.total 与平铺 total', () => {
    expect(extractTotal({ data: { total: 12 } })).toBe(12)
    expect(extractTotal({ total: 7 })).toBe(7)
  })

  it('data.total 为 0 时不回退到平铺值', () => {
    expect(extractTotal({ data: { total: 0 }, total: 99 })).toBe(0)
  })

  it('缺失时返回 0', () => {
    expect(extractTotal(undefined)).toBe(0)
    expect(extractTotal({})).toBe(0)
  })
})

describe('computePassRate', () => {
  it('按成功数占总数的比例四舍五入', () => {
    expect(computePassRate({ items: [task()] })).toBe(80)
  })

  it('多任务累加后计算', () => {
    const response = {
      data: {
        items: [
          task({ success_count: 1, total_count: 3 }),
          task({ success_count: 2, total_count: 3 }),
        ],
      },
    }

    expect(computePassRate(response)).toBe(50)
  })

  it('总数不足时取整', () => {
    expect(computePassRate({ items: [task({ success_count: 1, total_count: 3 })] })).toBe(33)
  })

  it('缺失字段按 0 处理', () => {
    const response = { items: [{ success_count: undefined, total_count: undefined }] }

    expect(computePassRate(response)).toBe(0)
  })

  it('空列表返回 0', () => {
    expect(computePassRate({ items: [] })).toBe(0)
    expect(computePassRate(undefined)).toBe(0)
  })

  it('全部失败返回 0', () => {
    expect(computePassRate({ items: [task({ success_count: 0, total_count: 10 })] })).toBe(0)
  })
})
