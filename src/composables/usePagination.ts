/**
 * 通用分页 composable
 *
 * 统一各列表页的 currentPage / pageSize / total 状态管理，
 * 消除各 store 和 composable 中重复的分页逻辑。
 */
import { reactive } from 'vue'

export interface PaginationState {
  page: number
  pageSize: number
  total: number
}

export interface UsePaginationOptions {
  defaultPageSize?: number
  onPageChange?: () => void
}

export function usePagination(options: UsePaginationOptions = {}) {
  const pagination = reactive<PaginationState>({
    page: 1,
    pageSize: options.defaultPageSize ?? 10,
    total: 0,
  })

  /** 切换页码 */
  function handleCurrentChange(page: number): void {
    pagination.page = page
    options.onPageChange?.()
  }

  /** 切换每页条数 */
  function handleSizeChange(size: number): void {
    pagination.pageSize = size
    pagination.page = 1
    options.onPageChange?.()
  }

  /** 重置到第一页 */
  function resetToFirstPage(): void {
    pagination.page = 1
  }

  /** 设置总数 */
  function setTotal(total: number): void {
    pagination.total = total
  }

  /** 获取请求参数 */
  function getParams(): { page: number; page_size: number } {
    return { page: pagination.page, page_size: pagination.pageSize }
  }

  return {
    pagination,
    handleCurrentChange,
    handleSizeChange,
    resetToFirstPage,
    setTotal,
    getParams,
  }
}
