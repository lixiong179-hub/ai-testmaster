/**
 * API 模块统一导出
 * 提供统一的 API 访问接口
 */

// 认证 API
export { authApi } from './auth'
export type { CaptchaResponse, LoginResponse, UserInfo } from './auth'

// 用户管理 API
export { userApi } from './user'

// 测试用例 API
export { testCaseApi, default as caseApi } from './case'
export type {
  TestCase,
  TestCaseStep,
  TestCaseCreate,
  TestCaseAIEnhancedRequest,
  CaseQueryParams,
  CasePageResponse,
  TestCaseListResponse,
  ImportResult,
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
  ProjectConfigResponse,
} from './project'

// 报告 API
export { default as reportApi, default as reportApiDefault } from './report'
export type { Report, TestCaseResult, ReportListResponse } from './report'

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
  updateVisibilityConfig,
} from './testExecution'

// 测试数据 API
export { testDataApi } from './testData'
export type {
  TestData,
  TestDataCreateRequest,
  TestDataUpdateRequest,
  StepTestDataResponse,
  GenerateStepDataResponse,
  AutoGenerateResponse,
} from './testData'
export { DataType, GenerationRule, dataTypeOptions, generationRuleOptions } from './testData'

// 测试点 API
export { testPointApi } from './testPoint'
export type {
  TestPoint,
  TestPointAnalyzeRequest,
  TestPointDraft,
  TestPointListResponse,
  AnalysisProgress,
} from './testPoint'

// 用例质量 API
export {
  analyzeCaseQuality,
  getCaseQualityTrend,
  estimateCaseCost,
  optimizeCaseLocators,
  getProjectCostSummary,
  batchAnalyzeCases,
} from './caseQuality'

// 批量定位器 API
export {
  batchLocatorApi,
  default as batchLocatorApiDefault,
  startBatchRecord,
  getBatchRecordStatus,
  getBatchRecordReport,
  cancelBatchRecord,
  listBatchTasks,
} from './batchLocator'
export type {
  BatchRecordRequest,
  BatchRecordResponse,
  BatchRecordStatus,
  StepResult,
  BatchRecordReport,
  BatchTask,
} from './batchLocator'

// 用例视图 API
export { testCaseViewApi, default as testCaseViewApiDefault } from './testCaseView'
export type {
  LocatorCoverage,
  LocatorInfo,
  TechnicalStep,
  TechnicalView,
  ViewStatistics,
} from './testCaseView'

// Pipeline API
export { pipelineApi } from './pipeline'
export type {
  PipelineRun,
  PipelineStep,
  PipelineArtifact,
  PipelineRunStatus,
  PipelineStepStatus,
  PipelineRunRequest,
  PipelineResumeRequest,
  PipelineRunResponse,
} from './pipeline'

// 评审 API
export { reviewApi } from './review'
export type {
  ReviewDecision,
  DecideRequest,
  BatchDecideItem,
  BatchDecideRequest,
  DecisionListResponse,
  FinalizeResponse,
} from './review'

// 文件 API
export { fileApi, FileAPI, default } from './file'
export type {
  ApiResponse,
  ProjectFile,
  UrlSubmitRequest,
  FileListData,
  FileListResponse,
  FileUploadResultData,
  FileUploadResponse,
  UrlSubmitResponse,
  FileBatchUploadData,
  FileBatchUploadResponse,
  FileDeleteResponse,
  FileUpdateRequest,
  FileUpdateResponse,
} from './file'

// 测试能力 API
export { testCapabilityApi } from './testCapability'
export type {
  TestCapabilityResponse,
  TestCapabilityCreateRequest,
  TestCapabilityUpdateRequest,
  TestCapabilityListParams,
} from './testCapability'

// 审计日志 API
export { default as auditLogApi } from './auditLog'
export type { AuditLogItem, AuditLogListResponse, AuditLogQueryParams } from './auditLog'
