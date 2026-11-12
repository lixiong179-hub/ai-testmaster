import { describe, it, expect } from 'vitest'
import {
  getUIScreenStatusType,
  getUIScreenStatusText,
  getUIScreenStatusMeta,
} from '../uiScreenStatus'
import { isUIScreenListResponse, getRouteQueryParam } from '../uiPrototypeHelpers'

describe('uiScreenStatus — 标签类型', () => {
  it('四种状态映射到对应 Tag 类型', () => {
    expect(getUIScreenStatusType('pending')).toBe('info')
    expect(getUIScreenStatusType('running')).toBe('warning')
    expect(getUIScreenStatusType('completed')).toBe('success')
    expect(getUIScreenStatusType('failed')).toBe('danger')
  })

  it('未知状态与空值回退 info', () => {
    expect(getUIScreenStatusType('weird')).toBe('info')
    expect(getUIScreenStatusType(null)).toBe('info')
    expect(getUIScreenStatusType(undefined)).toBe('info')
    expect(getUIScreenStatusType({ parse_status: null })).toBe('info')
  })

  it('支持对象入参', () => {
    expect(getUIScreenStatusType({ parse_status: 'failed' })).toBe('danger')
  })
})

describe('uiScreenStatus — 文案', () => {
  it('内置状态文案', () => {
    expect(getUIScreenStatusText('pending')).toBe('待解析')
    expect(getUIScreenStatusText('running')).toBe('解析中')
    expect(getUIScreenStatusText('completed')).toBe('已解析')
    expect(getUIScreenStatusText('failed')).toBe('解析失败')
  })

  it('parse_status_text 优先于内置文案', () => {
    expect(getUIScreenStatusText({ parse_status: 'failed', parse_status_text: 'OCR 超时' })).toBe(
      'OCR 超时'
    )
  })

  it('未知状态原样回显，缺省视为 pending', () => {
    expect(getUIScreenStatusText('unknown_state')).toBe('unknown_state')
    expect(getUIScreenStatusText({})).toBe('待解析')
  })
})

describe('uiScreenStatus — 派生元信息', () => {
  it('completed 为唯一可查看详情的状态', () => {
    const meta = getUIScreenStatusMeta('completed')

    expect(meta).toMatchObject({
      status: 'completed',
      type: 'success',
      text: '已解析',
      isCompleted: true,
      canShowDetails: true,
      isPending: false,
      isRunning: false,
      isFailed: false,
    })
  })

  it('running 不可查看详情', () => {
    const meta = getUIScreenStatusMeta({ parse_status: 'running' })

    expect(meta.isRunning).toBe(true)
    expect(meta.canShowDetails).toBe(false)
  })

  it('空值视为 pending', () => {
    const meta = getUIScreenStatusMeta(null)

    expect(meta.status).toBe('pending')
    expect(meta.isPending).toBe(true)
  })
})

describe('uiPrototypeHelpers — 响应体判定', () => {
  it('直接带 items 数组视为合法响应', () => {
    expect(isUIScreenListResponse({ items: [] })).toBe(true)
  })

  it('包一层 data 也视为合法响应', () => {
    expect(isUIScreenListResponse({ data: { items: [{ id: 1 }] } })).toBe(true)
  })

  it('非对象、items 非数组、data 无 items 均不合法', () => {
    expect(isUIScreenListResponse(null)).toBe(false)
    expect(isUIScreenListResponse([])).toBe(false)
    expect(isUIScreenListResponse('items')).toBe(false)
    expect(isUIScreenListResponse({ items: 'nope' })).toBe(false)
    expect(isUIScreenListResponse({ data: {} })).toBe(false)
    expect(isUIScreenListResponse({ data: null })).toBe(false)
  })
})

describe('uiPrototypeHelpers — 路由参数', () => {
  it('数组取首项，空数组回退空串', () => {
    expect(getRouteQueryParam(['a', 'b'])).toBe('a')
    expect(getRouteQueryParam([])).toBe('')
    // 只看首项，首项为空则回退空串（不回退到后续项）
    expect(getRouteQueryParam([null, 'b'])).toBe('')
  })

  it('字符串原样返回，null/undefined 回退空串', () => {
    expect(getRouteQueryParam('abc')).toBe('abc')
    expect(getRouteQueryParam(null)).toBe('')
    expect(getRouteQueryParam(undefined)).toBe('')
  })
})
