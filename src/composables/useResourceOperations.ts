/**
 * 资源操作 Composable
 * 职责：编辑、删除、AI分析等操作
 */
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fileApi } from '@/api/file'
import { uiPrototypeApi } from '@/api/uiPrototype'
import type { Resource } from './useResourceList'
import type { Iteration } from '@/api/iteration'

export function useResourceOperations(
  iterationManager: ReturnType<typeof import('./useIterationManager').useIterationManager>,
  refreshResources: () => void
) {
  const router = useRouter()

  /**
   * AI分析操作
   * @param row 资源行数据
   */
  const handleAnalyze = (row: Resource) => {
    const baseQuery: Record<string, string> = {
      project_id: String(row.project_id),
      filename: row.name,
    }

    if (row.resource_type === 'ui_mockup' && row.source_type === 'ui_prototype') {
      // UI原型资源的AI分析
      Object.assign(baseQuery, {
        source_type: 'ui_prototype',
        prototype_project_id: String(row.prototype_project_id || row.id),
      })
    } else {
      // 文件资源的AI分析
      Object.assign(baseQuery, {
        source_type: 'file',
        file_id: String(row.id),
      })
    }

    // 携带迭代信息（仅当有有效迭代ID时才携带）
    if (row.iteration_id && row.iteration_id > 0) {
      baseQuery.iteration_id = String(row.iteration_id)
      const iteration = iterationManager.iterations.find(
        (it: Iteration) => it.id === row.iteration_id
      )
      if (iteration) {
        baseQuery.iteration_name = iteration.name
      }
    } else if (
      iterationManager.selectedIterationId !== null &&
      iterationManager.selectedIterationId > 0
    ) {
      baseQuery.iteration_id = String(iterationManager.selectedIterationId)
      const iteration = iterationManager.iterations.find(
        (it: Iteration) => it.id === iterationManager.selectedIterationId
      )
      if (iteration) {
        baseQuery.iteration_name = iteration.name
      }
    }

    if (row.resource_type === 'ui_mockup' && row.source_type === 'ui_prototype') {
      // UI原型提取统一走测试点管理页的 ExtractDialog
      router.push({
        path: '/home/case/test-point-management',
        query: {
          projectId: baseQuery.project_id,
          openExtract: '1',
          filename: baseQuery.filename,
        },
      })
      return
    }

    router.push({
      path: '/home/case/test-point-management',
      query: {
        projectId: baseQuery.project_id,
        file_id: baseQuery.file_id,
        openExtract: '1',
        filename: baseQuery.filename,
      },
    })
  }

  /**
   * 删除资源
   * @param row 资源行数据
   */
  const handleDelete = async (row: Resource) => {
    // 构建更详细的确认消息
    let confirmMessage = ''
    if (row.resource_type === 'ui_mockup' && row.source_type === 'ui_prototype') {
      confirmMessage =
        `确定要删除UI原型项目 "${row.name}" 吗？\n\n` +
        `该操作将同时删除：\n` +
        `- 其下所有 ${row.screen_count || 0} 张图片\n` +
        `- 相关的测试用例关联数据\n\n` +
        `⚠️ 此操作不可撤销！`
    } else {
      // 查找所属迭代名称
      let iterationInfo = ''
      if (row.iteration_id && row.iteration_id > 0) {
        const iterationName = iterationManager.getIterationNameById(row.iteration_id)
        if (iterationName && iterationName !== '未分类') {
          iterationInfo = `\n所属迭代：${iterationName}`
        }
      }

      confirmMessage = `确定要删除 "${row.name}" 吗？${iterationInfo}\n\n⚠️ 此操作不可撤销！`
    }

    try {
      await ElMessageBox.confirm(confirmMessage, '删除确认', {
        type: 'warning',
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
      })

      if (row.resource_type === 'ui_mockup' && row.source_type === 'ui_prototype') {
        await uiPrototypeApi.deleteUIPrototypeProject(row.prototype_project_id || row.id)
        ElMessage.success(`UI原型项目 "${row.name}" 已删除`)
      } else {
        await fileApi.deleteFile(row.id, row.project_id)
        ElMessage.success(`文件 "${row.name}" 已删除`)
      }

      // 刷新列表
      refreshResources()
    } catch (error: unknown) {
      if (error !== 'cancel') {
        iterationManager.showError('删除', error)
      }
    }
  }

  /**
   * 编辑或查看资源详情
   * 对于UI原型资源，跳转到UI原型页面
   * 对于文件资源，打开编辑弹窗（由外部处理）
   * @param row 资源行数据
   * @returns 是否需要在弹窗中编辑（false表示已跳转）
   */
  const handleEditNavigation = (row: Resource): boolean => {
    if (row.resource_type === 'ui_mockup' && row.source_type === 'ui_prototype') {
      const query: Record<string, string> = {
        project_id: String(row.project_id),
        prototype_project_id: String(row.prototype_project_id || row.id),
        name: row.name,
      }
      if (
        iterationManager.selectedIterationId !== null &&
        iterationManager.selectedIterationId > 0
      ) {
        query.iteration_id = String(iterationManager.selectedIterationId)
        const iteration = iterationManager.iterations.find(
          (it: Iteration) => it.id === iterationManager.selectedIterationId
        )
        if (iteration) {
          query.iteration_name = iteration.name
        }
      }
      router.push({
        path: '/home/requirement/ui-prototype',
        query,
      })
      return false // 不需要打开弹窗
    }
    return true // 需要在弹窗中编辑
  }

  return {
    handleAnalyze,
    handleDelete,
    handleEditNavigation,
  }
}
