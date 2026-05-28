<template>
  <div class="report-table">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>测试用例详情</span>
          <el-dropdown trigger="click">
            <el-button type="primary" size="small">
              导出 <el-icon class="el-icon--right"><arrow-down /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="exportExcel">导出Excel</el-dropdown-item>
                <el-dropdown-item @click="exportCSV">导出CSV</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </template>

      <el-table
        :data="testCases"
        style="width: 100%"
        border
        stripe
        :empty-text="'暂无测试用例数据'"
      >
        <el-table-column type="index" label="序号" width="80" />
        <el-table-column prop="test_case_id" label="用例ID" width="100" />
        <el-table-column prop="test_case_name" label="用例名称" min-width="200" />
        <el-table-column prop="status" label="执行状态" width="120">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="expected_result" label="预期结果" min-width="200" />
        <el-table-column prop="actual_result" label="实际结果" min-width="200" />
        <el-table-column prop="start_time" label="开始时间" width="180" />
        <el-table-column prop="end_time" label="结束时间" width="180" />
        <el-table-column label="操作" width="120">
          <template #default="scope">
            <el-button type="primary" size="small" @click="viewTestCase(scope.row)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination" v-if="total > 0">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { TestCaseResult } from '@/api/report'
import { ArrowDown } from '@element-plus/icons-vue'
import { testCaseViewApi } from '@/api/testCaseView'
import { downloadFromResponse, parseBlobError } from '@/utils/download'
import type { TagType } from '@/types/element-plus'

const props = defineProps<{
  testCases: TestCaseResult[]
  total: number
}>()

const emit = defineEmits<{
  (e: 'pageChange', page: number, pageSize: number): void
}>()

const router = useRouter()
const page = ref(1)
const pageSize = ref(10)

// 获取状态类型
const getStatusType = (status: string): TagType => {
  const statusMap: Record<string, TagType> = {
    passed: 'success',
    failed: 'danger',
    blocked: 'warning',
  }
  return statusMap[status] || 'info'
}

// 处理分页
const handleSizeChange = (size: number) => {
  pageSize.value = size
  emit('pageChange', page.value, size)
}

const handleCurrentChange = (current: number) => {
  page.value = current
  emit('pageChange', current, pageSize.value)
}

// 查看用例详情
const viewTestCase = (testCase: TestCaseResult) => {
  router.push({ path: `/home/case/detail/${testCase.test_case_id}` })
}

// 导出Excel
const exportExcel = async () => {
  const ids = props.testCases.map((c) => c.test_case_id).filter(Boolean)
  if (ids.length === 0) {
    ElMessage.warning('暂无可导出的用例')
    return
  }
  try {
    const resp = await testCaseViewApi.exportToFunctionalExcel(ids)
    downloadFromResponse(resp, `测试用例_${new Date().toISOString().slice(0, 10)}.xlsx`)
    ElMessage.success(`已导出 ${ids.length} 条用例`)
  } catch (err) {
    const msg = await parseBlobError(err, '导出失败，请稍后重试')
    ElMessage.error(msg)
  }
}

const exportCSV = () => {
  ElMessage.info('CSV 导出功能即将上线')
}
</script>

<style scoped>
.report-table {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
