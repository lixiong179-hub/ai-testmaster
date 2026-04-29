/**
 * API 模块统一导出
 * 提供统一的 API 访问接口
 */

// 测试用例 API
export { testCaseApi, default as caseApi } from './case'
export type {
  TestCase,
  TestCaseStep,
  TestCaseCreate,
  TestCaseExecute,
  TestCaseAIEnhancedRequest,
  CaseQueryParams,
  CasePageResponse,
  TestCaseGenerateRequest,
  TestCaseListResponse,
  TestCaseRetryRequest,
  ImportResult
} from './case'

// 测试任务 API
export { default as testTaskApi, default as testTaskApiDefault } from './testTask'
export { TaskStatus, ExecutionStatus } from './testTask'

// 项目 API
export { ProjectAPI as projectApi, ProjectAPI } from './project'
export type {
  Project,
  ProjectCreateRequest,
  ProjectListResponse,
  ProjectDetailResponse,
  ProjectCreateResponse,
  ProjectDeleteResponse,
  WebEnvConfig,
  WebEnvConfigs,
  DeviceInfo,
  DeviceConfig,
  ProjectConfig,
  ProjectConfigResponse
} from './project'

// 报告 API
export { default as reportApi, default as reportApiDefault } from './report'
export type {
  Report,
  TestCaseResult,
  ReportListResponse
} from './report'

// 需求链接 API (模块暂未实现，注释导出)
// export { RequirementLinkAPI, default as requirementLinkApi } from './requirementLink'
// export type {
//   RequirementLink,
//   CreateRequirementLinkRequest,
//   UpdateRequirementLinkRequest,
//   FetchContentResponse,
//   TestCaseContext,
//   ValidateLinkResponse,
//   LinkType,
//   AuthType
// } from './requirementLink'

// 测试执行 API
export {
  startTestExecution,
  pauseTestExecution,
  resumeTestExecution,
  stopTestExecution,
  getExecutionStatus,
  getExecutionLogs,
  getStepScreenshot,
  getExecutionVideo,
  getVideoInfo,
  getReplaySession,
  startReplay,
  pauseReplay,
  resumeReplay,
  stopReplay,
  seekTo,
  setReplaySpeed,
  getVisibilityConfig,
  updateVisibilityConfig
} from './testExecution'

// 测试数据 API
export { testDataApi } from './testData'
export type {
  TestData,
  TestDataCreateRequest,
  TestDataUpdateRequest,
  StepTestDataResponse,
  GenerateStepDataResponse,
  AutoGenerateResponse
} from './testData'
export { DataType, GenerationRule, dataTypeOptions, generationRuleOptions } from './testData'

// 测试点 API
export { testPointApi } from './testPoint'
export type {
  TestPoint,
  TestPointAnalyzeRequest,
  TestPointListResponse,
  AnalysisProgress
} from './testPoint'

// 用例质量 API
export {
  analyzeCaseQuality,
  analyzeProjectQuality,
  getCaseQualityTrend,
  estimateCaseCost,
  optimizeCaseLocators,
  getProjectCostSummary,
  batchAnalyzeCases
} from './caseQuality'

// 批量定位器 API
export {
  batchLocatorApi,
  default as batchLocatorApiDefault,
  startBatchRecord,
  getBatchRecordStatus,
  getBatchRecordReport,
  cancelBatchRecord,
  listBatchTasks
} from './batchLocator'
export type {
  BatchRecordRequest,
  BatchRecordResponse,
  BatchRecordStatus,
  StepResult,
  BatchRecordReport,
  BatchTask
} from './batchLocator'

// 用例视图 API
export { testCaseViewApi, default as testCaseViewApiDefault } from './testCaseView'
export type {
  LocatorCoverage,
  LocatorInfo,
  TechnicalStep,
  TechnicalView,
  ViewStatistics
} from './testCaseView'

// 文件 API
export { fileApi, FileAPI, default } from './file'
export type {
  ProjectFile,
  UrlSubmitRequest,
  FileListResponse,
  FileUploadResponse,
  UrlSubmitResponse,
  FileDeleteResponse
} from './file'
