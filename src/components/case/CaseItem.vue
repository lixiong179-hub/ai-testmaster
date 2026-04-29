<template>
  <el-card class="case-item case-card" :class="{ 'failed': caseItem.generate_status === 2 }">
    <template #header>
      <div class="case-header">
        <div class="case-info">
          <span class="case-no">{{ caseItem.case_no }}</span>
          <span 
            class="case-priority" 
            :class="{
              'high': caseItem.priority === 1,
              'medium': caseItem.priority === 2,
              'low': caseItem.priority === 3
            }"
          >
            {{ priorityText(caseItem.priority) }}
          </span>
        </div>
        <div class="case-status" :class="statusClass(caseItem.generate_status)">
          {{ statusText(caseItem.generate_status) }}
        </div>
      </div>
    </template>
    
    <div class="case-content">
      <h3 class="case-title">{{ caseItem.title }}</h3>
      <div class="case-meta">
        <span class="case-meta-item">
          <el-icon><Folder /></el-icon>
          {{ caseItem.module }}
        </span>
        <el-tag
          :type="caseTypeTagType"
          size="small"
          effect="plain"
          class="case-type-tag"
        >
          {{ caseTypeLabel }}
        </el-tag>
        <span class="case-meta-item">
          <el-icon><Clock /></el-icon>
          {{ formatTime(caseItem.create_time) }}
        </span>
      </div>
      <div class="case-details">
        <div v-if="caseItem.precondition" class="case-section">
          <div class="section-header">
            <el-icon><Document /></el-icon>
            <span>前置条件</span>
          </div>
          <div class="section-content">
            <p>{{ caseItem.precondition }}</p>
          </div>
        </div>
        <div v-if="caseItem.steps && caseItem.steps.length > 0" class="case-section">
          <div class="section-header">
            <el-icon><List /></el-icon>
            <span>测试步骤</span>
          </div>
          <div class="section-content">
            <ul class="steps-list">
              <li v-for="(step, index) in caseItem.steps" :key="index">
                <span class="step-number">{{ step.step_number || step.step || index + 1 }}</span>
                <span class="step-content">{{ step.action }}{{ step.param ? ` (${step.param})` : '' }}</span>
                <span v-if="(step as any).expected" class="step-expected">→ {{ (step as any).expected }}</span>
              </li>
            </ul>
          </div>
        </div>
        <div v-if="caseItem.expected_result" class="case-section">
          <div class="section-header">
            <el-icon><SuccessFilled /></el-icon>
            <span>预期结果</span>
          </div>
          <div class="section-content">
            <p>{{ caseItem.expected_result }}</p>
          </div>
        </div>
      </div>
    </div>
    
    <div class="case-actions">
      <el-button type="primary" size="small" @click="viewDetail">
        <el-icon><View /></el-icon>
        查看详情
      </el-button>
      <el-button type="info" size="small" @click="copyCase">
        <el-icon><DocumentCopy /></el-icon>
        复制用例
      </el-button>
      <el-button 
        type="warning" 
        size="small" 
        v-if="caseItem.generate_status === 2"
        @click="retryGenerate"
      >
        <el-icon><Refresh /></el-icon>
        重试生成
      </el-button>
      <el-button type="danger" size="small" @click="deleteCase">
        <el-icon><Delete /></el-icon>
        删除
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { 
  Folder, 
  Clock, 
  Document, 
  List, 
  SuccessFilled, 
  View, 
  DocumentCopy, 
  Refresh, 
  Delete 
} from '@element-plus/icons-vue';
import type { TestCase } from '@/types/testCase';

const props = defineProps<{
  caseItem: TestCase;
}>();

const emit = defineEmits<{
  (e: 'viewDetail', caseId: number): void;
  (e: 'copyCase', caseItem: TestCase): void;
  (e: 'retryGenerate', caseId: number): void;
  (e: 'deleteCase', caseId: number): void;
}>();

const CASE_TYPE_MAP: Record<string, { label: string; tagType: string }> = {
  'ui_automation': { label: 'UI自动化', tagType: 'success' },
  'manual': { label: '手工测试', tagType: 'info' },
  'api_automation': { label: 'API自动化', tagType: '' },
  'performance': { label: '性能测试', tagType: 'warning' },
  'security': { label: '安全测试', tagType: 'danger' },
  'UI': { label: 'UI自动化', tagType: 'success' },
  'API': { label: 'API自动化', tagType: '' },
  '功能': { label: '手工测试', tagType: 'info' },
  '功能测试': { label: '手工测试', tagType: 'info' },
  'functional': { label: '手工测试', tagType: 'info' },
  '接口': { label: 'API自动化', tagType: '' },
};

const caseTypeLabel = computed(() => {
  const type = props.caseItem.case_type || '';
  return CASE_TYPE_MAP[type]?.label || type;
});

const caseTypeTagType = computed(() => {
  const type = props.caseItem.case_type || '';
  return CASE_TYPE_MAP[type]?.tagType || 'info';
});

const priorityText = (priority: number | undefined): string => {
  const map: Record<number, string> = {
    1: '高',
    2: '中',
    3: '低'
  };
  return map[priority ?? 2] || '中';
};

const statusText = (status: number | undefined): string => {
  const map: Record<number, string> = {
    0: '生成中',
    1: '生成成功',
    2: '生成失败'
  };
  return map[status ?? 0] || '未知';
};

const statusClass = (status: number | undefined): string => {
  const map: Record<number, string> = {
    0: 'status-processing',
    1: 'status-success',
    2: 'status-failed'
  };
  return map[status ?? 0] || '';
};

const formatTime = (time: string | undefined): string => {
  if (!time) return '';
  return new Date(time).toLocaleString();
};

const viewDetail = () => {
  emit('viewDetail', props.caseItem.id);
};

const copyCase = () => {
  emit('copyCase', props.caseItem);
};

const retryGenerate = () => {
  emit('retryGenerate', props.caseItem.id);
};

const deleteCase = () => {
  emit('deleteCase', props.caseItem.id);
};
</script>

<style>
/* 使用非 scoped 样式提高优先级 */
.case-item {
  margin-bottom: 16px !important;
  border-radius: 12px !important;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.08) !important;
  transition: all 0.3s ease !important;
  height: auto !important;
  min-height: auto !important;
  max-height: none !important;
  width: 100% !important;
  box-sizing: border-box !important;
}

.case-item:hover {
  box-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.12) !important;
  transform: translateY(-2px);
}

.case-item.failed {
  border-left: 4px solid #f56c6c !important;
}

.case-card .el-card__header {
  padding: 16px 20px !important;
  background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%) !important;
  border-bottom: 1px solid #f0f2f5 !important;
  height: auto !important;
  min-height: auto !important;
  max-height: none !important;
}

.case-card .el-card__body {
  padding: 20px !important;
  height: auto !important;
  min-height: auto !important;
  max-height: none !important;
  overflow: visible !important;
}

.case-header {
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
}

.case-info {
  display: flex !important;
  align-items: center !important;
  gap: 12px !important;
}

.case-no {
  font-size: 15px !important;
  font-weight: 700 !important;
  color: #409eff !important;
  letter-spacing: 0.3px !important;
}

.case-priority {
  padding: 4px 12px !important;
  border-radius: 16px !important;
  font-size: 12px !important;
  font-weight: 600 !important;
}

.case-priority.high {
  background: linear-gradient(135deg, #fef0f0 0%, #fee2e2 100%) !important;
  color: #f56c6c !important;
}

.case-priority.medium {
  background: linear-gradient(135deg, #fdf6ec 0%, #faecd8 100%) !important;
  color: #e6a23c !important;
}

.case-priority.low {
  background: linear-gradient(135deg, #f0f9eb 0%, #e1f3d8 100%) !important;
  color: #67c23a !important;
}

.case-status {
  padding: 4px 12px !important;
  border-radius: 16px !important;
  font-size: 12px !important;
  font-weight: 600 !important;
}

.status-processing {
  background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%) !important;
  color: #409eff !important;
}

.status-success {
  background: linear-gradient(135deg, #f0f9eb 0%, #e1f3d8 100%) !important;
  color: #67c23a !important;
}

.status-failed {
  background: linear-gradient(135deg, #fef0f0 0%, #fee2e2 100%) !important;
  color: #f56c6c !important;
}

.case-content {
  margin: 0 !important;
}

.case-title {
  font-size: 18px !important;
  font-weight: 700 !important;
  color: #1f2937 !important;
  margin: 0 0 16px 0 !important;
  line-height: 1.4 !important;
  height: auto !important;
  min-height: auto !important;
  max-height: none !important;
  display: block !important;
}

.case-meta {
  display: flex !important;
  gap: 20px !important;
  margin-bottom: 20px !important;
  font-size: 14px !important;
  color: #6b7280 !important;
  flex-wrap: wrap !important;
  align-items: center !important;
  height: auto !important;
  min-height: auto !important;
  max-height: none !important;
}

.case-meta-item {
  display: flex !important;
  align-items: center !important;
  gap: 6px !important;
}

.case-type-tag {
  flex-shrink: 0 !important;
}

.case-details {
  display: flex !important;
  flex-direction: column !important;
  gap: 16px !important;
}

.case-section {
  background: #f8fafc !important;
  border-radius: 8px !important;
  overflow: hidden !important;
}

.section-header {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  padding: 12px 16px !important;
  background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%) !important;
  font-size: 14px !important;
  font-weight: 600 !important;
  color: #475569 !important;
}

.section-content {
  padding: 14px 16px !important;
}

.section-content p {
  margin: 0 !important;
  font-size: 14px !important;
  color: #374151 !important;
  line-height: 1.6 !important;
}

.steps-list {
  list-style: none !important;
  padding: 0 !important;
  margin: 0 !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 10px !important;
}

.steps-list li {
  display: flex !important;
  align-items: flex-start !important;
  gap: 12px !important;
  font-size: 14px !important;
  color: #374151 !important;
  line-height: 1.6 !important;
}

.step-number {
  flex-shrink: 0 !important;
  width: 28px !important;
  height: 28px !important;
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%) !important;
  color: white !important;
  border-radius: 50% !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  font-weight: 700 !important;
  font-size: 13px !important;
}

.step-content {
  flex: 1 !important;
  padding-top: 2px !important;
}

.step-expected {
  color: #67c23a !important;
  font-style: italic !important;
  padding-top: 2px !important;
}

.case-actions {
  display: flex !important;
  gap: 10px !important;
  justify-content: flex-end !important;
  margin-top: 24px !important;
  padding-top: 20px !important;
  border-top: 1px solid #e5e7eb !important;
  flex-wrap: wrap !important;
  height: auto !important;
  min-height: auto !important;
  max-height: none !important;
}
</style>
