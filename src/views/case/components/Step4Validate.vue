<template>
  <div class="step-content step-full">
    <div class="step-title">
      <el-icon><List /></el-icon>
      <span>校验提取结果 (共{{ totalDisplayCount }}个)</span>
    </div>
    <div class="step-body">
      <div v-if="selectedRows.length > 0 || testPoints.length > 0" class="batch-toolbar">
        <div v-if="selectedRows.length > 0" class="batch-info">
          <el-alert
            :title="`已选择 ${selectedRows.length} 个测试点`"
            type="info"
            :closable="false"
            show-icon
          />
          <el-button
            type="danger"
            size="small"
            @click="batchDeleteTestPoints"
            :loading="batchDeleting"
          >
            <el-icon><Delete /></el-icon>
            批量删除
          </el-button>
          <el-button size="small" @click="clearSelection">取消选择</el-button>
        </div>
        <div class="action-buttons">
          <el-button type="success" @click="saveToDatabase" :loading="saving">
            <el-icon><Check /></el-icon>
            保存测试点
          </el-button>
          <el-button type="primary" @click="generateTestCases">
            <el-icon><MagicStick /></el-icon>
            进入 AI 生成
          </el-button>
          <el-button @click="goToManagement" :disabled="!currentProjectId">
            <el-icon><List /></el-icon>
            回到测试点管理
          </el-button>
        </div>
      </div>

      <div v-if="paginatedTestPoints.length > 0" class="table-wrapper">
        <el-table
          ref="testPointTable"
          :data="paginatedTestPoints"
          border
          stripe
          highlight-current-row
          @selection-change="handleSelectionChange"
          v-loading="loadingTestPoints"
          empty-text="暂无测试点数据"
          style="width: 100%"
        >
          <el-table-column type="selection" width="50" fixed="left" />
          <el-table-column prop="id" label="ID" width="72" />
          <el-table-column prop="module" label="模块" width="120" />
          <el-table-column prop="function" label="功能" width="120" />
          <el-table-column prop="point" label="测试点描述" min-width="200" />
          <el-table-column prop="priority" label="优先级" width="100">
            <template #default="scope">
              <el-tag :type="getPriorityTagType(scope.row.priority)">
                {{ getPriorityLabel(scope.row.priority) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button
                type="primary"
                size="small"
                @click="editTestPoint(row)"
                :loading="updating"
              >
                <el-icon><Edit /></el-icon>编辑
              </el-button>
              <el-popconfirm title="确定删除此测试点？" @confirm="deleteTestPoint(row)">
                <template #reference>
                  <el-button type="danger" size="small" :disabled="deleting">
                    <el-icon><Delete /></el-icon>删除
                  </el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <div
          class="pagination-wrapper"
          v-if="
            (savedFromDb && dbTotal > pageSize) || (!savedFromDb && testPoints.length > pageSize)
          "
        >
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="savedFromDb ? dbTotal : testPoints.length"
            layout="total, prev, pager, next, jumper"
            @current-change="handlePageChange"
          />
        </div>
      </div>

      <div v-else class="empty-hint">
        <el-empty description="暂无测试点数据，请先提取测试点" :image-size="120">
          <template #image>
            <div class="empty-icon">
              <el-icon :size="80" color="#C0C4CC"><Document /></el-icon>
            </div>
          </template>
        </el-empty>
      </div>
    </div>
  </div>

  <!-- 编辑测试点对话框 -->
  <el-dialog v-model="dialogVisible" title="编辑测试点" width="600px" destroy-on-close>
    <el-form :model="editForm" label-width="120px">
      <el-form-item label="模块" required>
        <el-input v-model="editForm.module" placeholder="如：登录模块" />
      </el-form-item>
      <el-form-item label="功能">
        <el-input v-model="editForm.function" placeholder="如：密码验证" />
      </el-form-item>
      <el-form-item label="测试点描述" required>
        <el-input
          v-model="editForm.point"
          type="textarea"
          :rows="4"
          placeholder="请输入测试点描述"
        />
      </el-form-item>
      <el-form-item label="优先级" required>
        <el-select v-model="editForm.priority" placeholder="请选择优先级">
          <el-option :value="1" label="高" />
          <el-option :value="2" label="中" />
          <el-option :value="3" label="低" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTestPoint">保存</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { useTestPointExtract } from '@/composables/useTestPointExtract'

const {
  totalDisplayCount,
  selectedRows,
  testPoints,
  batchDeleting,
  saving,
  currentProjectId,
  paginatedTestPoints,
  loadingTestPoints,
  dbTotal,
  pageSize,
  savedFromDb,
  currentPage,
  updating,
  deleting,
  dialogVisible,
  editForm,
  handleSelectionChange,
  clearSelection,
  batchDeleteTestPoints,
  saveToDatabase,
  generateTestCases,
  goToManagement,
  getPriorityTagType,
  getPriorityLabel,
  editTestPoint,
  saveTestPoint,
  deleteTestPoint,
  handlePageChange,
} = useTestPointExtract()
</script>
