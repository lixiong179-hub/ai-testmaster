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
      const token = localStorage.getItem('token')
      const response: Blob = await request.get(`/api/v1/file/preview-screen/${screen.id}`, {
        responseType: 'blob',
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      })
      const blob = response instanceof Blob ? response : new Blob([response], { type: 'image/jpeg' })
      const url = URL.createObjectURL(blob)
      imageCache.set(screen.id, url)
      return url
    } catch {
      return ''
    }
  }

  const cleanupImageCache = () => {
    imageCache.forEach(url => {
      if (url.startsWith('blob:')) {
        URL.revokeObjectURL(url)
      }
    })
    imageCache.clear()
  }

  return { getImageUrl, cleanupImageCache }
}
