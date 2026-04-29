// 测试用例类型定义

// 后端步骤JSON结构
interface StepJson {
  step_number?: number;
  action?: string;
  expected_result?: string;
  test_data?: Record<string, string | number | boolean | null>;
  [key: string]: string | number | boolean | null | undefined;
}

// 测试用例步骤
interface TestCaseStep {
  id?: number;
  step_number: number;
  action: string;
  expected_result: string;
  actual_result?: string;
  status?: 'pass' | 'fail' | 'pending';
}

// 测试用例
interface TestCase {
  id: number;
  case_no?: string;
  project_id?: number;
  requirement_file_id?: number;  // 关联需求文件ID
  name?: string;        // 兼容旧字段
  title: string;         // 后端实际字段
  module: string;        // 后端实际字段
  scene?: string;       // 兼容旧字段
  precondition?: string; // 前置条件
  steps?: TestCaseStep[];
  steps_json?: StepJson[];
  expected_result: string;
  actual_result?: string;
  status: 'pending' | 'running' | 'pass' | 'fail' | 'blocked';
  priority: number;      // 后端是 number: 1/2/3
  case_type?: string;    // 后端字段
  type?: string;         // 兼容旧字段
  tags?: string[];
  created_by?: number;
  updated_by?: number;
  created_at: string;
  updated_at?: string;
  generate_status?: number;  // AI生成状态：0生成中/1生成成功/2生成失败
  ai_generated?: number;  // 兼容旧字段
}

// 测试用例创建/更新请求
interface TestCaseCreate {
  project_id: number;
  case_no?: string;
  module?: string;
  title: string;
  name?: string;
  type?: string;
  scene?: string;
  precondition?: string;
  steps: TestCaseStep[];
  expected_result: string;
  priority: number;
  case_type?: string;
  generate_status?: number;
  tags?: string[];
}

// 测试用例执行请求
interface TestCaseExecute {
  case_id: number;
  steps: TestCaseStep[];
  actual_result?: string;
  status: 'pass' | 'fail';
}

// AI生成用例请求
interface TestCaseAIGenerate {
  scene: string;
  case_type: string;
}

// 分页查询参数
interface CaseQueryParams {
  project_id?: number;
  page?: number;
  page_size?: number;
  type?: string;
  status?: string;
  priority?: number;
  module?: string;
  keyword?: string;
}

// 分页响应
interface CasePageResponse {
  items: TestCase[];
  total: number;
  page: number;
  page_size: number;
}
