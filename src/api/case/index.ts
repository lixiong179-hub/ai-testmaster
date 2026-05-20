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
  TestCaseExecute,
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
  TestCaseRetryRequest,
  ImportResult,
  StepUpdateData,
  TestCaseUpdateData,
  StepLocatorUpdateData,
  CaseVersionItem,
  CaseVersionDetail,
  CaseVersionCompareResult,
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
} from './types'

export const testCaseApi = {
  ...crudApi,
  ...batchApi,
  ...versionApi,
  ...aiApi,
}

export const caseApi: typeof testCaseApi = testCaseApi

export default testCaseApi
