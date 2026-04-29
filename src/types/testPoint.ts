// 测试点类型定义
export interface TestPoint {
  id: number;
  project_id: number;
  module: string;
  function: string;
  point: string;
  priority: number;
  create_time: string;
  ai_prompt?: string;
}

export interface TestPointAnalyzeRequest {
  project_id: number;
}

export interface TestPointListResponse {
  code: number;
  msg: string;
  data: {
    test_points: TestPoint[];
  };
}

export interface AnalysisProgress {
  progress: number;
  message?: string;
  data?: TestPoint[];
}
