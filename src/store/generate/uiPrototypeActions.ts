import { uiPrototypeApi, type UIScreen } from '@/api/uiPrototype'
import request from '@/utils/request'
import { useFlowSortStore } from '@/store/flowSort'
import type { GenerateState } from './state'
import type { StoreActions } from './types'

export function createUiPrototypeActions(
  state: GenerateState,
  getActions: () => StoreActions
) {
  const loadUIPrototypeProjects = async () => {
    if (!state.formData.project_id) return
    try {
      const response = await uiPrototypeApi.getUIPrototypeProjectList(
        state.formData.project_id as number
      )
      if (response) {
        state.uiPrototypeProjects.value = Array.isArray(response)
          ? response
          : (response as Record<string, unknown>)?.data
            ? (response as Record<string, { items: import('@/api/uiPrototype').UIPrototypeProject[] }>).data.items || []
            : []
      }
    } catch (error) {
      console.error('获取 UI 原型项目列表失败:', error)
    }
  }

  const cleanupScreenImages = () => {
    Object.values(state.screenImageUrls.value).forEach((url) => {
      if (url.startsWith('blob:')) {
        URL.revokeObjectURL(url)
      }
    })
    state.screenImageUrls.value = {}
  }

  const loadScreenImages = async () => {
    if (state.isLoadingScreenImages.value) return
    state.isLoadingScreenImages.value = true
    try {
      const screensToLoad = state.uiScreens.value.filter(
        (screen) => screen.id && !state.screenImageUrls.value[screen.id]
      )
      const BATCH_SIZE = 5
      for (let i = 0; i < screensToLoad.length; i += BATCH_SIZE) {
        const batch = screensToLoad.slice(i, i + BATCH_SIZE)
        await Promise.allSettled(
          batch.map(async (screen) => {
            try {
              const response = await request.get(`/api/v1/file/preview-screen/${screen.id}`, {
                responseType: 'blob',
              })
              const blob =
                response.data instanceof Blob
                  ? response.data
                  : new Blob([response.data], { type: 'image/jpeg' })
              if (blob.size > 0) {
                const oldUrl = state.screenImageUrls.value[screen.id]
                if (oldUrl?.startsWith('blob:')) {
                  URL.revokeObjectURL(oldUrl)
                }
                state.screenImageUrls.value[screen.id] = URL.createObjectURL(blob)
              }
            } catch (e) {
              console.warn(`加载屏幕图片失败: ${screen.id}`, e)
            }
          })
        )
      }
    } finally {
      state.isLoadingScreenImages.value = false
    }
  }

  const loadUIScreens = async (uiPrototypeProjectId: number) => {
    if (!state.formData.project_id) return
    try {
      const response = await uiPrototypeApi.getUIScreenList(
        state.formData.project_id as number,
        uiPrototypeProjectId
      )
      if (response?.data?.items) {
        state.uiScreens.value = response.data.items.sort(
          (a: UIScreen, b: UIScreen) => (a.screen_order || 0) - (b.screen_order || 0)
        )
        cleanupScreenImages()
        await loadScreenImages()
      }
    } catch (error) {
      console.error('获取 UI 屏幕列表失败:', error)
    }
  }

  const handleUIPrototypeProjectChange = async (projectId: number | string) => {
    state.showParseWarning.value = true
    state.lastContext.value = {}
    state.selectedUiPrototypeProjectId.value = projectId as number | ''
    const flowSortStore = useFlowSortStore()
    if (projectId) {
      if (state.formData.project_id) {
        flowSortStore.setProjectId(state.formData.project_id as number)
      }
      await getActions().loadUIScreens(projectId as number)
      if (state.formData.project_id) {
        await flowSortStore.loadFromBackend()
      }
      if (state.uiScreens.value.length > 0) {
        state.formData.ui_screen_ids = state.uiScreens.value.map((s) => s.id)
      } else {
        state.formData.ui_screen_ids = []
      }
    } else {
      state.uiScreens.value = []
      state.formData.ui_screen_ids = []
      flowSortStore.reset()
    }
  }

  return {
    loadUIPrototypeProjects,
    loadUIScreens,
    loadScreenImages,
    handleUIPrototypeProjectChange,
    cleanupScreenImages,
  }
}
