import { describe, it, expect, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({
  getPreviewScreen: vi.fn(),
}))

vi.mock('@/api/file', () => {
  const api = { getPreviewScreen: mocks.getPreviewScreen }
  return { fileApi: api, default: api }
})

import { useScreenImageUrl } from '../useScreenImageUrl'

const createObjectURL = vi.mocked(URL.createObjectURL)
const revokeObjectURL = vi.mocked(URL.revokeObjectURL)

beforeEach(() => {
  useScreenImageUrl().cleanupImageCache()
  vi.clearAllMocks()
  createObjectURL.mockReturnValue('blob:screen')
  mocks.getPreviewScreen.mockResolvedValue({ data: new Blob(['x'], { type: 'image/png' }) })
})

describe('useScreenImageUrl — 获取图片地址', () => {
  it('缺少屏幕 ID 时返回空串', async () => {
    const { getImageUrl } = useScreenImageUrl()

    await expect(getImageUrl({ id: 0 } as never)).resolves.toBe('')
    expect(mocks.getPreviewScreen).not.toHaveBeenCalled()
  })

  it('Blob 响应直接生成对象地址', async () => {
    const { getImageUrl } = useScreenImageUrl()

    const url = await getImageUrl({ id: 1 } as never)

    expect(mocks.getPreviewScreen).toHaveBeenCalledWith(1)
    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(url).toBe('blob:screen')
  })

  it('非 Blob 响应包装为图片 Blob', async () => {
    mocks.getPreviewScreen.mockResolvedValue({ data: 'raw' })
    const { getImageUrl } = useScreenImageUrl()

    await getImageUrl({ id: 2 } as never)

    const arg = (createObjectURL.mock.calls as unknown as [[Blob]])[0][0]
    expect(arg).toBeInstanceOf(Blob)
    expect((arg as Blob).type).toBe('image/jpeg')
  })

  it('同一屏幕命中缓存不重复请求', async () => {
    const { getImageUrl } = useScreenImageUrl()

    const first = await getImageUrl({ id: 3 } as never)
    const second = await getImageUrl({ id: 3 } as never)

    expect(mocks.getPreviewScreen).toHaveBeenCalledTimes(1)
    expect(second).toBe(first)
  })

  it('请求失败返回空串', async () => {
    mocks.getPreviewScreen.mockRejectedValue(new Error('boom'))
    const { getImageUrl } = useScreenImageUrl()

    await expect(getImageUrl({ id: 4 } as never)).resolves.toBe('')
    expect(createObjectURL).not.toHaveBeenCalled()
  })
})

describe('useScreenImageUrl — 缓存清理', () => {
  it('清理时释放 blob 地址并清空缓存', async () => {
    const { getImageUrl, cleanupImageCache } = useScreenImageUrl()
    await getImageUrl({ id: 5 } as never)

    cleanupImageCache()

    expect(revokeObjectURL).toHaveBeenCalledWith('blob:screen')

    await getImageUrl({ id: 5 } as never)
    expect(mocks.getPreviewScreen).toHaveBeenCalledTimes(2)
  })

  it('非 blob 地址不调用释放', async () => {
    createObjectURL.mockReturnValueOnce('data:image/png;base64,xx')
    const { getImageUrl, cleanupImageCache } = useScreenImageUrl()
    await getImageUrl({ id: 6 } as never)

    cleanupImageCache()

    expect(revokeObjectURL).not.toHaveBeenCalled()
  })

  it('清理可重复执行', () => {
    const { cleanupImageCache } = useScreenImageUrl()

    cleanupImageCache()
    cleanupImageCache()

    expect(revokeObjectURL).not.toHaveBeenCalled()
  })
})
