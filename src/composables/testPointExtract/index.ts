import { onUnmounted, provide, inject, type InjectionKey } from 'vue'
import { createSharedState } from './createSharedState'
import { useResourceState } from './useResourceState'
import { useTestPointState } from './useTestPointState'
import { useExtractCore } from './useExtractCore'
import { useTestPointActions } from './useTestPointActions'
import type { TestPointItem, ProjectItem, FileItem, ResourceRow } from './types'

export type { TestPointItem, ProjectItem, FileItem, ResourceRow }

export type TestPointExtractState = ReturnType<typeof createExtractState>

const EXTRACT_KEY: InjectionKey<TestPointExtractState> = Symbol('testPointExtract')

function createExtractState() {
  const state = createSharedState()
  const resource = useResourceState(state)
  const testPoint = useTestPointState(state)
  const extract = useExtractCore(state)
  const actions = useTestPointActions(state, {
    loadSavedTestPoints: testPoint.loadSavedTestPoints,
    clearSelection: testPoint.clearSelection,
  })

  async function handleProjectChange(projectId: number): Promise<void> {
    if (projectId) {
      await resource.loadResources(projectId)
      state.selectedResource.value = null
      state.testPoints.value = []
      state.savedFromDb.value = false
      state.dbTotal.value = 0
      state.currentPage.value = 1
      state.errorMessage.value = ''
      await testPoint.loadSavedTestPoints(projectId)
    } else {
      state.files.value = []
      state.selectedResource.value = null
      state.testPoints.value = []
      state.savedFromDb.value = false
      state.dbTotal.value = 0
      state.currentPage.value = 1
    }
  }

  async function init(): Promise<void> {
    await resource.getProjects()

    const idParam = Number(state.route.query.file_id)
    const projectIdParam = Number(state.route.query.project_id)

    if (projectIdParam) {
      state.formData.project_id = projectIdParam
      await resource.loadResources(projectIdParam)
      await testPoint.loadSavedTestPoints(projectIdParam)
      if (idParam) {
        const row = resource.resourceRows.value.find((r) => r.id === idParam)
        if (row) {
          state.selectedResource.value = row
        }
      }
    }
  }

  function cleanup(): void {
    if (state.progressInterval.value) {
      clearInterval(state.progressInterval.value)
      state.progressInterval.value = null
    }
  }

  onUnmounted(cleanup)

  return {
    currentStep: state.currentStep,
    formData: state.formData,
    projects: state.projects,
    files: state.files,
    selectedResource: state.selectedResource,
    testPoints: state.testPoints,
    extracting: state.extracting,
    saving: state.saving,
    batchDeleting: state.batchDeleting,
    deleting: state.deleting,
    savedFromDb: state.savedFromDb,
    loadingTestPoints: state.loadingTestPoints,
    selectedRows: state.selectedRows,
    testPointTable: state.testPointTable,
    currentPage: state.currentPage,
    pageSize: state.pageSize,
    dbTotal: state.dbTotal,
    progress: state.progress,
    progressText: state.progressText,
    errorMessage: state.errorMessage,
    dialogVisible: state.dialogVisible,
    resourceTypeFilter: state.resourceTypeFilter,
    editForm: state.editForm,
    editingIndex: state.editingIndex,
    updating: state.updating,
    selectedProjectInfo: resource.selectedProjectInfo,
    currentProjectId: resource.currentProjectId,
    resourceRows: resource.resourceRows,
    filteredResourceRows: resource.filteredResourceRows,
    progressStatus: testPoint.progressStatus,
    paginatedTestPoints: testPoint.paginatedTestPoints,
    moduleCount: testPoint.moduleCount,
    totalDisplayCount: testPoint.totalDisplayCount,
    formatFileSize: resource.formatFileSize,
    getResourceTypeLabel: resource.getResourceTypeLabel,
    getResourceTypeTagType: resource.getResourceTypeTagType,
    getResourceIcon: resource.getResourceIcon,
    getPriorityTagType: testPoint.getPriorityTagType,
    getPriorityLabel: testPoint.getPriorityLabel,
    getPriorityCount: testPoint.getPriorityCount,
    getModuleDistribution: testPoint.getModuleDistribution,
    getResourceTypeCount: resource.getResourceTypeCount,
    getResourceTypePercentage: resource.getResourceTypePercentage,
    getProjects: resource.getProjects,
    loadResources: resource.loadResources,
    loadSavedTestPoints: testPoint.loadSavedTestPoints,
    handleProjectChange,
    handleResourceSelect: resource.handleResourceSelect,
    goToExtract: extract.goToExtract,
    startExtract: extract.startExtract,
    retryExtract: extract.retryExtract,
    goToNextStep: extract.goToNextStep,
    goToPrevStep: extract.goToPrevStep,
    handlePageChange: testPoint.handlePageChange,
    extractTestPoints: extract.extractTestPoints,
    handleCancel: extract.handleCancel,
    handleSelectionChange: testPoint.handleSelectionChange,
    clearSelection: testPoint.clearSelection,
    batchDeleteTestPoints: actions.batchDeleteTestPoints,
    editTestPoint: actions.editTestPoint,
    saveTestPoint: actions.saveTestPoint,
    deleteTestPoint: actions.deleteTestPoint,
    saveToDatabase: actions.saveToDatabase,
    generateTestCases: actions.generateTestCases,
    goToManagement: actions.goToManagement,
    init,
    cleanup,
  }
}

export function provideTestPointExtract(): TestPointExtractState {
  const state = createExtractState()
  provide(EXTRACT_KEY, state)
  return state
}

export function useTestPointExtract(): TestPointExtractState {
  const state = inject(EXTRACT_KEY)
  if (!state) {
    throw new Error(
      'useTestPointExtract() must be called within a component tree that provides test point extract state.'
    )
  }
  return state
}
