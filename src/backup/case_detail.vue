<template>
  <div class="case-detail-container">
    <!-- 页面标题和操作栏 -->
    <div class="page-header">
      <h2>{{ isEditMode ? '编辑测试用例' : '测试用例详情' }}</h2>
      <div class="header-actions">
        <el-button v-if="!isEditMode" type="primary" @click="handleEdit">
          <el-icon><Edit /></el-icon>
          编辑
        </el-button>
        <el-button v-if="!isEditMode" @click="handleExecute">
          <el-icon><Switch /></el-icon>
          执行
        </el-button>
        <el-button v-if="isEditMode" type="primary" @click="handleSave" :loading="saving">
          <el-icon><Check /></el-icon>
          保存
        </el-button>
        <el-button @click="handleBack">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
      </div>
    </div>

    <!-- 基本信息 -->
    <el-card class="info-card">
      <el-form :model="caseForm" label-width="120px" v-if="isEditMode">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="用例名称" required>
              <el-input v-model="caseForm.name" placeholder="请输入用例名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="用例类型" required>
              <el-select v-model="caseForm.type" placeholder="请选择用例类型">
                <el-option label="UI自动化" value="ui_automation" />
                <el-option label="手工测试" value="manual" />
                <el-option label="API自动化" value="api_automation" />
                <el-option label="性能测试" value="performance" />
                <el-option label="安全测试" value="security" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="优先级" required>
              <el-select v-model="caseForm.priority" placeholder="请选择优先级">
                <el-option label="低" value="low" />
                <el-option label="中" value="medium" />
                <el-option label="高" value="high" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属模块">
              <el-input v-model="caseForm.module" placeholder="请输入所属模块" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="测试场景" required>
          <el-input
            v-model="caseForm.scene"
            type="textarea"
            :rows="3"
            placeholder="请输入测试场景描述"
          />
        </el-form-item>
        <el-form-item label="预期结果" required>
          <el-input
            v-model="caseForm.expected_result"
            type="textarea"
            :rows="3"
            placeholder="请输入预期结果"
          />
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="caseForm.tags"
            multiple
            placeholder="请选择标签"
            style="width: 100%"
          >
            <el-option v-for="tag in tagOptions" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <template v-else>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="用例名称">{{ caseDetail.name }}</el-descriptions-item>
          <el-descriptions-item label="用例类型">
            <el-tag :type="getTypeTagType(caseDetail.type)">
              {{ getTypeLabel(caseDetail.type) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="getPriorityTagType(caseDetail.priority)">
              {{ getPriorityLabel(caseDetail.priority) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="所属模块">{{ caseDetail.module || '-' }}</el-descriptions-item>
          <el-descriptions-item label="测试场景" :span="2">{{ caseDetail.scene }}</el-descriptions-item>
          <el-descriptions-item label="预期结果" :span="2">{{ caseDetail.expected_result }}</el-descriptions-item>
          <el-descriptions-item label="标签" :span="2">
            <el-tag v-for="tag in (caseDetail.tags || [])" :key="tag" size="small" style="margin-right: 8px;">
              {{ tag }}
            </el-tag>
            <span v-if="caseDetail.tags.length === 0">-</span>
          </el-descriptions-item>
          <el-descriptions-item label="AI生成">
            <el-tag v-if="caseDetail.ai_generated" type="info">是</el-tag>
            <el-tag v-else type="info">否</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ caseDetail.created_at }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ caseDetail.updated_at }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTagType(caseDetail.status)">
              {{ getStatusLabel(caseDetail.status) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-card>

    <!-- 测试步骤 -->
    <el-card class="steps-card" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>测试步骤</span>
          <el-button v-if="isEditMode" type="primary" size="small" @click="addStep">
            <el-icon><Plus /></el-icon>
            添加步骤
          </el-button>
        </div>
      </template>
      
      <div v-if="isEditMode">
        <el-table
          v-model:data="caseForm.steps"
          style="width: 100%"
          border
        >
          <el-table-column label="步骤" width="80">
            <template #default="{ $index }">
              {{ $index + 1 }}
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="300">
            <template #default="{ row }">
              <el-input
                v-model="row.action"
                type="textarea"
                :rows="2"
                placeholder="请输入操作步骤"
              />
            </template>
          </el-table-column>
          <el-table-column label="预期结果" min-width="300">
            <template #default="{ row }">
              <el-input
                v-model="row.expected_result"
                type="textarea"
                :rows="2"
                placeholder="请输入预期结果"
              />
            </template>
          </el-table-column>
          <el-table-column label="测试数据" width="120">
            <template #default="{ row, $index }">
              <el-button
                type="info"
                size="small"
                @click="openTestDataDialog(row, $index)"
              >
                <el-icon><DataLine /></el-icon>
                数据
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ $index }">
              <el-button
                type="danger"
                size="small"
                @click="removeStep($index)"
                :disabled="caseForm.steps.length <= 1"
              >
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      
      <div v-else>
        <el-timeline>
          <el-timeline-item
            v-for="(step, index) in caseDetail.steps"
            :key="index"
            :timestamp="`步骤 ${Number(index) + 1}`"
            placement="top"
          >
            <el-card>
              <h4>操作</h4>
              <p>{{ step.action }}</p>
              <h4 style="margin-top: 10px;">预期结果</h4>
              <p>{{ step.expected_result }}</p>
              <div v-if="step.status" style="margin-top: 10px;">
                <el-tag :type="step.status === 'pass' ? 'success' : 'danger'">
                  {{ step.status === 'pass' ? '通过' : '失败' }}
                </el-tag>
                <p v-if="step.actual_result" style="margin-top: 5px; color: #606266;">
                  实际结果: {{ step.actual_result }}
                </p>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <div v-if="(caseDetail.steps || []).length === 0" class="empty-steps">
          <el-empty description="暂无测试步骤" />
        </div>
      </div>
    </el-card>

    <!-- 执行结果 -->
    <el-card v-if="!isEditMode && caseDetail.actual_result" class="result-card" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>执行结果</span>
        </div>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="实际结果">{{ caseDetail.actual_result }}</el-descriptions-item>
        <el-descriptions-item label="执行状态">
          <el-tag :type="caseDetail.status === 'pass' ? 'success' : 'danger'">
            {{ getStatusLabel(caseDetail.status) }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 测试数据管理对话框 -->
    <el-dialog
      v-model="testDataDialogVisible"
      :title="`步骤 ${currentStepIndex + 1} - 测试数据管理`"
      width="900px"
    >
      <div v-loading="testDataLoading">
        <!-- 测试数据列表 -->
        <el-table :data="testDataList" style="width: 100%; margin-bottom: 20px;" border>
          <el-table-column label="字段名" prop="field_name" width="150" />
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ getFieldTypeLabel(row.field_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="生成规则" width="120">
            <template #default="{ row }">
              {{ getGenerationRuleLabel(row.generation_rule) }}
            </template>
          </el-table-column>
          <el-table-column label="数据值" prop="data_value" min-width="150" show-overflow-tooltip />
          <el-table-column label="必填" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_required ? 'danger' : 'info'" size="small">
                {{ row.is_required ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" size="small" @click="editTestData(row)">编辑</el-button>
              <el-button type="danger" size="small" @click="deleteTestData(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 添加/编辑测试数据表单 -->
        <el-divider content-position="left">{{ editingTestDataId ? '编辑测试数据' : '添加测试数据' }}</el-divider>
        
        <el-form :model="testDataForm" label-width="100px">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="字段名" required>
                <el-input v-model="testDataForm.field_name" placeholder="例如：username" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="字段类型" required>
                <el-select v-model="testDataForm.field_type" style="width: 100%">
                  <el-option label="文本" value="text" />
                  <el-option label="数字" value="number" />
                  <el-option label="邮箱" value="email" />
                  <el-option label="手机号" value="phone" />
                  <el-option label="日期" value="date" />
                  <el-option label="日期时间" value="datetime" />
                  <el-option label="枚举" value="enum" />
                  <el-option label="布尔值" value="boolean" />
                  <el-option label="URL" value="url" />
                  <el-option label="身份证号" value="id_card" />
                  <el-option label="银行卡号" value="bank_card" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="生成规则" required>
                <el-select v-model="testDataForm.generation_rule" style="width: 100%">
                  <el-option label="随机生成" value="random" />
                  <el-option label="固定值" value="fixed" />
                  <el-option label="边界最小值" value="boundary_min" />
                  <el-option label="边界最大值" value="boundary_max" />
                  <el-option label="边界超长值" value="boundary_over" />
                  <el-option label="特殊字符" value="special_chars" />
                  <el-option label="空值" value="empty" />
                  <el-option label="自定义" value="custom" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="是否必填">
                <el-switch v-model="testDataForm.is_required" active-text="是" inactive-text="否" />
              </el-form-item>
            </el-col>
          </el-row>
          
          <!-- 固定值或自定义规则时显示数据值输入 -->
          <el-form-item 
            v-if="testDataForm.generation_rule === 'fixed' || testDataForm.generation_rule === 'custom'" 
            label="数据值"
          >
            <el-input v-model="testDataForm.data_value" placeholder="请输入固定值" />
          </el-form-item>
          
          <!-- 文本类型显示长度限制 -->
          <el-row :gutter="20" v-if="testDataForm.field_type === DataType.TEXT">
            <el-col :span="12">
              <el-form-item label="最小长度">
                <el-input-number v-model="testDataForm.min_length" :min="0" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="最大长度">
                <el-input-number v-model="testDataForm.max_length" :min="0" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
          
          <!-- 数字类型显示数值范围 -->
          <el-row :gutter="20" v-if="testDataForm.field_type === DataType.NUMBER">
            <el-col :span="12">
              <el-form-item label="最小值">
                <el-input-number v-model="testDataForm.min_value" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="最大值">
                <el-input-number v-model="testDataForm.max_value" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
          
          <!-- 枚举类型显示枚举值 -->
          <el-form-item v-if="testDataForm.field_type === DataType.ENUM" label="枚举值">
            <el-select
              v-model="testDataForm.enum_values"
              multiple
              filterable
              allow-create
              placeholder="请输入枚举值，按回车确认"
              style="width: 100%"
            />
          </el-form-item>
          
          <el-form-item label="描述">
            <el-input 
              v-model="testDataForm.description" 
              type="textarea" 
              :rows="2" 
              placeholder="请输入字段描述"
            />
          </el-form-item>
        </el-form>
      </div>
      
      <template #footer>
        <div style="display: flex; justify-content: space-between;">
          <div>
            <el-button type="success" @click="autoGenerateTestData" :loading="generatingTestData">
              <el-icon><MagicStick /></el-icon>
              自动推断
            </el-button>
            <el-button type="warning" @click="generateTestDataValues">
              <el-icon><RefreshRight /></el-icon>
              生成数据
            </el-button>
          </div>
          <div>
            <el-button @click="resetTestDataForm">重置</el-button>
            <el-button type="primary" @click="saveTestData">保存</el-button>
            <el-button @click="testDataDialogVisible = false">关闭</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 执行对话框 -->
    <el-dialog
      v-model="executeDialogVisible"
      title="执行测试用例"
      width="800px"
    >
      <el-table
        v-model:data="executeSteps"
        style="width: 100%"
        border
      >
        <el-table-column label="步骤" width="80">
          <template #default="{ $index }">
            {{ $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="250">
          <template #default="{ row }">
            <el-input
              v-model="row.action"
              type="textarea"
              :rows="2"
              disabled
            />
          </template>
        </el-table-column>
        <el-table-column label="预期结果" min-width="250">
          <template #default="{ row }">
            <el-input
              v-model="row.expected_result"
              type="textarea"
              :rows="2"
              disabled
            />
          </template>
        </el-table-column>
        <el-table-column label="实际结果" min-width="250">
          <template #default="{ row }">
            <el-input
              v-model="row.actual_result"
              type="textarea"
              :rows="2"
              placeholder="请输入实际结果"
            />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-select v-model="row.status" placeholder="请选择">
              <el-option label="通过" value="pass" />
              <el-option label="失败" value="fail" />
            </el-select>
          </template>
        </el-table-column>
      </el-table>
      
      <el-form :model="executeForm" label-width="80px" style="margin-top: 20px;">
        <el-form-item label="执行结果">
          <el-input
            v-model="executeForm.actual_result"
            type="textarea"
            :rows="3"
            placeholder="请输入整体执行结果"
          />
        </el-form-item>
        <el-form-item label="执行状态">
          <el-select v-model="executeForm.status" placeholder="请选择">
            <el-option label="通过" value="pass" />
            <el-option label="失败" value="fail" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="executeDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleExecuteConfirm" :loading="executing">
            确认执行
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import caseApi from '@/api/case';
import testTaskApi from '@/api/testTask';
import { testDataApi, type TestData, type TestDataCreateRequest, DataType, GenerationRule } from '@/api/testData';
// 类型从全局 case.d.ts 声明文件获取，无需显式导入
import { Edit, Switch, Check, ArrowLeft, Plus, Delete, DataLine, RefreshRight, MagicStick } from '@element-plus/icons-vue';

const router = useRouter();
const route = useRoute();

// 状态管理
const caseDetail = ref<any>({
  id: 0,
  name: '',
  type: '',
  scene: '',
  steps: [],
  expected_result: '',
  status: 'pending',
  priority: 'medium',
  tags: [],
  created_at: '',
  updated_at: '',
  ai_generated: 0
});

const caseForm = reactive<any>({
  name: '',
  type: 'ui_automation',
  scene: '',
  steps: [{
    step_number: 1,
    action: '',
    expected_result: ''
  }],
  expected_result: '',
  priority: 'medium',
  tags: []
});

const executeSteps = ref<any[]>([]);
const executeForm = reactive({
  actual_result: '',
  status: 'pass' as 'pass' | 'fail'
});

const loading = ref(false);
const saving = ref(false);
const executing = ref(false);
const executeDialogVisible = ref(false);

// 测试数据管理
const testDataDialogVisible = ref(false);
const testDataLoading = ref(false);
const currentStepId = ref<number | null>(null);
const currentStepIndex = ref<number>(0);
const testDataList = ref<TestData[]>([]);
const testDataForm = reactive<TestDataCreateRequest>({
  step_id: 0,
  field_name: '',
  field_type: DataType.TEXT,
  generation_rule: GenerationRule.RANDOM,
  data_value: '',
  rule_config: undefined,
  min_length: undefined,
  max_length: undefined,
  min_value: undefined,
  max_value: undefined,
  enum_values: [],
  description: '',
  is_required: true,
  sort_order: 0
});
const editingTestDataId = ref<number | null>(null);
const generatingTestData = ref(false);

// 标签选项
const tagOptions = [
  '冒烟测试', '回归测试', '集成测试', '系统测试',
  '边界值', '等价类', '路径覆盖', '性能测试',
  '安全测试', '兼容性测试'
];

// 计算属性
const caseId = computed(() => route.query.id as string);
const isEditMode = computed(() => route.query.mode === 'edit' || !caseId.value);

// 初始化
onMounted(() => {
  if (caseId.value) {
    fetchCaseDetail();
  }
});

// 监听编辑模式变化
watch(isEditMode, (newVal) => {
  if (newVal && caseId.value) {
    // 切换到编辑模式时，同步表单数据
    syncFormData();
  }
});

// 获取测试用例详情
const fetchCaseDetail = async () => {
  if (!caseId.value) return;
  
  loading.value = true;
  try {
    const caseData = await caseApi.getCase(Number(caseId.value));
    caseDetail.value = caseData;
    
    // 如果是编辑模式，同步表单数据
    if (isEditMode.value) {
      syncFormData();
    }
  } catch (error) {
    ElMessage.error('获取测试用例详情失败');
  } finally {
    loading.value = false;
  }
};

// 同步表单数据
const syncFormData = () => {
  caseForm.name = caseDetail.value.name;
  caseForm.type = caseDetail.value.type;
  caseForm.scene = caseDetail.value.scene;
  caseForm.steps = JSON.parse(JSON.stringify(caseDetail.value.steps));
  caseForm.expected_result = caseDetail.value.expected_result;
  caseForm.priority = caseDetail.value.priority;
  caseForm.tags = [...caseDetail.value.tags];
  caseForm.module = caseDetail.value.module;
};

// 添加步骤
const addStep = () => {
  caseForm.steps.push({
    step_number: caseForm.steps.length + 1,
    action: '',
    expected_result: ''
  });
};

// 删除步骤
const removeStep = (index: number) => {
  caseForm.steps.splice(index, 1);
  // 重新编号
  caseForm.steps.forEach((step: TestCaseStep, i: number) => {
    step.step_number = i + 1;
  });
};

// 保存测试用例
const handleSave = async () => {
  // 验证表单
  if (!caseForm.name || !caseForm.scene || !caseForm.expected_result) {
    ElMessage.warning('请填写必填字段');
    return;
  }
  
  if (caseForm.steps.length === 0) {
    ElMessage.warning('请添加测试步骤');
    return;
  }
  
  saving.value = true;
  try {
    if (caseId.value) {
      // 更新
      await caseApi.updateCase(Number(caseId.value), caseForm);
      ElMessage.success('更新成功');
    } else {
      // 创建
      await caseApi.createCase(caseForm);
      ElMessage.success('创建成功');
    }
    router.push('/case');
  } catch (error) {
    ElMessage.error('保存失败');
  } finally {
    saving.value = false;
  }
};

// 编辑
const handleEdit = () => {
  router.push(`/case/detail?id=${caseId.value}&mode=edit`);
};

// 执行测试用例
const handleExecute = () => {
  executeSteps.value = JSON.parse(JSON.stringify(caseDetail.value.steps));
  executeForm.actual_result = '';
  executeForm.status = 'pass';
  executeDialogVisible.value = true;
};

// 确认执行
const handleExecuteConfirm = async () => {
  // 验证执行数据
  const allStepsHaveStatus = executeSteps.value.every(step => step.status);
  if (!allStepsHaveStatus) {
    ElMessage.warning('请为所有步骤设置执行状态');
    return;
  }
  
  executing.value = true;
  try {
    // 后端无独立execute端点，通过创建任务执行
    const projectId = caseDetail.value?.project_id
    if (projectId) {
      await testTaskApi.createTask({
        task_name: `执行用例-${caseDetail.value?.title || caseId.value}`,
        project_id: projectId,
        case_ids: [Number(caseId.value)],
      })
    }
    ElMessage.success('执行任务已创建');
    executeDialogVisible.value = false;
    fetchCaseDetail();
  } catch (error) {
    ElMessage.error('执行失败');
  } finally {
    executing.value = false;
  }
};

// 返回
const handleBack = () => {
  router.push('/case');
};

// 辅助方法
const getTypeTagType = (type: string) => {
  const typeMap: Record<string, string> = {
    'ui_automation': 'success',
    'manual': 'info',
    'api_automation': '',
    'performance': 'warning',
    'security': 'danger',
    'UI': 'success',
    'API': '',
    'functional': 'info',
  };
  return typeMap[type] || 'info';
};

const getTypeLabel = (type: string) => {
  const typeMap: Record<string, string> = {
    'ui_automation': 'UI自动化',
    'manual': '手工测试',
    'api_automation': 'API自动化',
    'performance': '性能测试',
    'security': '安全测试',
    'UI': 'UI自动化',
    'API': 'API自动化',
    'functional': '手工测试',
  };
  return typeMap[type] || type;
};

const getStatusTagType = (status: string) => {
  const statusMap: Record<string, string> = {
    pending: 'info',
    running: 'warning',
    pass: 'success',
    fail: 'danger',
    blocked: 'info'
  };
  return statusMap[status] || 'info';
};

const getStatusLabel = (status: string) => {
  const statusMap: Record<string, string> = {
    pending: '待执行',
    running: '执行中',
    pass: '通过',
    fail: '失败',
    blocked: '阻塞'
  };
  return statusMap[status] || status;
};

const getPriorityTagType = (priority: string) => {
  const priorityMap: Record<string, string> = {
    low: 'info',
    medium: 'warning',
    high: 'danger'
  };
  return priorityMap[priority] || 'info';
};

const getPriorityLabel = (priority: string) => {
  const priorityMap: Record<string, string> = {
    low: '低',
    medium: '中',
    high: '高'
  };
  return priorityMap[priority] || priority;
};

// ==================== 测试数据管理方法 ====================

// 打开测试数据对话框
const openTestDataDialog = async (step: any, index: number) => {
  currentStepId.value = step.id || null;
  currentStepIndex.value = index;
  testDataDialogVisible.value = true;
  
  if (step.id) {
    await fetchTestDataList(step.id);
  } else {
    testDataList.value = [];
    ElMessage.warning('请先保存用例以获取步骤ID');
  }
};

// 获取测试数据列表
const fetchTestDataList = async (stepId: number) => {
  testDataLoading.value = true;
  try {
    const response = await testDataApi.getByStepId(stepId);
    testDataList.value = response.data_list || [];
  } catch (error) {
    ElMessage.error('获取测试数据失败');
    testDataList.value = [];
  } finally {
    testDataLoading.value = false;
  }
};

// 保存测试数据
const saveTestData = async () => {
  if (!testDataForm.field_name || !testDataForm.field_type) {
    ElMessage.warning('请填写必填字段');
    return;
  }
  
  if (!currentStepId.value) {
    ElMessage.error('步骤ID不存在');
    return;
  }
  
  try {
    if (editingTestDataId.value) {
      // 更新
      await testDataApi.update(editingTestDataId.value, testDataForm);
      ElMessage.success('更新成功');
    } else {
      // 创建
      await testDataApi.create({
        ...testDataForm,
        step_id: currentStepId.value
      });
      ElMessage.success('创建成功');
    }
    
    // 刷新列表
    if (currentStepId.value) {
      await fetchTestDataList(currentStepId.value);
    }
    resetTestDataForm();
  } catch (error) {
    ElMessage.error('保存失败');
  }
};

// 编辑测试数据
const editTestData = (row: TestData) => {
  editingTestDataId.value = row.id;
  Object.assign(testDataForm, {
    field_name: row.field_name,
    field_type: row.field_type,
    generation_rule: row.generation_rule,
    data_value: row.data_value || '',
    rule_config: row.rule_config,
    min_length: row.min_length,
    max_length: row.max_length,
    min_value: row.min_value,
    max_value: row.max_value,
    enum_values: row.enum_values || [],
    description: row.description || '',
    is_required: row.is_required,
    sort_order: row.sort_order
  });
};

// 删除测试数据
const deleteTestData = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要删除这条测试数据吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
    
    await testDataApi.delete(id);
    ElMessage.success('删除成功');
    
    if (currentStepId.value) {
      await fetchTestDataList(currentStepId.value);
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败');
    }
  }
};

// 重置测试数据表单
const resetTestDataForm = () => {
  editingTestDataId.value = null;
  Object.assign(testDataForm, {
    step_id: currentStepId.value || 0,
    field_name: '',
    field_type: DataType.TEXT,
    generation_rule: GenerationRule.RANDOM,
    data_value: '',
    rule_config: undefined,
    min_length: undefined,
    max_length: undefined,
    min_value: undefined,
    max_value: undefined,
    enum_values: [],
    description: '',
    is_required: true,
    sort_order: 0
  });
};

// 自动生成测试数据
const autoGenerateTestData = async () => {
  if (!currentStepId.value) {
    ElMessage.error('步骤ID不存在');
    return;
  }
  
  generatingTestData.value = true;
  try {
    // 获取当前步骤的操作描述
    const step = (caseForm.steps as any[])[currentStepIndex.value];
    if (!step || !step.action) {
      ElMessage.warning('步骤操作描述为空，无法自动推断');
      return;
    }
    
    await testDataApi.autoGenerate(currentStepId.value, step.action);
    ElMessage.success('自动推断完成');
    await fetchTestDataList(currentStepId.value);
  } catch (error) {
    ElMessage.error('自动推断失败');
  } finally {
    generatingTestData.value = false;
  }
};

// 生成测试数据值
const generateTestDataValues = async () => {
  if (!currentStepId.value) {
    ElMessage.error('步骤ID不存在');
    return;
  }
  
  try {
    const response = await testDataApi.generate(currentStepId.value);
    const generatedData = response.generated_data || {};
    
    // 更新列表中的数据值
    testDataList.value = testDataList.value.map((item: TestData) => {
      if (generatedData[item.field_name]) {
        return { ...item, data_value: generatedData[item.field_name] } as TestData;
      }
      return item;
    });
    
    ElMessage.success('数据生成完成');
  } catch (error) {
    ElMessage.error('数据生成失败');
  }
};

// 获取字段类型标签
const getFieldTypeLabel = (type: string): string => {
  const typeMap: Record<string, string> = {
    text: '文本',
    number: '数字',
    email: '邮箱',
    phone: '手机号',
    date: '日期',
    datetime: '日期时间',
    enum: '枚举',
    boolean: '布尔值',
    url: 'URL',
    id_card: '身份证',
    bank_card: '银行卡'
  };
  return typeMap[type] || type;
};

// 获取生成规则标签
const getGenerationRuleLabel = (rule: string): string => {
  const ruleMap: Record<string, string> = {
    random: '随机生成',
    fixed: '固定值',
    boundary_min: '边界最小',
    boundary_max: '边界最大',
    boundary_over: '边界超长',
    special_chars: '特殊字符',
    empty: '空值',
    custom: '自定义'
  };
  return ruleMap[rule] || rule;
};

// 本地缓存（防止刷新丢失）
if (isEditMode.value) {
  // 监听表单变化，保存到本地存储
  watch(caseForm, (newValue) => {
    localStorage.setItem('caseForm', JSON.stringify(newValue));
  }, { deep: true });
  
  // 页面加载时从本地存储恢复
  const savedForm = localStorage.getItem('caseForm');
  if (savedForm) {
    const parsedForm = JSON.parse(savedForm);
    Object.assign(caseForm, parsedForm);
  }
  
  // 页面卸载时清理本地存储
  window.addEventListener('beforeunload', () => {
    localStorage.removeItem('caseForm');
  });
}
</script>

<style scoped>
.case-detail-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.info-card,
.steps-card,
.result-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-steps {
  padding: 40px 0;
  text-align: center;
}

.dialog-footer {
  text-align: right;
}
</style>
