<template>
  <div class="case-quality-analysis-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button @click="goBack" :icon="ArrowLeft">返回</el-button>
        <h2 class="page-title">用例质量分析 - {{ caseInfo?.title || '加载中...' }}</h2>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="analyzeQuality" :loading="analyzing">
          <el-icon><Refresh /></el-icon>重新分析
        </el-button>
        <el-button @click="showOptimizationDialog = true">
          <el-icon><MagicStick /></el-icon>查看优化建议
        </el-button>
      </div>
    </div>

    <!-- 综合评分卡片 -->
    <div class="overall-score-section" v-if="qualityReport">
      <el-card class="score-card">
        <div class="score-display">
          <div class="main-score">
            <el-progress
              type="dashboard"
              :percentage="qualityReport.overall_score"
              :color="scoreColor"
              :stroke-width="12"
              :width="150"
            />
            <div class="score-label">综合质量评分</div>
            <div class="score-level" :class="scoreLevelClass">{{ scoreLevelText }}</div>
          </div>
          <div class="score-details">
            <div class="score-item">
              <div class="score-item-label">复杂度</div>
              <el-progress :percentage="qualityReport.complexity.total_score" :color="getScoreColor(qualityReport.complexity.total_score)" />
              <div class="score-item-value">{{ qualityReport.complexity.total_score }}分</div>
            </div>
            <div class="score-item">
              <div class="score-item-label">冗余度</div>
              <el-progress :percentage="qualityReport.redundancy.total_score" :color="getScoreColor(qualityReport.redundancy.total_score)" />
              <div class="score-item-value">{{ qualityReport.redundancy.total_score }}分</div>
            </div>
            <div class="score-item">
              <div class="score-item-label">覆盖率</div>
              <el-progress :percentage="qualityReport.coverage.total_score" :color="getScoreColor(qualityReport.coverage.total_score)" />
              <div class="score-item-value">{{ qualityReport.coverage.total_score }}分</div>
            </div>
            <div class="score-item">
              <div class="score-item-label">成本效率</div>
              <el-progress :percentage="getCostScore(qualityReport.cost)" :color="getScoreColor(getCostScore(qualityReport.cost))" />
              <div class="score-item-value">{{ getCostScore(qualityReport.cost) }}分</div>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 详细分析 -->
    <div class="analysis-details" v-if="qualityReport">
      <el-row :gutter="20">
        <!-- 复杂度分析 -->
        <el-col :span="12">
          <el-card class="analysis-card">
            <template #header>
              <div class="card-header">
                <span>复杂度分析</span>
                <el-tag :type="getComplexityTagType(qualityReport.complexity.level)">
                  {{ getComplexityText(qualityReport.complexity.level) }}
                </el-tag>
              </div>
            </template>
            <div class="analysis-content">
              <div class="metric-item">
                <div class="metric-label">步骤数量评分</div>
                <el-progress :percentage="qualityReport.complexity.step_count_score" />
                <div class="metric-desc">{{ qualityReport.complexity.step_count_score >= 20 ? '步骤数量适中' : '步骤数量过多，建议拆分' }}</div>
              </div>
              <div class="metric-item">
                <div class="metric-label">操作类型多样性</div>
                <el-progress :percentage="qualityReport.complexity.action_variety_score" />
                <div class="metric-desc">操作类型越丰富，用例覆盖越全面</div>
              </div>
              <div class="metric-item">
                <div class="metric-label">数据依赖复杂度</div>
                <el-progress :percentage="qualityReport.complexity.data_dependency_score" />
                <div class="metric-desc">数据依赖越少，执行越稳定</div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 冗余度分析 -->
        <el-col :span="12">
          <el-card class="analysis-card">
            <template #header>
              <div class="card-header">
                <span>冗余度分析</span>
                <el-tag v-if="qualityReport.redundancy.redundant_step_indices.length > 0" type="warning">
                  发现{{ qualityReport.redundancy.redundant_step_indices.length }}个冗余步骤
                </el-tag>
                <el-tag v-else type="success">无冗余</el-tag>
              </div>
            </template>
            <div class="analysis-content">
              <div class="metric-item">
                <div class="metric-label">重复步骤评分</div>
                <el-progress :percentage="qualityReport.redundancy.duplicate_steps_score" />
              </div>
              <div class="metric-item">
                <div class="metric-label">相似用例评分</div>
                <el-progress :percentage="qualityReport.redundancy.similar_cases_score" />
              </div>
              <div class="metric-item">
                <div class="metric-label">不必要步骤评分</div>
                <el-progress :percentage="qualityReport.redundancy.unnecessary_steps_score" />
              </div>
              <div v-if="qualityReport.redundancy.redundant_step_indices.length > 0" class="redundant-steps">
                <div class="redundant-title">冗余步骤索引:</div>
                <el-tag
                  v-for="index in qualityReport.redundancy.redundant_step_indices"
                  :key="index"
                  type="warning"
                  class="redundant-tag"
                >
                  步骤{{ index + 1 }}
                </el-tag>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" class="mt-20">
        <!-- 覆盖率分析 -->
        <el-col :span="12">
          <el-card class="analysis-card">
            <template #header>
              <div class="card-header">
                <span>覆盖率分析</span>
              </div>
            </template>
            <div class="analysis-content">
              <div class="coverage-item">
                <div class="coverage-header">
                  <span>元素定位覆盖率</span>
                  <span class="coverage-value">{{ qualityReport.coverage.locator_coverage }}%</span>
                </div>
                <el-progress :percentage="qualityReport.coverage.locator_coverage" :color="getCoverageColor(qualityReport.coverage.locator_coverage)" />
                <div class="coverage-desc">
                  {{ qualityReport.coverage.locator_coverage >= 80 ? '定位信息完整' : '建议补充元素定位，降低AI视觉成本' }}
                </div>
              </div>
              <div class="coverage-item">
                <div class="coverage-header">
                  <span>执行历史覆盖率</span>
                  <span class="coverage-value">{{ qualityReport.coverage.execution_coverage }}%</span>
                </div>
                <el-progress :percentage="qualityReport.coverage.execution_coverage" />
                <div class="coverage-desc">执行次数越多，用例越稳定</div>
              </div>
              <div class="coverage-item">
                <div class="coverage-header">
                  <span>断言覆盖率</span>
                  <span class="coverage-value">{{ qualityReport.coverage.assertion_coverage }}%</span>
                </div>
                <el-progress :percentage="qualityReport.coverage.assertion_coverage" :color="getCoverageColor(qualityReport.coverage.assertion_coverage)" />
                <div class="coverage-desc">
                  {{ qualityReport.coverage.assertion_coverage >= 30 ? '验证点充足' : '建议增加验证步骤' }}
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 成本分析 -->
        <el-col :span="12">
          <el-card class="analysis-card">
            <template #header>
              <div class="card-header">
                <span>AI视觉成本分析</span>
              </div>
            </template>
            <div class="analysis-content">
              <div class="cost-overview">
                <div class="cost-item">
                  <div class="cost-label">预估AI调用次数</div>
                  <div class="cost-value">{{ qualityReport.cost.ai_vision_calls }}次</div>
                </div>
                <div class="cost-item">
                  <div class="cost-label">预估成本</div>
                  <div class="cost-value">{{ qualityReport.cost.estimated_cost }}单位</div>
                </div>
                <div class="cost-item highlight">
                  <div class="cost-label">潜在节省</div>
                  <div class="cost-value savings">{{ qualityReport.cost.potential_savings }}单位</div>
                </div>
              </div>
              <div class="cost-suggestions" v-if="qualityReport.cost.optimization_suggestions.length > 0">
                <div class="suggestions-title">成本优化建议:</div>
                <div
                  v-for="(suggestion, index) in qualityReport.cost.optimization_suggestions"
                  :key="index"
                  class="suggestion-item"
                >
                  <el-tag :type="suggestion.priority === 'high' ? 'danger' : 'warning'" size="small">
                    {{ suggestion.type }}
                  </el-tag>
                  <span class="suggestion-desc">{{ suggestion.description }}</span>
                  <span class="suggestion-savings">可节省{{ suggestion.potential_savings }}单位</span>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 优化建议对话框 -->
    <el-dialog
      v-model="showOptimizationDialog"
      title="优化建议"
      width="800px"
    >
      <div v-if="qualityReport && qualityReport.optimization_suggestions.length > 0" class="optimization-list">
        <div
          v-for="(suggestion, index) in qualityReport.optimization_suggestions"
          :key="index"
          class="optimization-item"
        >
          <div class="optimization-header">
            <el-tag :type="getPriorityType(suggestion.priority)">{{ suggestion.priority }}</el-tag>
            <span class="optimization-category">{{ suggestion.category }}</span>
          </div>
          <div class="optimization-title">{{ suggestion.title }}</div>
          <div class="optimization-desc">{{ suggestion.description }}</div>
          <div class="optimization-impact">
            <el-icon><InfoFilled /></el-icon>
            <span>影响: {{ suggestion.impact }}</span>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无优化建议，用例质量良好！" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh, MagicStick, InfoFilled } from '@element-plus/icons-vue'
import { analyzeCaseQuality } from '@/api/caseQuality'
import { testCaseApi } from '@/api/case'

// 路由
const route = useRoute()
const router = useRouter()
const caseId = computed(() => Number(route.params.caseId))

// 状态
const caseInfo = ref<any>(null)
const qualityReport = ref<any>(null)
const analyzing = ref(false)
const showOptimizationDialog = ref(false)

// 计算属性
const scoreColor = computed(() => {
  const score = qualityReport.value?.overall_score || 0
  if (score >= 80) return '#67C23A'
  if (score >= 60) return '#E6A23C'
  return '#F56C6C'
})

const scoreLevelClass = computed(() => {
  const score = qualityReport.value?.overall_score || 0
  if (score >= 80) return 'excellent'
  if (score >= 60) return 'good'
  if (score >= 40) return 'fair'
  return 'poor'
})

const scoreLevelText = computed(() => {
  const score = qualityReport.value?.overall_score || 0
  if (score >= 80) return '优秀'
  if (score >= 60) return '良好'
  if (score >= 40) return '一般'
  return '需优化'
})

// 方法
const loadCaseInfo = async () => {
  try {
    const res = await testCaseApi.getCaseDetail(caseId.value)
    caseInfo.value = res
  } catch (error) {
    console.error('加载用例信息失败:', error)
    ElMessage.error('加载用例信息失败')
  }
}

const analyzeQuality = async () => {
  analyzing.value = true
  try {
    const res = await analyzeCaseQuality(caseId.value)
    if (res.data.code === 200) {
      qualityReport.value = res.data.data
      ElMessage.success('质量分析完成')
    } else {
      ElMessage.error(res.data.message || '分析失败')
    }
  } catch (error) {
    console.error('质量分析失败:', error)
    ElMessage.error('质量分析失败')
  } finally {
    analyzing.value = false
  }
}

const getScoreColor = (score: number) => {
  if (score >= 80) return '#67C23A'
  if (score >= 60) return '#E6A23C'
  return '#F56C6C'
}

const getCostScore = (cost: any) => {
  if (!cost || cost.estimated_cost === 0) return 100
  return Math.max(0, 100 - cost.estimated_cost * 10)
}

const getComplexityTagType = (level: string) => {
  const typeMap: Record<string, any> = {
    'low': 'success',
    'medium': 'warning',
    'high': 'danger'
  }
  return typeMap[level] || 'info'
}

const getComplexityText = (level: string) => {
  const textMap: Record<string, string> = {
    'low': '低复杂度',
    'medium': '中复杂度',
    'high': '高复杂度'
  }
  return textMap[level] || '未知'
}

const getCoverageColor = (coverage: number) => {
  if (coverage >= 80) return '#67C23A'
  if (coverage >= 50) return '#E6A23C'
  return '#F56C6C'
}

const getPriorityType = (priority: string) => {
  const typeMap: Record<string, any> = {
    'high': 'danger',
    'medium': 'warning',
    'low': 'info'
  }
  return typeMap[priority] || 'info'
}

const goBack = () => {
  router.back()
}

// 生命周期
onMounted(async () => {
  await loadCaseInfo()
  analyzeQuality()
})
</script>

<style scoped lang="scss">
.case-quality-analysis-page {
  padding: 20px;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 15px;

      .page-title {
        margin: 0;
        font-size: 20px;
      }
    }

    .header-right {
      display: flex;
      gap: 10px;
    }
  }

  .overall-score-section {
    margin-bottom: 20px;

    .score-card {
      .score-display {
        display: flex;
        align-items: center;
        gap: 40px;

        .main-score {
          text-align: center;

          .score-label {
            margin-top: 10px;
            font-size: 16px;
            color: #606266;
          }

          .score-level {
            margin-top: 5px;
            font-size: 18px;
            font-weight: bold;

            &.excellent {
              color: #67C23A;
            }

            &.good {
              color: #E6A23C;
            }

            &.fair {
              color: #409EFF;
            }

            &.poor {
              color: #F56C6C;
            }
          }
        }

        .score-details {
          flex: 1;

          .score-item {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;

            &:last-child {
              margin-bottom: 0;
            }

            .score-item-label {
              width: 100px;
              color: #606266;
            }

            .el-progress {
              flex: 1;
            }

            .score-item-value {
              width: 60px;
              text-align: right;
              font-weight: bold;
            }
          }
        }
      }
    }
  }

  .analysis-details {
    .mt-20 {
      margin-top: 20px;
    }

    .analysis-card {
      height: 100%;

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-weight: bold;
      }

      .analysis-content {
        .metric-item {
          margin-bottom: 20px;

          &:last-child {
            margin-bottom: 0;
          }

          .metric-label {
            margin-bottom: 8px;
            color: #606266;
          }

          .metric-desc {
            margin-top: 5px;
            font-size: 12px;
            color: #909399;
          }
        }

        .redundant-steps {
          margin-top: 15px;
          padding: 10px;
          background: #fdf6ec;
          border-radius: 4px;

          .redundant-title {
            margin-bottom: 8px;
            color: #e6a23c;
            font-weight: bold;
          }

          .redundant-tag {
            margin-right: 8px;
            margin-bottom: 5px;
          }
        }

        .coverage-item {
          margin-bottom: 20px;

          &:last-child {
            margin-bottom: 0;
          }

          .coverage-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;

            .coverage-value {
              font-weight: bold;
            }
          }

          .coverage-desc {
            margin-top: 5px;
            font-size: 12px;
            color: #909399;
          }
        }

        .cost-overview {
          display: flex;
          justify-content: space-around;
          margin-bottom: 20px;
          padding: 15px;
          background: #f5f7fa;
          border-radius: 4px;

          .cost-item {
            text-align: center;

            .cost-label {
              font-size: 12px;
              color: #909399;
              margin-bottom: 5px;
            }

            .cost-value {
              font-size: 24px;
              font-weight: bold;
              color: #606266;

              &.savings {
                color: #67c23a;
              }
            }

            &.highlight {
              .cost-value {
                color: #67c23a;
              }
            }
          }
        }

        .cost-suggestions {
          .suggestions-title {
            margin-bottom: 10px;
            font-weight: bold;
          }

          .suggestion-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            margin-bottom: 8px;
            background: #f5f7fa;
            border-radius: 4px;

            .suggestion-desc {
              flex: 1;
            }

            .suggestion-savings {
              color: #67c23a;
              font-weight: bold;
            }
          }
        }
      }
    }
  }

  .optimization-list {
    .optimization-item {
      padding: 15px;
      margin-bottom: 15px;
      border: 1px solid #ebeef5;
      border-radius: 4px;

      &:last-child {
        margin-bottom: 0;
      }

      .optimization-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;

        .optimization-category {
          color: #909399;
          font-size: 12px;
        }
      }

      .optimization-title {
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 8px;
      }

      .optimization-desc {
        color: #606266;
        margin-bottom: 10px;
        line-height: 1.6;
      }

      .optimization-impact {
        display: flex;
        align-items: center;
        gap: 5px;
        color: #409eff;
        font-size: 12px;
      }
    }
  }
}
</style>
