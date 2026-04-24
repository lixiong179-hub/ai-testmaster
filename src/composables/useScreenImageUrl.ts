import type { UIScreen } from '@/api/uiPrototype'
import request from '@/utils/request'

const imageCache = new Map<number, string>()

export function useScreenImageUrl() {
  const getImageUrl = async (screen: UIScreen): Promise<string> => {
    if (!screen.id) return ''
    if (imageCache.has(screen.id)) {
      return imageCache.get(screen.id) ?? ''
    }
    try {
      const response = await request.get(`/api/v1/file/preview-screen/${screen.id}`, {
        responseType: 'blob',
      })
      // 响应拦截器已经返回了原始响应，我们需要从 response.data 中获取 blob
      const blob =
        response.data instanceof Blob
          ? response.data
          : new Blob([response.data], { type: 'image/jpeg' })
      const url = URL.createObjectURL(blob)
      imageCache.set(screen.id, url)
      return url
    } catch {
      return ''
    }
  }

  const cleanupImageCache = () => {
    imageCache.forEach((url) => {
      if (url.startsWith('blob:')) {
        URL.revokeObjectURL(url)
      }
    })
    imageCache.clear()
  }

  return { getImageUrl, cleanupImageCache }
}
