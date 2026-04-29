import axios from '@/utils/request';

// 测试数据API封装
export const testDataApi = {
  // 创建测试数据
  create: async (data: TestDataCreateRequest): Promise<TestData> => {
    const response = await axios.post('/api/v1/test-data', data);
    return response.data;
  },

  // 获取测试数据详情
  getById: async (id: number): Promise<TestData> => {
    const response = await axios.get(`/api/v1/test-data/${id}`);
    return response.data;
  },

  // 获取步骤的所有测试数据
  getByStepId: async (stepId: number): Promise<StepTestDataResponse> => {
    const response = await axios.get(`/api/v1/test-data/step/${stepId}`);
    return response.data;
  },

  // 更新测试数据
  update: async (id: number, data: TestDataUpdateRequest): Promise<TestData> => {
    const response = await axios.put(`/api/v1/test-data/${id}`, data);
    return response.data;
  },

  // 删除测试数据
  delete: async (id: number): Promise<{ success: boolean; message: string }> => {
    const response = await axios.delete(`/api/v1/test-data/${id}`);
    return response.data;
  },

  // 生成步骤的测试数据
  generate: async (stepId: number): Promise<GenerateStepDataResponse> => {
    const response = await axios.post(`/api/v1/test-data/step/${stepId}/generate`);
    return response.data;
  },

  // 根据操作描述自动推断生成测试数据
  autoGenerate: async (stepId: number, actionDescription: string): Promise<AutoGenerateResponse> => {
    const response = await axios.post(`/api/v1/test-data/step/${stepId}/auto-generate`, null, {
      params: { action_description: actionDescription }
    });
    return response.data;
  }
};

// 数据类型枚举
export enum DataType {
  TEXT = 'text',
  EMAIL = 'email',
  PHONE = 'phone',
  NUMBER = 'number',
  DATE = 'date',
  DATETIME = 'datetime',
  BOOLEAN = 'boolean',
  URL = 'url',
  USERNAME = 'username',
  PASSWORD = 'password',
  ID_CARD = 'id_card',
  ENUM = 'enum'
}

// 生成规则枚举
export enum GenerationRule {
  RANDOM = 'random',
  FIXED = 'fixed',
  BOUNDARY = 'boundary',
  SPECIAL_CHARS = 'special_chars',
  CUSTOM = 'custom'
}

// 测试数据类型定义
export interface TestData {
  id: number;
  step_id: number;
  field_name: string;
  field_type: string;
  data_value: string | null;
  generation_rule: string;
  rule_config: Record<string, string | number | boolean | null> | null;
  min_length: number | null;
  max_length: number | null;
  min_value: number | null;
  max_value: number | null;
  enum_values: string[] | null;
  description: string | null;
  is_required: boolean;
  sort_order: number;
}

// 创建请求
export interface TestDataCreateRequest {
  step_id: number;
  field_name: string;
  field_type: DataType;
  generation_rule?: GenerationRule;
  data_value?: string;
  rule_config?: Record<string, string | number | boolean | null>;
  min_length?: number;
  max_length?: number;
  min_value?: number;
  max_value?: number;
  enum_values?: string[];
  description?: string;
  is_required?: boolean;
  sort_order?: number;
}

// 更新请求
export interface TestDataUpdateRequest {
  field_name?: string;
  field_type?: DataType;
  generation_rule?: GenerationRule;
  data_value?: string;
  rule_config?: Record<string, string | number | boolean | null>;
  min_length?: number;
  max_length?: number;
  min_value?: number;
  max_value?: number;
  enum_values?: string[];
  description?: string;
  is_required?: boolean;
  sort_order?: number;
}

// 步骤测试数据响应
export interface StepTestDataResponse {
  step_id: number;
  data_list: TestData[];
}

// 生成步骤数据响应
export interface GenerateStepDataResponse {
  step_id: number;
  generated_data: Record<string, string | number | boolean | null>;
}

// 自动生成响应
export interface AutoGenerateResponse {
  success: boolean;
  count: number;
  data_list: TestData[];
}

// 数据类型选项
export const dataTypeOptions = [
  { label: '文本', value: DataType.TEXT },
  { label: '邮箱', value: DataType.EMAIL },
  { label: '手机号', value: DataType.PHONE },
  { label: '数字', value: DataType.NUMBER },
  { label: '日期', value: DataType.DATE },
  { label: '日期时间', value: DataType.DATETIME },
  { label: '布尔值', value: DataType.BOOLEAN },
  { label: 'URL', value: DataType.URL },
  { label: '用户名', value: DataType.USERNAME },
  { label: '密码', value: DataType.PASSWORD },
  { label: '身份证号', value: DataType.ID_CARD }
];

// 生成规则选项
export const generationRuleOptions = [
  { label: '随机生成', value: GenerationRule.RANDOM },
  { label: '固定值', value: GenerationRule.FIXED },
  { label: '边界值', value: GenerationRule.BOUNDARY },
  { label: '特殊字符', value: GenerationRule.SPECIAL_CHARS },
  { label: '自定义', value: GenerationRule.CUSTOM }
];
