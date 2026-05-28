<template>
  <el-card v-if="store.currentStep === 1" class="step-card">
    <template #header>
      <div class="card-header">
        <span>配置测试参数</span>
        <el-button size="small" @click="$emit('prev')">上一步</el-button>
      </div>
    </template>
    <el-form :model="store.formData" label-width="120px">
      <el-form-item label="待生成范围">
        <div class="scope-preview">
          <div class="quality-card">
            <div class="quality-main">
              <div>
                <div class="quality-title">{{ store.contextQuality.title }}</div>
                <div class="quality-desc">{{ store.contextQuality.description }}</div>
              </div>
              <el-tag
                :type="store.contextQuality.missing.length === 0 ? 'success' : 'warning'"
                effect="dark"
              >
                {{
                  store.contextQuality.mode === 'new_full_generation' ? '完整上下文' : '轻量/待补齐'
                }}
              </el-tag>
            </div>
            <div class="quality-tags" v-if="store.contextQuality.sourceTags.length > 0">
              <el-tag v-for="tag in store.contextQuality.sourceTags" :key="tag" size="small" round>
                {{ tag }}
              </el-tag>
            </div>
            <el-alert
              v-if="store.contextQuality.missing.length > 0"
              type="warning"
              :closable="false"
              show-icon
              class="quality-alert"
            >
              <template #title> 建议补齐：{{ store.contextQuality.missing.join('、') }} </template>
            </el-alert>
            <el-alert
              v-for="warning in store.contextQuality.warnings"
              :key="warning"
              type="info"
              :closable="false"
              show-icon
              class="quality-alert"
            >
              <template #title>{{ warning }}</template>
            </el-alert>
          </div>
          <div class="scope-stats">
            <el-statistic title="已选测试点" :value="store.formData.test_point_ids.length" />
            <el-statistic
              title="需求文档"
              :value="store.formData.requirement_file_ids.length"
              class="stat-docs"
            />
            <el-statistic
              title="UI原型"
              :value="store.formData.ui_screen_ids.length || store.formData.ui_file_ids.length"
              class="stat-ui"
            />
          </div>
          <div class="scope-testpoints" v-if="store.selectedTestPointsForDisplay.length > 0">
            <div class="st-list">
              <div v-for="tp in store.selectedTestPointsForDisplay" :key="tp.id" class="st-item">
                <span class="st-mod">{{ tp.module }}</span>
                <span class="st-sep">/</span>
                <span class="st-point">{{ tp.point }}</span>
                <el-tag size="small" :type="store.getPriorityType(tp.priority)" round>{{
                  store.getPriorityLabel(tp.priority)
                }}</el-tag>
              </div>
            </div>
            <div class="st-more" v-if="store.formData.test_point_ids.length > 5">
              还有 {{ store.formData.test_point_ids.length - 5 }} 个测试点未展示...
            </div>
          </div>
          <el-alert v-else type="info" :closable="false" show-icon style="margin-top: 8px">
            AI 将基于所选需求文档和测试点自动分析并生成测试用例，无需手动描述场景
          </el-alert>
        </div>
      </el-form-item>
      <el-form-item label="用例类型">
        <div class="case-type-group">
          <el-select
            v-model="store.formData.case_type"
            placeholder="请选择用例类型（不选择则由AI智能判断）"
            style="width: 180px"
            @change="store.handleCaseTypeChange"
          >
            <el-option label="UI自动化" value="ui_automation" />
            <el-option label="手工测试" value="manual" />
            <el-option label="API自动化" value="api_automation" />
            <el-option label="性能测试" value="performance" />
            <el-option label="安全测试" value="security" />
          </el-select>
          <div class="exec-mode-group" v-if="store.formData.case_type === 'ui_automation'">
            <span class="exec-label">执行方式：</span>
            <el-radio-group v-model="store.formData.exec_mode" size="small">
              <el-radio-button value="all">
                全部自动标注
                <el-tooltip
                  content="AI根据每个用例内容自动判断是UI自动化还是手工测试"
                  placement="top"
                >
                  <el-icon style="margin-left: 4px; vertical-align: middle; color: #909399"
                    ><InfoFilled
                  /></el-icon>
                </el-tooltip>
              </el-radio-button>
              <el-radio-button value="ui_auto">仅 UI 自动化</el-radio-button>
              <el-radio-button value="manual">仅手工测试</el-radio-button>
            </el-radio-group>
          </div>
          <el-alert
            v-if="store.formData.case_type === 'api_automation'"
            type="success"
            :closable="false"
            show-icon
            style="margin-top: 8px; max-width: 500px"
          >
            <template #title>API自动化模式</template>
            AI 将根据接口文档/API定义生成接口级测试用例，包含请求参数、断言规则、响应校验
          </el-alert>
          <el-alert
            v-if="store.formData.case_type === 'performance'"
            type="warning"
            :closable="false"
            show-icon
            style="margin-top: 8px; max-width: 500px"
          >
            <template #title>性能测试模式</template>
            AI 将生成关注响应时间、并发、吞吐量等性能指标的测试用例
          </el-alert>
          <el-alert
            v-if="store.formData.case_type === 'security'"
            type="error"
            :closable="false"
            show-icon
            style="margin-top: 8px; max-width: 500px"
          >
            <template #title>安全测试模式</template>
            AI 将生成涉及XSS、SQL注入、权限绕过等安全验证的测试用例
          </el-alert>
        </div>
      </el-form-item>
      <el-form-item label="补充要求">
        <el-input
          v-model="store.formData.extra_requirements"
          type="textarea"
          :rows="3"
          placeholder="可选：补充特殊要求"
        />
        <div class="form-tip" style="margin-top: 4px">
          不填则由 AI 根据测试点智能判断，通常无需填写
        </div>
      </el-form-item>
      <el-form-item label="优先级">
        <el-select v-model="store.formData.priority" placeholder="请选择优先级">
          <el-option label="P0-高（核心流程）" :value="1" />
          <el-option label="P2-中（主要功能）" :value="2" />
          <el-option label="P3-低（边缘场景）" :value="3" />
        </el-select>
      </el-form-item>
      <el-form-item label="增强模式">
        <el-switch v-model="store.formData.enhanced_mode" active-text="启用" inactive-text="禁用" />
        <span class="form-tip">启用后生成含具体测试数据、断言规则的详细用例</span>
      </el-form-item>
      <el-form-item>
        <el-button
          type="primary"
          @click="$emit('generate')"
          :loading="store.generating"
          :disabled="store.canGenerate === false"
        >
          <el-icon><MagicStick /></el-icon>
          开始生成 ({{ store.generateButtonLabel }})
        </el-button>
        <el-button @click="store.resetForm">重置</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { MagicStick, InfoFilled } from '@element-plus/icons-vue'
import { useGenerateStore } from '@/store/useGenerateStore'

defineEmits<{ prev: []; generate: [] }>()
const store = useGenerateStore()
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.step-card {
  margin-bottom: 20px;
}
.scope-preview {
  width: 100%;
}
.quality-card {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: #fff;
}
.quality-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.quality-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.quality-desc {
  margin-top: 4px;
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
}
.quality-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.quality-alert {
  margin-top: 8px;
}
.scope-stats {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  padding: 12px 16px;
  background: #f8f9fb;
  border-radius: 8px;
}
.scope-stats .stat-docs :deep(.el-statistic__head),
.scope-stats .stat-ui :deep(.el-statistic__head) {
  color: #606266;
}
.scope-testpoints {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 14px;
  background: #fafbfc;
  max-height: 240px;
  overflow-y: auto;
}
.st-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.st-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 4px;
  font-size: 13px;
  transition: background 0.2s;
}
.st-item:hover {
  background: #ecf5ff;
}
.st-mod {
  color: #409eff;
  font-weight: 600;
  white-space: nowrap;
  min-width: 70px;
}
.st-sep {
  color: #c0c4cc;
}
.st-point {
  color: #606266;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
}
.st-more {
  text-align: center;
  color: #909399;
  font-size: 12px;
  padding: 6px 0;
  border-top: 1px dashed #e4e7ed;
  margin-top: 4px;
}
.case-type-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.exec-mode-group {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  padding: 10px 14px;
  background: #f8f9fb;
  border-radius: 6px;
}
.exec-label {
  color: #606266;
  font-size: 13px;
  white-space: nowrap;
  font-weight: 500;
}
.form-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}
</style>
