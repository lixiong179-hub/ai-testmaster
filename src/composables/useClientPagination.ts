/**
 * 客户端分页 composable
 *
 * 为一次性加载全量数据的表格提供客户端分页能力，
 * 避免大数据量（100+ 行）一次性渲染导致的性能问题。
 *
 * 与 usePagination 的区别：
 * - usePagination 用于服务端分页（每次翻页发请求）
 * - useClientPagination 用于已加载全量数据的客户端分页（纯前端切片）
 */
import { ref, computed, type Ref } from 'vue'

export function useClientPagination<T>(source: Ref<T[]>, defaultPageSize = 50) {
  const currentPage = ref(1)
  const pageSize = ref(defaultPageSize)

  const total = computed(() => source.value.length)

  const totalPages = computed(() =>
    pageSize.value > 0 ? Math.ceil(total.value / pageSize.value) : 1
  )

  /** 当前页可见数据 */
  const pagedData = computed<T[]>(() => {
    const start = (currentPage.value - 1) * pageSize.value
    const end = start + pageSize.value
    return source.value.slice(start, end)
  })

  /** 是否还有更多数据未展示 */
  const hasMore = computed(() => currentPage.value < totalPages.value)

  /** 切换页码 */
  function handlePageChange(page: number): void {
    currentPage.value = page
  }

  /** 切换每页条数 */
  function handleSizeChange(size: number): void {
    pageSize.value = size
    currentPage.value = 1
  }

  /** 加载更多（增量追加，适用于 "加载更多" 按钮） */
  function loadMore(): void {
    if (hasMore.value) {
      currentPage.value++
    }
  }

  /** 重置到第一页（数据刷新后调用） */
  function reset(): void {
    currentPage.value = 1
  }

  return {
    currentPage,
    pageSize,
    total,
    totalPages,
    pagedData,
    hasMore,
    handlePageChange,
    handleSizeChange,
    loadMore,
    reset,
  }
}
