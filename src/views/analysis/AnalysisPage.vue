<template>
  <div class="analysis-page">
    <el-card>
      <template #header>
        <div class="page-header">
          <h2>需求分析</h2>
          <el-button
            type="primary"
            :disabled="analysisStore.status === 'analyzing'"
            @click="startAnalysis"
          >
            {{ analysisStore.status === 'analyzing' ? '分析中...' : '开始分析' }}
          </el-button>
        </div>
      </template>

      <!-- 项目文件列表 -->
      <div class="file-list">
        <h3>项目文件</h3>
        <el-empty v-if="files.length === 0" description="暂无文件，请先上传需求文档或提交URL" />
        <el-table v-else :data="files" style="width: 100%">
          <el-table-column prop="file_name" label="文件名" width="300" />
          <el-table-column prop="file_type" label="文件类型" width="100" />
          <el-table-column prop="upload_time" label="上传时间" width="200" />
          <el-table-column prop="file_path" label="文件路径" show-overflow-tooltip />
        </el-table>
      </div>

      <!-- 分析进度 -->
      <ProgressBar
        v-if="analysisStore.status === 'analyzing'"
        :progress="analysisStore.progress"
        :message="analysisStore.message"
        title="分析进度"
      />

      <!-- 分析结果 -->
      <div
        class="analysis-result"
        v-if="analysisStore.status === 'success' && analysisStore.testPoints.length > 0"
      >
        <div class="result-header">
          <h3>测试点列表</h3>
          <div class="filter-container">
            <el-select
              v-model="filter.module"
              placeholder="按模块筛选"
              style="width: 150px; margin-right: 10px"
            >
              <el-option v-for="module in modules" :key="module" :label="module" :value="module" />
            </el-select>
            <el-select v-model="filter.priority" placeholder="按优先级筛选" style="width: 150px">
              <el-option label="高" value="1" />
              <el-option label="中" value="2" />
              <el-option label="低" value="3" />
            </el-select>
          </div>
        </div>

        <!-- 测试点列表 -->
        <el-collapse>
          <el-collapse-item
            v-for="(modulePoints, module) in filteredTestPoints"
            :key="module"
            :title="`${module} (${modulePoints.length}个测试点)`"
          >
            <el-table
              :data="modulePoints"
              style="width: 100%"
              @selection-change="handleSelectionChange"
            >
              <el-table-column type="selection" width="55" />
              <el-table-column prop="point" label="测试点" show-overflow-tooltip />
              <el-table-column prop="priority" label="优先级" width="80">
                <template #default="scope">
                  <span
                    class="priority-tag"
                    :class="{
                      high: scope.row.priority === 1,
                      medium: scope.row.priority === 2,
                      low: scope.row.priority === 3,
                    }"
                  >
                    {{ priorityText(scope.row.priority) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="create_time" label="创建时间" width="180" />
            </el-table>
          </el-collapse-item>
        </el-collapse>

        <!-- 生成测试用例按钮 -->
        <div class="generate-button-container">
          <el-button type="success" @click="generateAllCases">生成所有测试用例</el-button>
          <el-button
            type="warning"
            @click="generateSelectedCases"
            :disabled="selectedPoints.length === 0"
          >
            生成选中测试用例 ({{ selectedPoints.length }})
          </el-button>
        </div>
      </div>

      <!-- 分析失败 -->
      <el-alert
        v-if="analysisStore.status === 'failed'"
        type="error"
        :title="analysisStore.message"
        show-icon
      />

      <!-- 无测试点 -->
      <el-empty
        v-if="analysisStore.status === 'success' && analysisStore.testPoints.length === 0"
        description="未提取到测试点，请检查需求文档内容"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import ProgressBar from '@/components/analysis/ProgressBar.vue'
import { useAnalysisStore } from '@/store/analysis'
import { useCaseStore } from '@/store/case'
import type { TestPoint } from '@/types/testPoint'

const route = useRoute()
const router = useRouter()
const analysisStore = useAnalysisStore()
const caseStore = useCaseStore()

// 获取项目ID
const projectId = computed(() => Number(route.params.projectId) || 0)

// 文件列表（模拟数据，实际应该从API获取）
const files = ref([
  {
    file_name: '需求文档.docx',
    file_type: 'docx',
    upload_time: '2024-01-01 10:00:00',
    file_path: 'uploads/1/需求文档.docx',
  },
  {
    file_name: '登录页面原型.png',
    file_type: 'png',
    upload_time: '2024-01-01 10:30:00',
    file_path: 'uploads/1/登录页面原型.png',
  },
])

// 筛选条件
const filter = ref({
  module: '',
  priority: '',
})

// 选中的测试点
const selectedPoints = ref<number[]>([])

const handleSelectionChange = (selection: any[]) => {
  selectedPoints.value = selection.map((item) => item.id)
}

// 模块列表
const modules = computed(() => {
  const moduleSet = new Set<string>()
  analysisStore.testPoints.forEach((point) => moduleSet.add(point.module))
  return Array.from(moduleSet)
})

// 筛选后的测试点
const filteredTestPoints = computed(() => {
  let filtered = analysisStore.testPoints

  if (filter.value.module) {
    filtered = filtered.filter((point) => point.module === filter.value.module)
  }

  if (filter.value.priority) {
    filtered = filtered.filter((point) => point.priority === Number(filter.value.priority))
  }

  // 按模块分组
  const grouped: Record<string, TestPoint[]> = {}
  filtered.forEach((point) => {
    if (!grouped[point.module]) {
      grouped[point.module] = []
    }
    grouped[point.module].push(point)
  })

  return grouped
})

// 优先级文本
const priorityText = (priority: number): string => {
  const map: Record<number, string> = {
    1: '高',
    2: '中',
    3: '低',
  }
  return map[priority] || '中'
}

// 开始分析
const startAnalysis = async () => {
  if (files.value.length === 0) {
    ElMessage.warning('请先上传需求文档或提交URL')
    return
  }

  ElMessageBox.confirm('确认分析所有需求文件？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      await analysisStore.startAnalysis(projectId.value)
    })
    .catch(() => {
      // 取消操作
    })
}

// 生成所有测试用例
const generateAllCases = async () => {
  await caseStore.generateCases(projectId.value)
  if (caseStore.generateStatus === 'success') {
    ElMessage.success('测试用例生成成功')
    router.push(`/case/list/${projectId.value}`)
  }
}

// 生成选中测试用例
const generateSelectedCases = async () => {
  if (selectedPoints.value.length === 0) {
    ElMessage.warning('请先选择测试点')
    return
  }

  await caseStore.generateCases(projectId.value, selectedPoints.value)
  if (caseStore.generateStatus === 'success') {
    ElMessage.success('测试用例生成成功')
    router.push(`/case/list/${projectId.value}`)
  }
}

// 监听路由变化
watch(
  () => route.params.projectId,
  (newVal) => {
    if (newVal) {
      analysisStore.fetchTestPoints(Number(newVal))
    }
  }
)

// 页面加载时获取测试点
onMounted(() => {
  if (projectId.value) {
    analysisStore.fetchTestPoints(projectId.value)
  }
})
</script>

<style scoped>
.analysis-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.file-list {
  margin: 20px 0;
}

.file-list h3 {
  margin-bottom: 15px;
  font-size: 16px;
  font-weight: 500;
}

.analysis-result {
  margin-top: 20px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.result-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}

.filter-container {
  display: flex;
  align-items: center;
}

.priority-tag {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}

.priority-tag.high {
  background: #fef0f0;
  color: #f56c6c;
}

.priority-tag.medium {
  background: #fdf6ec;
  color: #e6a23c;
}

.priority-tag.low {
  background: #f0f9eb;
  color: #67c23a;
}

.generate-button-container {
  margin-top: 20px;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
</style>
