import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useCaseStore } from '@/store/case'
import type { TestCase } from '@/api/case'
import type { PaginationState } from './useCaseFilter'

export interface UseCaseSelectionOptions {
  caseStore: ReturnType<typeof useCaseStore>
  paginatedTestCases: ComputedRef<TestCase[]>
  filteredTestCases: ComputedRef<TestCase[]>
  pagination: Ref<PaginationState>
  loading: Ref<boolean>
}

/** 用例选择与批量操作 composable */
export function useCaseSelection(options: UseCaseSelectionOptions) {
  const { caseStore, paginatedTestCases, filteredTestCases, pagination, loading } = options

  // 批量选择状态
  const selectedCases = ref<number[]>([])

  // 存储最近删除的用例ID，用于撤销
  const recentlyDeletedIds = ref<number[]>([])

  // 是否全选当前页
  const isAllSelected = computed((): boolean => {
    if (paginatedTestCases.value.length === 0) return false
    return paginatedTestCases.value.every((item) => selectedCases.value.includes(item.id))
  })

  // 是否半选状态
  const isIndeterminate = computed((): boolean => {
    if (paginatedTestCases.value.length === 0) return false
    const selectedCount = paginatedTestCases.value.filter((item) =>
      selectedCases.value.includes(item.id)
    ).length
    return selectedCount > 0 && selectedCount < paginatedTestCases.value.length
  })

  // 使用 Set 优化查找性能
  const selectedCasesSet = computed((): Set<number> => new Set(selectedCases.value))

  /** 判断某用例是否已选中 */
  const isSelected = (id: number): boolean => {
    return selectedCasesSet.value.has(id)
  }

  /** 处理单个用例的选择/取消 */
  const handleCaseSelect = (val: boolean, id: number): void => {
    if (val) {
      if (!selectedCases.value.includes(id)) {
        selectedCases.value.push(id)
      }
    } else {
      selectedCases.value = selectedCases.value.filter((caseId) => caseId !== id)
    }
  }

  /** 全选/取消全选当前页 */
  const handleSelectAll = (val: boolean): void => {
    if (val) {
      // 添加当前页所有未选择的项
      paginatedTestCases.value.forEach((item) => {
        if (!selectedCases.value.includes(item.id)) {
          selectedCases.value.push(item.id)
        }
      })
    } else {
      // 移除当前页所有项
      const currentPageIds = paginatedTestCases.value.map((item) => item.id)
      selectedCases.value = selectedCases.value.filter((id) => !currentPageIds.includes(id))
    }
  }

  /** 选择所有页的全部用例 */
  const handleSelectAllPages = (): void => {
    filteredTestCases.value.forEach((item) => {
      if (!selectedCases.value.includes(item.id)) {
        selectedCases.value.push(item.id)
      }
    })
  }

  /** 清空所有选择 */
  const clearSelection = (): void => {
    selectedCases.value = []
  }

  /** 撤销删除 */
  const handleUndoDelete = async (): Promise<void> => {
    if (recentlyDeletedIds.value.length === 0) {
      ElMessage.warning('没有可撤销的删除操作')
      return
    }

    try {
      loading.value = true
      const result = await caseStore.batchRestoreTestCases(recentlyDeletedIds.value)
      loading.value = false

      // 清空已记录的删除ID
      recentlyDeletedIds.value = []

      if (result.fail_count === 0 && result.not_found_count === 0) {
        ElMessage.success(`成功恢复 ${result.success_count} 个测试用例`)
      } else {
        ElMessage.warning(
          `恢复完成：成功 ${result.success_count} 个，失败 ${result.fail_count} 个，未找到 ${result.not_found_count} 个`
        )
      }
    } catch (error) {
      loading.value = false
      ElMessage.error('撤销删除失败，请稍后重试')
    }
  }

  /** 批量删除选中用例 */
  const handleBatchDelete = (): void => {
    if (selectedCases.value.length === 0) {
      ElMessage.warning('请先选择要删除的用例')
      return
    }

    ElMessageBox.confirm(
      `确定要删除选中的 ${selectedCases.value.length} 个测试用例吗？`,
      '批量删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
      .then(async () => {
        loading.value = true

        try {
          // 调用批量删除API
          const result = await caseStore.batchDeleteTestCases(selectedCases.value)

          loading.value = false

          // 记录删除的ID用于撤销
          if (result.deleted_ids && result.deleted_ids.length > 0) {
            recentlyDeletedIds.value = result.deleted_ids
          }

          // 清空选择
          selectedCases.value = []

          if (result.fail_count === 0 && result.not_found_count === 0) {
            // 显示带撤销按钮的成功消息
            ElMessage.success({
              message: `成功删除 ${result.success_count} 个测试用例`,
              duration: 5000,
              showClose: true,
            })
          } else {
            // 显示详细结果弹窗
            ElMessageBox.alert(
              `<div style="text-align: center;">
              <div style="font-size: 48px; margin-bottom: 16px;">${result.success_count === 0 ? '❌' : '⚠️'}</div>
              <div style="font-size: 18px; margin-bottom: 12px;">删除完成</div>
              <div style="color: #67c23a; margin-bottom: 8px;">✓ 成功：${result.success_count} 个</div>
              ${result.fail_count > 0 ? `<div style="color: #f56c6c; margin-bottom: 8px;">✗ 失败：${result.fail_count} 个</div>` : ''}
              ${result.not_found_count > 0 ? `<div style="color: #e6a23c;">⚠ 未找到：${result.not_found_count} 个</div>` : ''}
            </div>`,
              '删除结果',
              {
                confirmButtonText: '确定',
                dangerouslyUseHTMLString: true,
                type: result.success_count === 0 ? 'error' : 'warning',
              }
            )
          }

          // 检查当前页是否还有数据，如果没有则回到上一页
          const currentPageData = paginatedTestCases.value
          if (currentPageData.length === 0 && pagination.value.currentPage > 1) {
            pagination.value.currentPage--
          }
        } catch (error) {
          loading.value = false
          ElMessage.error('批量删除失败，请稍后重试')
        }
      })
      .catch(() => {})
  }

  return {
    selectedCases,
    recentlyDeletedIds,
    isAllSelected,
    isIndeterminate,
    isSelected,
    handleCaseSelect,
    handleSelectAll,
    handleSelectAllPages,
    clearSelection,
    handleBatchDelete,
    handleUndoDelete,
  }
}
