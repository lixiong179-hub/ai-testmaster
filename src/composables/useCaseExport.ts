import { ref, type Ref, type ComputedRef } from 'vue'
import { ElMessage } from 'element-plus'
import { testCaseViewApi } from '@/api/testCaseView'
import { downloadFromResponse, parseBlobError } from '@/utils/download'
import type { TestCase } from '@/api/case'

export interface UseCaseExportOptions {
  filteredTestCases: ComputedRef<TestCase[]>
  selectedCases: Ref<number[]>
}

/** 用例导出功能 composable */
export function useCaseExport(options: UseCaseExportOptions) {
  const { filteredTestCases, selectedCases } = options

  const exporting = ref(false)

  /** 导出指定用例ID列表为功能用例Excel */
  const exportFunctionalExcel = async (ids: number[]): Promise<void> => {
    if (ids.length === 0) {
      ElMessage.warning('暂无可导出的用例')
      return
    }
    exporting.value = true
    try {
      const resp = await testCaseViewApi.exportToFunctionalExcel(ids)
      const fallback = `功能测试用例_${new Date().toISOString().slice(0, 10)}.xlsx`
      downloadFromResponse(resp, fallback)

      // 后端可能因权限静默过滤掉部分用例，前端给出提示
      const skippedRaw = resp.headers?.['x-export-skipped-count']
      const skipped = skippedRaw ? Number(skippedRaw) : 0
      const exported = ids.length - skipped
      if (skipped > 0) {
        ElMessage.warning(`已导出 ${exported} 条用例，${skipped} 条因权限被忽略`)
      } else {
        ElMessage.success(`已导出 ${exported} 条用例`)
      }
    } catch (err) {
      const msg = await parseBlobError(err, '导出失败，请稍后重试')
      console.error('导出失败:', err)
      ElMessage.error(msg)
    } finally {
      exporting.value = false
    }
  }

  /** 导出全部（按当前筛选结果） */
  const handleExportAll = (): void => {
    const ids = filteredTestCases.value.map((c) => c.id)
    exportFunctionalExcel(ids)
  }

  /** 导出选中用例 */
  const handleExportSelected = (): void => {
    if (selectedCases.value.length === 0) {
      ElMessage.warning('请先选择要导出的用例')
      return
    }
    exportFunctionalExcel([...selectedCases.value])
  }

  return {
    exporting,
    exportFunctionalExcel,
    handleExportAll,
    handleExportSelected,
  }
}
