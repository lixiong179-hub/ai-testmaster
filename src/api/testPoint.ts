import request, { type ApiResponse } from '@/utils/request';

export interface TestPoint {
  id: number;
  project_id: number;
  module: string;
  function: string;
  point: string;
  priority: number;
  create_time: string | Date;
  ai_prompt?: string;
}

export interface TestPointAnalyzeRequest {
  project_id: number;
}

export interface TestPointListResponse {
  total: number;
  items: TestPoint[];
  page: number;
  page_size: number;
}

export interface AnalysisProgress {
  progress: number;
  message?: string;
  data?: TestPoint[];
}

export interface TestPointApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface UpdateTestPointData {
  id: number;
  project_id: number;
  module: string;
  function: string;
  point: string;
  priority: number;
  ai_prompt?: string | null;
  create_time: string;
}

export interface DeleteTestData {
  id: number;
}

export interface BatchDeleteData {
  deleted_count: number;
  requested_count: number;
}

export interface UpdateTestPointRequest {
  project_id: number;
  module: string;
  function?: string;
  point: string;
  priority?: number;
  ai_prompt?: string;
}

export interface TestPointDetailResponse {
  id: number;
  project_id: number;
  module: string;
  function: string;
  point: string;
  priority: number;
  ai_prompt?: string;
  create_time: string;
}

export const testPointApi = {
  analyze: async (data: TestPointAnalyzeRequest): Promise<AsyncGenerator<AnalysisProgress>> => {
    const response = await request.post('/api/v1/test-point/analyze', data, {
      responseType: 'stream'
    });

    return new Promise((resolve) => {
      const stream = response.data as ReadableStream;
      const reader = stream.getReader();

      const generator = (async function* () {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = new TextDecoder('utf-8').decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.trim()) {
              try {
                const progress: AnalysisProgress = JSON.parse(line);
                yield progress;
              } catch (e: unknown) {
                console.error('解析进度数据失败:', e instanceof Error ? e.message : String(e));
              }
            }
          }
        }
      })();

      resolve(generator);
    });
  },

  getList: async (projectId: number, params?: {
    module?: string;
    priority?: number;
    page?: number;
    page_size?: number;
  }): Promise<TestPointListResponse> => {
    const response = await request.get(`/api/v1/test-point/list/${projectId}`, { params });
    return (response as unknown as ApiResponse<TestPointListResponse>).data;
  },

  getDetail: async (testPointId: number, projectId?: number): Promise<TestPointDetailResponse> => {
    const url = projectId
      ? `/api/v1/test-point/detail/${testPointId}?project_id=${projectId}`
      : `/api/v1/test-point/detail/${testPointId}`;
    const response = await request.get(url);
    return response as unknown as TestPointDetailResponse;
  },

  update: async (
    testPointId: number,
    data: UpdateTestPointRequest
  ): Promise<TestPointApiResponse<UpdateTestPointData>> => {
    const response = await request.put(
      `/api/v1/test-point/${testPointId}`,
      data,
      { params: { project_id: data.project_id } }
    );
    return response as unknown as TestPointApiResponse<UpdateTestPointData>;
  },

  delete: async (
    testPointId: number,
    projectId: number
  ): Promise<TestPointApiResponse<DeleteTestData>> => {
    const response = await request.delete(
      `/api/v1/test-point/${testPointId}`,
      { params: { project_id: projectId } }
    );
    return response as unknown as TestPointApiResponse<DeleteTestData>;
  },

  batchDelete: async (
    projectId: number,
    ids: number[]
  ): Promise<TestPointApiResponse<BatchDeleteData>> => {
    const response = await request.delete(
      '/api/v1/test-point/batch',
      {
        params: { project_id: projectId },
        data: ids
      }
    );
    return response as unknown as TestPointApiResponse<BatchDeleteData>;
  }
};
