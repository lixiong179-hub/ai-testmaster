import { defineStore } from 'pinia'
import { createGenerateState } from './generate/state'
import { createGenerateComputed } from './generate/computed'
import { createProjectActions } from './generate/projectActions'
import { createTestPointActions } from './generate/testPointActions'
import { createUiPrototypeActions } from './generate/uiPrototypeActions'
import { createGenerateActions } from './generate/generateActions'
import { createCaseActions } from './generate/caseActions'
import { createSaveActions } from './generate/saveActions'
import { createEditActions } from './generate/editActions'
import type { StoreActions } from './generate/types'

export type {
  GeneratedStep,
  GeneratedCase,
  EditingCase,
  ContextPreview,
  GenerateFormData,
} from './generate/types'

export const useGenerateStore = defineStore('generate', () => {
  const state = createGenerateState()
  const comp = createGenerateComputed(state)

  let combinedActions: StoreActions = {} as StoreActions
  const getActions = (): StoreActions => combinedActions

  const projectActs = createProjectActions(state, getActions)
  const testPointActs = createTestPointActions(state)
  const uiPrototypeActs = createUiPrototypeActions(state, getActions)
  const saveActs = createSaveActions(state, comp)
  const caseActs = createCaseActions(state, comp, getActions)
  const generateActs = createGenerateActions(state, comp, getActions)
  const editActs = createEditActions(state, comp)

  combinedActions = {
    nextCaseId: state.nextCaseId,
    handleSourceFileChange: testPointActs.handleSourceFileChange,
    loadTestPoints: testPointActs.loadTestPoints,
    loadProjectFiles: projectActs.loadProjectFiles,
    loadUIPrototypeProjects: uiPrototypeActs.loadUIPrototypeProjects,
    loadProjectCases: projectActs.loadProjectCases,
    loadUIScreens: uiPrototypeActs.loadUIScreens,
    saveSingleCaseToDb: saveActs.saveSingleCaseToDb,
    handleRegenerateCase: caseActs.handleRegenerateCase,
  }

  return {
    currentStep: state.currentStep,
    generating: state.generating,
    saving: state.saving,
    progress: state.progress,
    progressText: state.progressText,
    errorMessage: state.errorMessage,
    errorSuggestions: state.errorSuggestions,
    projects: state.projects,
    projectsLoading: state.projectsLoading,
    projectsLoaded: state.projectsLoaded,
    requirementFiles: state.requirementFiles,
    uiFiles: state.uiFiles,
    testPoints: state.testPoints,
    uiPrototypeProjects: state.uiPrototypeProjects,
    selectedUiPrototypeProjectId: state.selectedUiPrototypeProjectId,
    selectedUiPrototypeProject: comp.selectedUiPrototypeProject,
    uiScreens: state.uiScreens,
    screenImageUrls: state.screenImageUrls,
    showParseWarning: state.showParseWarning,
    projectCases: state.projectCases,
    selectedHistoryCaseIds: state.selectedHistoryCaseIds,
    _historyCaseUserCleared: state._historyCaseUserCleared,
    isLoadingProjectCases: state.isLoadingProjectCases,
    testPointPage: state.testPointPage,
    testPointPageSize: state.testPointPageSize,
    testPointTotal: state.testPointTotal,
    testPointAllIds: state.testPointAllIds,
    testPointSelectKey: state.testPointSelectKey,
    isLoadingMore: state.isLoadingMore,
    testPointCache: state.testPointCache,
    contextPreview: state.contextPreview,
    lastContext: state.lastContext,
    generatedCases: state.generatedCases,
    currentCaseIndex: state.currentCaseIndex,
    isEditingResult: state.isEditingResult,
    editingCase: state.editingCase,
    selectedCaseIndices: state.selectedCaseIndices,
    allSelected: comp.allSelected,
    hasSelected: comp.hasSelected,
    selectedCount: comp.selectedCount,
    toggleCaseSelection: editActs.toggleCaseSelection,
    toggleSelectAll: editActs.toggleSelectAll,
    issueDialogVisible: state.issueDialogVisible,
    issueDialogValidation: state.issueDialogValidation,
    formData: state.formData,
    flowSortModuleInfo: comp.flowSortModuleInfo,
    screenPreviewStatusType: comp.screenPreviewStatusType,
    screenPreviewStatusText: comp.screenPreviewStatusText,
    viewingCase: comp.viewingCase,
    selectedTestPointsForDisplay: comp.selectedTestPointsForDisplay,
    contextQuality: comp.contextQuality,
    canGenerate: comp.canGenerate,
    generateButtonLabel: comp.generateButtonLabel,
    progressStatus: comp.progressStatus,
    getProjects: projectActs.getProjects,
    loadProjectFiles: projectActs.loadProjectFiles,
    loadTestPoints: testPointActs.loadTestPoints,
    handleSourceFileChange: testPointActs.handleSourceFileChange,
    selectAllTestPoints: testPointActs.selectAllTestPoints,
    deselectAllTestPoints: testPointActs.deselectAllTestPoints,
    addTestPoint: testPointActs.addTestPoint,
    removeTestPoint: testPointActs.removeTestPoint,
    getTestPointLabel: testPointActs.getTestPointLabel,
    selectCurrentPageAll: testPointActs.selectCurrentPageAll,
    goToTestPointPage: testPointActs.goToTestPointPage,
    loadProjectCases: projectActs.loadProjectCases,
    loadUIPrototypeProjects: uiPrototypeActs.loadUIPrototypeProjects,
    loadUIScreens: uiPrototypeActs.loadUIScreens,
    loadScreenImages: uiPrototypeActs.loadScreenImages,
    handleUIPrototypeProjectChange: uiPrototypeActs.handleUIPrototypeProjectChange,
    handleProjectChange: projectActs.handleProjectChange,
    handleProjectFocus: projectActs.handleProjectFocus,
    extractFileContent: projectActs.extractFileContent,
    nextStep: editActs.nextStep,
    prevStep: editActs.prevStep,
    skipToStep2: editActs.skipToStep2,
    handleCaseTypeChange: editActs.handleCaseTypeChange,
    handleGenerate: generateActs.handleGenerate,
    handleRegenerateCase: caseActs.handleRegenerateCase,
    handleDeleteCase: caseActs.handleDeleteCase,
    handleRegenerateSelected: caseActs.handleRegenerateSelected,
    handleDeleteSelected: caseActs.handleDeleteSelected,
    handleCancel: caseActs.handleCancel,
    handleSaveCase: saveActs.handleSaveCase,
    startEditResult: editActs.startEditResult,
    cancelEditResult: editActs.cancelEditResult,
    addEditStep: editActs.addEditStep,
    removeEditStep: editActs.removeEditStep,
    handleRetry: editActs.handleRetry,
    resetForm: editActs.resetForm,
    getPriorityType: editActs.getPriorityType,
    getSelectedTagType: editActs.getSelectedTagType,
    getTypeTagType: editActs.getTypeTagType,
    getTypeLabel: editActs.getTypeLabel,
    getPriorityTagType: editActs.getPriorityTagType,
    getPriorityLabel: editActs.getPriorityLabel,
    getDataTypeLabel: editActs.getDataTypeLabel,
    cleanExpectedResult: editActs.cleanExpectedResult,
    handleFlowSortUpdate: editActs.handleFlowSortUpdate,
    onIssueDialogConfirm: generateActs.onIssueDialogConfirm,
    onIssueDialogCancel: generateActs.onIssueDialogCancel,
    cleanupScreenImages: uiPrototypeActs.cleanupScreenImages,
    resetGenerateState: editActs.resetGenerateState,
  }
})
