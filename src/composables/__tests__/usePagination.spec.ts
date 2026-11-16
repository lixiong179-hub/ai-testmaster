import { describe, it, expect, vi } from 'vitest'
import { usePagination } from '../usePagination'

describe('usePagination — 初始状态', () => {
  it('默认 page=1 / pageSize=10 / total=0', () => {
    const { pagination } = usePagination()

    expect(pagination).toEqual({ page: 1, pageSize: 10, total: 0 })
  })

  it('支持自定义默认每页条数', () => {
    const { pagination } = usePagination({ defaultPageSize: 20 })

    expect(pagination.pageSize).toBe(20)
  })
})

describe('usePagination — 交互', () => {
  it('切换页码并触发回调', () => {
    const onPageChange = vi.fn()
    const { pagination, handleCurrentChange } = usePagination({ onPageChange })

    handleCurrentChange(3)

    expect(pagination.page).toBe(3)
    expect(onPageChange).toHaveBeenCalledTimes(1)
  })

  it('切换每页条数时回到第一页并触发回调', () => {
    const onPageChange = vi.fn()
    const { pagination, handleCurrentChange, handleSizeChange } = usePagination({ onPageChange })
    handleCurrentChange(4)

    handleSizeChange(50)

    expect(pagination.pageSize).toBe(50)
    expect(pagination.page).toBe(1)
    expect(onPageChange).toHaveBeenCalledTimes(2)
  })

  it('resetToFirstPage 只重置页码', () => {
    const { pagination, handleCurrentChange, resetToFirstPage } = usePagination()
    handleCurrentChange(5)

    resetToFirstPage()

    expect(pagination.page).toBe(1)
    expect(pagination.pageSize).toBe(10)
  })

  it('setTotal 写入总数', () => {
    const { pagination, setTotal } = usePagination()

    setTotal(137)

    expect(pagination.total).toBe(137)
  })

  it('getParams 返回服务端分页参数口径', () => {
    const { handleCurrentChange, handleSizeChange, getParams } = usePagination()
    handleSizeChange(20)
    handleCurrentChange(2)

    expect(getParams()).toEqual({ page: 2, page_size: 20 })
  })

  it('未传回调时不报错', () => {
    const { handleCurrentChange, handleSizeChange } = usePagination()

    expect(() => {
      handleCurrentChange(2)
      handleSizeChange(30)
    }).not.toThrow()
  })
})
