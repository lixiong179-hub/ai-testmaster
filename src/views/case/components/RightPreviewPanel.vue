<template>
  <div class="right-panel right-panel-enhanced">
    <transition name="fade" mode="out-in">
      <!-- 步骤1右侧 -->
      <div v-if="currentStep === 0" key="preview1" class="preview-card preview-card-enhanced">
        <div v-if="!selectedProjectInfo" class="preview-welcome">
          <div class="welcome-illustration">
            <div class="welcome-icon-bg">
              <el-icon :size="56" color="#fff"><MagicStick /></el-icon>
            </div>
          </div>
          <h3 class="welcome-title">高级测试点提取向导</h3>
          <p class="welcome-desc">适用于复杂资源筛选、兼容旧流程和逐步提取场景</p>

          <div class="feature-list">
            <div class="feature-item">
              <div class="feature-icon">
                <el-icon :size="20" color="#409EFF"><Document /></el-icon>
              </div>
              <div class="feature-text">
                <div class="feature-name">智能解析</div>
                <div class="feature-desc">自动识别需求文档结构</div>
              </div>
            </div>
            <div class="feature-item">
              <div class="feature-icon">
                <el-icon :size="20" color="#67C23A"><MagicStick /></el-icon>
              </div>
              <div class="feature-text">
                <div class="feature-name">AI 提取</div>
                <div class="feature-desc">智能生成测试点</div>
              </div>
            </div>
            <div class="feature-item">
              <div class="feature-icon">
                <el-icon :size="20" color="#E6A23C"><DataAnalysis /></el-icon>
              </div>
              <div class="feature-text">
                <div class="feature-name">数据分析</div>
                <div class="feature-desc">多维度统计分析</div>
              </div>
            </div>
          </div>

          <div class="tip-card">
            <el-icon :size="18" color="#E6A23C"><InfoFilled /></el-icon>
            <span>请先从左侧选择一个项目开始</span>
          </div>
        </div>

        <div v-else class="preview-body preview-body-enhanced">
          <div class="project-summary-card">
            <div class="summary-header">
              <el-icon :size="32" color="#409EFF"><FolderOpened /></el-icon>
              <div class="summary-info">
                <h4 class="summary-title">{{ selectedProjectInfo.name }}</h4>
                <span class="summary-id">ID: {{ selectedProjectInfo.id }}</span>
              </div>
            </div>

            <div class="summary-stats">
              <div class="summary-stat-item">
                <div class="stat-icon-wrapper stat-blue">
                  <el-icon><Files /></el-icon>
                </div>
                <div class="stat-detail">
                  <div class="stat-number">{{ files.length }}</div>
                  <div class="stat-text">资源文件</div>
                </div>
              </div>
              <div class="summary-stat-divider"></div>
              <div class="summary-stat-item">
                <div class="stat-icon-wrapper stat-green">
                  <el-icon><Document /></el-icon>
                </div>
                <div class="stat-detail">
                  <div class="stat-number">{{ getResourceTypeCount('requirement') }}</div>
                  <div class="stat-text">需求文档</div>
                </div>
              </div>
            </div>

            <div class="resource-preview-list">
              <div class="preview-list-title">资源类型分布</div>
              <div class="preview-type-items">
                <div class="type-item">
                  <div
                    class="type-bar type-requirement"
                    :style="{ width: getResourceTypePercentage('requirement') + '%' }"
                  ></div>
                  <span class="type-label">需求文档</span>
                  <span class="type-count">{{ getResourceTypeCount('requirement') }}</span>
                </div>
                <div class="type-item">
                  <div
                    class="type-bar type-ui"
                    :style="{ width: getResourceTypePercentage('ui_mockup') + '%' }"
                  ></div>
                  <span class="type-label">UI原型</span>
                  <span class="type-count">{{ getResourceTypeCount('ui_mockup') }}</span>
                </div>
                <div class="type-item">
                  <div
                    class="type-bar type-api"
                    :style="{ width: getResourceTypePercentage('api_doc') + '%' }"
                  ></div>
                  <span class="type-label">API文档</span>
                  <span class="type-count">{{ getResourceTypeCount('api_doc') }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="next-action-card">
            <div class="action-hint">
              <el-icon><ArrowRight /></el-icon>
              <span>准备就绪，可以继续下一步</span>
            </div>
            <el-button type="primary" class="next-btn-large" @click="goToNextStep">
              下一步：选择需求
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <!-- 步骤2右侧 -->
      <div v-else-if="currentStep === 1 && selectedResource" key="preview2" class="preview-card">
        <div class="preview-header">
          <el-icon><View /></el-icon>
          <span>资源详情</span>
        </div>
        <div class="preview-body">
          <div class="resource-detail-card">
            <div class="detail-icon">
              <el-icon :size="48" color="#409EFF">
                <component :is="getResourceIcon(selectedResource.resource_type)" />
              </el-icon>
            </div>
            <div class="detail-info">
              <div class="detail-name">{{ selectedResource.display_name }}</div>
              <div class="detail-meta">
                <el-tag :type="getResourceTypeTagType(selectedResource.resource_type)" size="small">
                  {{ getResourceTypeLabel(selectedResource.resource_type) }}
                </el-tag>
              </div>
              <div class="detail-stats">
                <div class="stat-item">
                  <span class="stat-label">大小</span>
                  <span class="stat-value">{{ selectedResource.size_text }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">时间</span>
                  <span class="stat-value">{{ selectedResource.time_text }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="next-step-hint">
            <el-button type="primary" @click="goToNextStep">
              下一步：AI提取
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <!-- 步骤2右侧(空) -->
      <div
        v-else-if="currentStep === 1 && !selectedResource"
        key="preview2-empty"
        class="preview-card preview-empty"
      >
        <el-empty description="请从左侧选择一个需求资源" :image-size="100" />
      </div>

      <!-- 步骤3右侧 -->
      <div v-else-if="currentStep === 2" key="preview3" class="preview-card">
        <div class="preview-header">
          <el-icon><DataAnalysis /></el-icon>
          <span>{{
            extracting ? '提取中...' : testPoints.length > 0 ? '提取结果' : '等待提取'
          }}</span>
        </div>
        <div class="preview-body">
          <div v-if="extracting" class="stats-skeleton">
            <el-skeleton :rows="4" animated />
          </div>
          <div v-else-if="testPoints.length > 0" class="extract-stats">
            <div class="stat-card total">
              <div class="stat-number">{{ testPoints.length }}</div>
              <div class="stat-label">测试点总数</div>
            </div>
            <div class="priority-distribution">
              <div class="distribution-title">优先级分布</div>
              <div class="distribution-items">
                <div class="dist-item high">
                  <span class="dist-count">{{ getPriorityCount(1) }}</span>
                  <span class="dist-label">高优先级</span>
                </div>
                <div class="dist-item medium">
                  <span class="dist-count">{{ getPriorityCount(2) }}</span>
                  <span class="dist-label">中优先级</span>
                </div>
                <div class="dist-item low">
                  <span class="dist-count">{{ getPriorityCount(3) }}</span>
                  <span class="dist-label">低优先级</span>
                </div>
              </div>
            </div>
            <div class="module-distribution">
              <div class="distribution-title">模块分布</div>
              <div class="module-list">
                <div
                  v-for="(count, module) in getModuleDistribution()"
                  :key="module"
                  class="module-item"
                >
                  <span class="module-name">{{ module }}</span>
                  <span class="module-count">{{ count }}</span>
                </div>
              </div>
            </div>
            <div class="next-step-hint">
              <el-button type="primary" @click="goToNextStep">
                下一步：管理测试点
                <el-icon><ArrowRight /></el-icon>
              </el-button>
            </div>
          </div>
          <div v-else class="waiting-state">
            <el-empty description="等待提取测试点" :image-size="100" />
          </div>
        </div>
      </div>

      <!-- 步骤4右侧 -->
      <div v-else-if="currentStep === 3" key="preview4" class="preview-card">
        <div class="preview-header">
          <el-icon><Guide /></el-icon>
          <span>操作指南</span>
        </div>
        <div class="preview-body">
          <div class="guide-list">
            <div class="guide-item">
              <el-icon color="#67C23A"><Check /></el-icon>
              <span>支持逐条校验提取结果后再保存</span>
            </div>
            <div class="guide-item">
              <el-icon color="#409EFF"><Edit /></el-icon>
              <span>可编辑单个测试点后再入库</span>
            </div>
            <div class="guide-item">
              <el-icon color="#E6A23C"><FolderAdd /></el-icon>
              <span>建议保存后回测试点管理继续日常维护</span>
            </div>
            <div class="guide-item">
              <el-icon color="#F56C6C"><MagicStick /></el-icon>
              <span>仅在需要高级流程时再进入 AI 生成页</span>
            </div>
          </div>
          <div class="quick-stats" v-if="testPoints.length > 0">
            <div class="quick-stat-item">
              <span class="qs-label">总测试点</span>
              <span class="qs-value">{{ savedFromDb ? dbTotal : testPoints.length }}</span>
            </div>
            <div class="quick-stat-item">
              <span class="qs-label">已选中</span>
              <span class="qs-value highlight">{{ selectedRows.length }}</span>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import {
  MagicStick,
  Document,
  DataAnalysis,
  InfoFilled,
  FolderOpened,
  Files,
  View,
  ArrowRight,
  Guide,
  Check,
  Edit,
  FolderAdd,
} from '@element-plus/icons-vue'
import { useTestPointExtract } from '@/composables/useTestPointExtract'

const {
  currentStep,
  selectedProjectInfo,
  files,
  selectedResource,
  extracting,
  testPoints,
  savedFromDb,
  dbTotal,
  selectedRows,
  getResourceIcon,
  getResourceTypeTagType,
  getResourceTypeLabel,
  getResourceTypeCount,
  getResourceTypePercentage,
  getPriorityCount,
  getModuleDistribution,
  goToNextStep,
} = useTestPointExtract()
</script>
