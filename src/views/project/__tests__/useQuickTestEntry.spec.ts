import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage } from 'element-plus'
import { createComposableHost, deferred, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  launch: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/store/quickTest', () => ({
  useQuickTestStore: () => ({ launch: mocks.launch }),
}))

import { useQuickTestCard, useQuickTestEntry } from '../useQuickTestEntry'

type EntryCtx = ReturnType<typeof useQuickTestEntry>
type CardCtx = ReturnType<typeof useQuickTestCard>

const entryHost = createComposableHost<EntryCtx>(() => useQuickTestEntry())
const cardHost = createComposableHost<CardCtx>(() => useQuickTestCard())
let entry: EntryCtx
let card: CardCtx

async function mountEntry() {
  await entryHost.mount()
  entry = entryHost.ctx
}

async function mountCard() {
  await cardHost.mount()
  card = cardHost.ctx
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mocks.launch.mockResolvedValue(undefined)
  mocks.push.mockResolvedValue(undefined)
})

describe('useQuickTestEntry — URL 校验', () => {
  it('空值提示输入网址', async () => {
    await mountEntry()

    expect(entry.validateUrl('')).toBe('请输入网址')
    expect(entry.validateUrl('   ')).toBe('请输入网址')
    expect(entry.validateUrl(undefined as unknown as string)).toBe('请输入网址')
  })

  it('缺少 http/https 前缀时提示', async () => {
    await mountEntry()

    expect(entry.validateUrl('www.example.com')).toBe('网址必须以 http:// 或 https:// 开头')
    expect(entry.validateUrl('ftp://example.com')).toBe('网址必须以 http:// 或 https:// 开头')
    expect(entry.validateUrl('http:/example.com')).toBe('网址必须以 http:// 或 https:// 开头')
  })

  it('合法地址（含大小写与前后空格）通过校验', async () => {
    await mountEntry()

    expect(entry.validateUrl('http://example.com')).toBeNull()
    expect(entry.validateUrl('https://example.com/path?q=1')).toBeNull()
    expect(entry.validateUrl('  HTTPS://Example.com  ')).toBeNull()
  })
})

describe('useQuickTestEntry — 发起快速测试', () => {
  it('成功时跳转快速测试页并返回 true', async () => {
    await mountEntry()

    const ok = await entry.launch({ url: 'https://example.com' })

    expect(ok).toBe(true)
    expect(mocks.launch).toHaveBeenCalledWith({ url: 'https://example.com' })
    expect(mocks.push).toHaveBeenCalledWith('/home/quick-test')
    expect(entry.loading.value).toBe(false)
  })

  it('请求期间 loading 为 true', async () => {
    const pending = deferred<void>()
    mocks.launch.mockReturnValueOnce(pending.promise)
    await mountEntry()

    const task = entry.launch({ url: 'https://example.com' })
    expect(entry.loading.value).toBe(true)

    pending.resolve()
    await task

    expect(entry.loading.value).toBe(false)
  })

  it('失败时提示错误并返回 false，不跳转', async () => {
    mocks.launch.mockRejectedValue(new Error('启动被拒绝'))
    await mountEntry()

    const ok = await entry.launch({ url: 'https://example.com' })

    expect(ok).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('启动被拒绝')
    expect(mocks.push).not.toHaveBeenCalled()
    expect(entry.loading.value).toBe(false)
  })

  it('失败且非 Error 时使用兜底文案', async () => {
    mocks.launch.mockRejectedValue('boom')
    await mountEntry()

    await entry.launch({ url: 'https://example.com' })

    expect(ElMessage.error).toHaveBeenCalledWith('快速测试启动失败')
  })

  it('launchByUrl 会去除首尾空格', async () => {
    await mountEntry()

    await entry.launchByUrl('  https://example.com  ')

    expect(mocks.launch).toHaveBeenCalledWith({ url: 'https://example.com' })
  })

  it('launchByUrl 传入空值时按空串提交（校验由调用方负责）', async () => {
    await mountEntry()

    await entry.launchByUrl(null as unknown as string)

    expect(mocks.launch).toHaveBeenCalledWith({ url: '' })
  })
})

describe('useQuickTestCard — 表单提交', () => {
  it('URL 非法时写入内联错误且不发起请求', async () => {
    await mountCard()
    card.url.value = 'example.com'

    await card.submitCard()

    expect(card.error.value).toBe('网址必须以 http:// 或 https:// 开头')
    expect(mocks.launch).not.toHaveBeenCalled()
  })

  it('仅 URL 时请求体只包含 url', async () => {
    await mountCard()
    card.url.value = '  https://example.com  '

    await card.submitCard()

    expect(mocks.launch).toHaveBeenCalledWith({ url: 'https://example.com' })
    expect(card.error.value).toBe('')
  })

  it('描述与成对凭据一并提交', async () => {
    await mountCard()
    card.url.value = 'https://example.com'
    card.description.value = ' 冒烟验证 '
    card.username.value = ' admin '
    card.password.value = 'secret'

    await card.submitCard()

    expect(mocks.launch).toHaveBeenCalledWith({
      url: 'https://example.com',
      description: '冒烟验证',
      credentials: { username: 'admin', password: 'secret' },
    })
  })

  it('凭据缺一时不提交 credentials', async () => {
    await mountCard()
    card.url.value = 'https://example.com'
    card.username.value = 'admin'

    await card.submitCard()

    expect(mocks.launch).toHaveBeenCalledWith({ url: 'https://example.com' })
  })

  it('clearError 仅在存在错误时清空', async () => {
    await mountCard()

    card.clearError()
    expect(card.error.value).toBe('')

    card.error.value = '旧错误'
    card.clearError()
    expect(card.error.value).toBe('')
  })

  it('resetCard 清空表单与错误', async () => {
    await mountCard()
    card.url.value = 'https://example.com'
    card.description.value = '描述'
    card.username.value = 'admin'
    card.password.value = 'secret'
    card.error.value = '错误'

    card.resetCard()

    expect(card.url.value).toBe('')
    expect(card.description.value).toBe('')
    expect(card.username.value).toBe('')
    expect(card.password.value).toBe('')
    expect(card.error.value).toBe('')
  })
})
