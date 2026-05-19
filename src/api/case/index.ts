import { crudApi } from './crud'
import { batchApi } from './batch'
import { versionApi } from './version'
import { aiApi } from './ai'

export type {
  TestCase,
  TestCaseStep,
  TestCaseAIGenerate,
  TestCaseApiStep,
  TestCaseCreate,
  TestPointData,
  FlowMetaData,
  FlowNodeSubmitData,
  FlowEdgeSubmitData,
  FlowSortSubmitData,
  TestCaseAIEnhancedRequest,
  CaseQueryParams,
  CasePageResponse,
  TestCaseGenerateRequest,
  TestCaseListResponse,
  TestCaseListParams,
  ImportResult,
  StepUpdateData,
  TestCaseUpdateData,
  StepLocatorUpdateData,
  CaseVersionItem,
  CaseVersionDetail,
  CaseVersionPageResponse,
  CorrectionResponse,
  VerificationResponse,
  AIEnhancedGenerateResponse,
  BatchCreateRequest,
  BatchCreateResponse,
  LineageNode,
  LineageResponse,
  SupplementResponse,
  QualityAnalysisResult,
  QualityDimension,
  QualityOptimizationItem,
} from './types'

export const testCaseApi = {
  ...crudApi,
  ...batchApi,
  ...versionApi,
  ...aiApi,
}

export const caseApi: typeof testCaseApi = testCaseApi

export default testCaseApi
