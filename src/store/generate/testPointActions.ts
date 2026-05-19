import { testPointApi, type TestPoint } from '@/api/testPoint'
import { TEST_POINT_CACHE_MAX } from './types'
import type { GenerateState } from './state'

export function createTestPointActions(state: GenerateState) {
  const loadTestPoints = async (
    page: number = 1,
    append: boolean = false,
    refreshKey: boolean = true
  ) => {
    if (!state.formData.project_id) return
    try {
      const apiData = await testPointApi.getList(state.formData.project_id as number, {
        page,
        page_size: state.testPointPageSize.value,
      })
      if (apiData) {
        const newItems = apiData.items || []
        if (append && page > 1) {
          state.testPoints.value = [...state.testPoints.value, ...newItems]
        } else {
          state.testPoints.value = newItems
        }
        newItems.forEach((item: TestPoint) => {
          state.testPointCache.set(item.id, item)
          if (!state.testPointAllIds.value.includes(item.id)) {
            state.testPointAllIds.value.push(item.id)
          }
        })
        if (state.testPointCache.size > TEST_POINT_CACHE_MAX) {
          const overflow = state.testPointCache.size - TEST_POINT_CACHE_MAX
          let count = 0
          for (const key of state.testPointCache.keys()) {
            if (count >= overflow) break
            state.testPointCache.delete(key)
            count++
          }
        }
        state.testPointTotal.value = apiData.total || 0
        state.testPointPage.value = page
        if (refreshKey) {
          state.testPointSelectKey.value++
        }
        if (
          state.testPointAllIds.value.length < state.testPointTotal.value &&
          page === 1 &&
          state.testPointTotal.value <= 200
        ) {
          const allApiData = await testPointApi.getList(state.formData.project_id as number, {
            page: 1,
            page_size: Math.min(state.testPointTotal.value, 200),
          })
          if (allApiData?.items) {
            state.testPointAllIds.value = allApiData.items.map((item: TestPoint) => item.id)
          }
        }
      }
    } catch (error) {
      console.error('获取测试点列表失败:', error)
    }
  }

  const handleSourceFileChange = () => {
    if (!state.formData.project_id) return
    state.testPointPage.value = 1
    state.testPointTotal.value = 0
    state.testPointAllIds.value = []
    state.formData.test_point_ids = []
    state.testPoints.value = []
    state.testPointCache.clear()
    state.testPointSelectKey.value++
  }

  const selectAllTestPoints = () => {
    if (state.testPointAllIds.value.length > 0) {
      state.formData.test_point_ids = [...state.testPointAllIds.value]
    }
  }

  const deselectAllTestPoints = () => {
    state.formData.test_point_ids = []
  }

  const addTestPoint = (id: number) => {
    if (!state.formData.test_point_ids.includes(id)) {
      state.formData.test_point_ids.push(id)
    }
  }

  const removeTestPoint = (id: number) => {
    const index = state.formData.test_point_ids.indexOf(id)
    if (index !== -1) {
      state.formData.test_point_ids.splice(index, 1)
    }
  }

  const getTestPointLabel = (id: number): string => {
    let point = state.testPointCache.get(id)
    if (!point) {
      point = state.testPoints.value.find((p) => p.id === id)
    }
    if (point) {
      return `${point.module} - ${point.point}`
    }
    return `测试点 #${id}`
  }

  const selectCurrentPageAll = () => {
    const visibleIds = state.testPoints.value.map((p) => p.id)
    const currentSet = new Set(state.formData.test_point_ids)
    visibleIds.forEach((id) => {
      if (!currentSet.has(id)) {
        state.formData.test_point_ids.push(id)
      }
    })
  }

  const goToTestPointPage = async (page: number) => {
    if (state.isLoadingMore.value) return
    state.isLoadingMore.value = true
    try {
      await loadTestPoints(page, false, false)
    } finally {
      state.isLoadingMore.value = false
    }
  }

  return {
    loadTestPoints,
    handleSourceFileChange,
    selectAllTestPoints,
    deselectAllTestPoints,
    addTestPoint,
    removeTestPoint,
    getTestPointLabel,
    selectCurrentPageAll,
    goToTestPointPage,
  }
}
