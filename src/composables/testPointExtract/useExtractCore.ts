import { ElMessage, ElMessageBox } from 'element-plus'
import { testPointApi } from '@/api/testPoint'
import type { TestPointDraft } from '@/types/testPoint'
import { PROGRESS_PHASES } from './types'
import type { ExtractSharedState, ResourceRow } from './types'

export function useExtractCore(state: ExtractSharedState) {
  function goToExtract(row?: ResourceRow): void {
    const target = row ?? state.selectedResource.value
    if (!target) {
      ElMessage.warning('请先选择需求文件')
      return
    }
    state.selectedResource.value = target
    state.currentStep.value = 2
  }

  function startExtract(): void {
    if (!state.selectedResource.value) {
      ElMessage.warning('请先选择需求文件')
      return
    }
    extractTestPoints()
  }

  function retryExtract(): void {
    state.errorMessage.value = ''
    extractTestPoints()
  }

  function goToNextStep(): void {
    if (state.currentStep.value === 0 && !state.formData.project_id) {
      ElMessage.warning('请先选择项目')
      return
    }
    if (state.currentStep.value === 1 && !state.selectedResource.value) {
      ElMessage.warning('请先选择需求资源')
      return
    }
    if (state.currentStep.value < 3) {
      state.currentStep.value++
    }
  }

  function goToPrevStep(): void {
    if (state.currentStep.value > 0) {
      state.currentStep.value--
    }
  }

  async function extractTestPoints(): Promise<void> {
    const target = state.selectedResource.value
    if (!target) {
      ElMessage.warning('请先选择需求文件')
      return
    }

    if (state.extracting.value) {
      ElMessage.warning('正在提取中，请稍候')
      return
    }

    state.testPoints.value = []
    state.savedFromDb.value = false
    state.dbTotal.value = 0
    state.currentPage.value = 1
    state.errorMessage.value = ''
    state.extracting.value = true
    state.progress.value = 0
    state.progressText.value = '正在读取文件内容...'

    if (state.progressInterval.value) {
      clearInterval(state.progressInterval.value)
      state.progressInterval.value = null
    }

    let phaseIndex = 0

    state.progressInterval.value = setInterval(() => {
      if (phaseIndex < PROGRESS_PHASES.length) {
        const targetProgress = PROGRESS_PHASES[phaseIndex].end
        if (state.progress.value < targetProgress) {
          state.progress.value = Math.round(
            Math.min(state.progress.value + Math.random() * 4 + 1, targetProgress)
          )
          state.progressText.value = PROGRESS_PHASES[phaseIndex].text
        } else {
          phaseIndex++
        }
      }
    }, 300)

    try {
      state.progressText.value = PROGRESS_PHASES[PROGRESS_PHASES.length - 1].text

      const response = await testPointApi.extract({
        file_id: target.id,
      })

      if (response && response.items) {
        state.testPoints.value = response.items.map((item: TestPointDraft, index: number) => ({
          id: item.id ?? index + 1,
          module: item.module || '',
          point: item.point || '',
          priority: typeof item.priority === 'number' ? item.priority : 2,
          ai_prompt: item.ai_prompt ?? undefined,
          create_time: item.create_time ?? undefined,
          _raw: { ...item } as Record<string, unknown>,
        }))
        state.savedFromDb.value = false
        ElMessage.success(`测试点提取成功，共 ${state.testPoints.value.length} 个`)
      } else {
        ElMessage.warning('未提取到测试点')
      }

      clearInterval(state.progressInterval.value)
      state.progressInterval.value = null
      state.progress.value = 100
      state.progressText.value = `提取完成！共 ${state.testPoints.value.length} 个测试点`
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      if (state.progressInterval.value) {
        clearInterval(state.progressInterval.value)
        state.progressInterval.value = null
      }
      state.progress.value = 0

      const detail = err.response?.data?.detail
      if (
        typeof detail === 'string' &&
        !detail.includes('traceback') &&
        !detail.includes('stack')
      ) {
        state.errorMessage.value = detail.length > 200 ? detail.slice(0, 200) + '...' : detail
      } else if (err.response?.data?.message) {
        state.errorMessage.value = err.response.data.message
      } else {
        state.errorMessage.value = '测试点提取失败，请检查网络连接或稍后重试'
      }

      ElMessage.error('提取失败，请查看错误信息')
    } finally {
      state.extracting.value = false
    }
  }

  function handleCancel(): void {
    ElMessageBox.confirm('确定要取消提取吗？', '取消确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      if (state.progressInterval.value) {
        clearInterval(state.progressInterval.value)
        state.progressInterval.value = null
      }
      state.extracting.value = false
      state.progress.value = 0
      state.progressText.value = '已取消'
      ElMessage.info('提取已取消')
    })
  }

  return {
    goToExtract,
    startExtract,
    retryExtract,
    goToNextStep,
    goToPrevStep,
    extractTestPoints,
    handleCancel,
  }
}
