import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { useClientPagination } from '../useClientPagination'

function range(count: number): number[] {
  return Array.from({ length: count }, (_, i) => i + 1)
}

describe('useClientPagination — 切片', () => {
  it('默认每页 50 条并返回首页切片', () => {
    const source = ref(range(120))
    const api = useClientPagination(source)

    expect(api.pageSize.value).toBe(50)
    expect(api.total.value).toBe(120)
    expect(api.totalPages.value).toBe(3)
    expect(api.pagedData.value).toHaveLength(50)
    expect(api.pagedData.value[0]).toBe(1)
    expect(api.pagedData.value[49]).toBe(50)
    expect(api.hasMore.value).toBe(true)
  })

  it('末页切片只含剩余数据且 hasMore 为 false', () => {
    const source = ref(range(120))
    const api = useClientPagination(source)

    api.handlePageChange(3)

    expect(api.pagedData.value).toEqual(range(120).slice(100))
    expect(api.hasMore.value).toBe(false)
  })

  it('数据收缩后按当前位置重新切片', () => {
    const source = ref(range(120))
    const api = useClientPagination(source)
    api.handlePageChange(3)

    source.value = range(60)

    expect(api.total.value).toBe(60)
    expect(api.totalPages.value).toBe(2)
    expect(api.pagedData.value).toEqual([])
  })

  it('空数据时 total/totalPages 为 0 且无更多', () => {
    const api = useClientPagination(ref<number[]>([]))

    expect(api.total.value).toBe(0)
    expect(api.totalPages.value).toBe(0)
    expect(api.pagedData.value).toEqual([])
    expect(api.hasMore.value).toBe(false)
  })

  it('pageSize 为 0 时 totalPages 兜底为 1', () => {
    const api = useClientPagination(ref(range(10)), 0)

    expect(api.totalPages.value).toBe(1)
  })
})

describe('useClientPagination — 翻页动作', () => {
  it('切换每页条数会回到第一页', () => {
    const api = useClientPagination(ref(range(100)))
    api.handlePageChange(2)

    api.handleSizeChange(20)

    expect(api.pageSize.value).toBe(20)
    expect(api.currentPage.value).toBe(1)
    expect(api.totalPages.value).toBe(5)
  })

  it('loadMore 仅在还有更多时前进一页', () => {
    const api = useClientPagination(ref(range(120)), 50)

    api.loadMore()
    expect(api.currentPage.value).toBe(2)

    api.loadMore()
    expect(api.currentPage.value).toBe(3)

    api.loadMore()
    expect(api.currentPage.value).toBe(3)
  })

  it('reset 回到第一页', () => {
    const api = useClientPagination(ref(range(120)))
    api.handlePageChange(3)

    api.reset()

    expect(api.currentPage.value).toBe(1)
  })
})
