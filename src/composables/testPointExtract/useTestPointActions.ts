import { ElMessage, ElMessageBox } from 'element-plus'
import { testPointApi } from '@/api/testPoint'
import type { ExtractSharedState, TestPointItem } from './types'

export function useTestPointActions(
  state: ExtractSharedState,
  deps: {
    loadSavedTestPoints: (projectId: number, page?: number) => Promise<void>
    clearSelection: () => void
  }
) {
  async function batchDeleteTestPoints(): Promise<void> {
    if (state.selectedRows.value.length === 0) {
      ElMessage.warning('请先选择要删除的测试点')
      return
    }

    if (!state.formData.project_id) {
      ElMessage.warning('请先选择项目')
      return
    }

    try {
      await ElMessageBox.confirm(
        `确定要删除选中的 ${state.selectedRows.value.length} 个测试点吗？此操作不可恢复！`,
        '批量删除确认',
        {
          confirmButtonText: '确定删除',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )

      state.batchDeleting.value = true

      const ids = state.selectedRows.value.map((row) => row.id)

      const result = await testPointApi.batchDelete(Number(state.formData.project_id), ids)

      if (result.code === 200) {
        ElMessage.success(result.message || `成功删除 ${result.data.deleted_count} 个测试点`)
        deps.clearSelection()

        if (state.savedFromDb.value) {
          await deps.loadSavedTestPoints(Number(state.formData.project_id), state.currentPage.value)
        } else {
          const deletedIds = new Set(ids)
          state.testPoints.value = state.testPoints.value.filter((item) => !deletedIds.has(item.id))
        }
      } else {
        throw new Error(result.message || '批量删除失败')
      }
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      if (error !== 'cancel') {
        console.error('批量删除失败:', error)
        ElMessage.error(
          err.response?.data?.detail ||
            err.response?.data?.message ||
            err.message ||
            '批量删除失败，请稍后重试'
        )
      }
    } finally {
      state.batchDeleting.value = false
    }
  }

  function editTestPoint(testPoint: TestPointItem): void {
    const index = state.testPoints.value.findIndex((item) => item.id === testPoint.id)
    state.editingIndex.value = index
    state.editForm.id = testPoint.id
    state.editForm.module = testPoint.module
    state.editForm.function = testPoint.function || ''
    state.editForm.point = testPoint.point
    state.editForm.priority = testPoint.priority || 2
    state.dialogVisible.value = true
  }

  async function saveTestPoint(): Promise<void> {
    if (!state.editForm.module || !state.editForm.point) {
      ElMessage.warning('请填写完整的测试点信息')
      return
    }

    try {
      state.updating.value = true

      const index = state.editingIndex.value
      if (index !== -1 && index < state.testPoints.value.length) {
        const currentPoint = state.testPoints.value[index]

        if (currentPoint.id && state.savedFromDb.value && state.formData.project_id) {
          const result = await testPointApi.update(currentPoint.id, {
            project_id: Number(state.formData.project_id),
            module: state.editForm.module,
            function: state.editForm.function,
            point: state.editForm.point,
            priority: state.editForm.priority,
            ai_prompt: currentPoint.ai_prompt,
          })

          if (result.code === 200) {
            state.testPoints.value[index] = {
              ...result.data,
              ai_prompt: result.data.ai_prompt ?? undefined,
              _raw: result.data as unknown as Record<string, unknown>,
            }
            ElMessage.success('测试点更新成功')
            state.dialogVisible.value = false

            await deps.loadSavedTestPoints(
              Number(state.formData.project_id),
              state.currentPage.value
            )
          } else {
            throw new Error(result.message || '更新失败')
          }
        } else {
          state.testPoints.value[index] = { ...state.editForm }
          ElMessage.success('测试点更新成功（本地）')
          state.dialogVisible.value = false
        }
      }
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      console.error('保存测试点失败:', error)
      ElMessage.error(
        err.response?.data?.detail ||
          err.response?.data?.message ||
          err.message ||
          '保存失败，请稍后重试'
      )
    } finally {
      state.updating.value = false
    }
  }

  async function deleteTestPoint(testPoint: TestPointItem): Promise<void> {
    try {
      if (!state.formData.project_id) {
        ElMessage.warning('请先选择项目')
        return
      }

      state.deleting.value = true

      if (testPoint.id && state.savedFromDb.value) {
        const result = await testPointApi.delete(testPoint.id, Number(state.formData.project_id))

        if (result.code === 200) {
          ElMessage.success('删除成功')
          let targetPage = state.currentPage.value
          const totalAfterDelete = state.dbTotal.value - 1
          const maxPage = Math.max(1, Math.ceil(totalAfterDelete / state.pageSize.value))
          if (targetPage > maxPage) {
            targetPage = maxPage
          }
          await deps.loadSavedTestPoints(Number(state.formData.project_id), targetPage)
        } else {
          ElMessage.error(result.message || '删除失败')
        }
      } else {
        const index = state.testPoints.value.findIndex((item) => item.id === testPoint.id)
        if (index !== -1) {
          state.testPoints.value.splice(index, 1)
        }
        ElMessage.success('删除成功（本地）')
      }
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      console.error('删除测试点失败:', error)
      ElMessage.error(
        err.response?.data?.detail ||
          err.response?.data?.message ||
          err.message ||
          '删除失败，请稍后重试'
      )
    } finally {
      state.deleting.value = false
    }
  }

  async function saveToDatabase(): Promise<void> {
    if (state.testPoints.value.length === 0) {
      ElMessage.warning('没有可保存的测试点')
      return
    }

    const projectId =
      state.selectedResource.value?.project_id ||
      (state.formData.project_id ? Number(state.formData.project_id) : 0)
    if (!projectId) {
      ElMessage.warning('请先选择项目')
      return
    }

    state.saving.value = true
    try {
      const rawData = state.testPoints.value
        .map((tp) =>
          tp._raw
            ? JSON.parse(JSON.stringify(tp._raw))
            : {
                module: tp.module,
                point: tp.point,
                priority: tp.priority,
              }
        )
        .filter((raw) => raw && raw.module && raw.point)

      if (rawData.length === 0) {
        ElMessage.warning('没有有效的测试点数据')
        state.saving.value = false
        return
      }

      const response = await testPointApi.batchSave(projectId, rawData)

      if (response?.code === 200) {
        ElMessage.success(response?.message || `成功保存 ${rawData.length} 个测试点`)
        state.savedFromDb.value = true
        await deps.loadSavedTestPoints(projectId)
      } else {
        ElMessage.error(response?.message || '保存失败')
      }
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      console.error('保存测试点失败:', error)
      ElMessage.error(
        err.response?.data?.detail ||
          err.response?.data?.message ||
          err.message ||
          '保存到数据库失败'
      )
    } finally {
      state.saving.value = false
    }
  }

  function generateTestCases(): void {
    if (state.testPoints.value.length === 0) {
      ElMessage.warning('请先提取或加载测试点')
      return
    }

    const projectId =
      state.selectedResource.value?.project_id ||
      (state.formData.project_id ? Number(state.formData.project_id) : 0)
    if (!projectId) {
      ElMessage.warning('请先选择项目')
      return
    }

    const query: Record<string, string> = {
      project_id: String(projectId),
      test_point_ids: JSON.stringify(state.testPoints.value.map((tp) => tp.id)),
    }

    if (state.selectedResource.value) {
      query.file_id = String(state.selectedResource.value.id)
      query.filename = state.selectedResource.value.display_name
    }

    state.router.push({ path: '/home/case/ai-generate', query })
  }

  function goToManagement(): void {
    const query: Record<string, string> = {}
    const projectId = state.formData.project_id ? Number(state.formData.project_id) : 0
    if (projectId) {
      query.projectId = String(projectId)
    }
    state.router.push({
      path: '/home/case/test-point-management',
      query,
    })
  }

  return {
    batchDeleteTestPoints,
    editTestPoint,
    saveTestPoint,
    deleteTestPoint,
    saveToDatabase,
    generateTestCases,
    goToManagement,
  }
}
