<template>
  <el-dialog v-model="ctx.quickVerifyVisible.value" title="快速验证" width="500px">
    <p>选择要验证的步骤：</p>
    <el-checkbox-group v-model="ctx.selectedVerifySteps.value">
      <div v-if="ctx.technicalViewData.value" class="verify-step-list">
        <el-checkbox
          v-for="step in ctx.technicalViewData.value.steps"
          :key="step.step_number"
          :value="step.step_number"
          :label="step.step_number"
        >
          步骤 {{ step.step_number }}: {{ step.display_action || step.description || step.action?.substring(0, 50) || '-' }}{{ (step.display_action || step.description || step.action || '').length > 50 ? '...' : '' }}
        </el-checkbox>
      </div>
    </el-checkbox-group>
    <template #footer>
      <el-button @click="ctx.quickVerifyVisible.value = false">取消</el-button>
      <el-button type="primary" @click="ctx.executeQuickVerify" :loading="ctx.quickVerifyLoading.value">开始验证</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="ctx.versionHistoryVisible.value" title="版本历史" width="700px">
    <div v-if="ctx.versionLoading.value" class="loading-container">
      <el-skeleton :rows="5" animated />
    </div>
    <div v-else>
      <el-table :data="ctx.versionList.value" style="width: 100%" border stripe>
        <el-table-column label="版本号" width="80" align="center">
          <template #default="{ row }"><el-tag size="small">v{{ row.version_number }}</el-tag></template>
        </el-table-column>
        <el-table-column label="修改类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.change_type === 'correction' ? 'warning' : row.change_type === 'rollback' ? 'info' : ''" size="small">
              {{ row.change_type === 'correction' ? '纠正' : row.change_type === 'update' ? '编辑' : row.change_type === 'rollback' ? '回滚' : row.change_type === 'create' ? '创建' : row.change_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="修改说明" min-width="200">
          <template #default="{ row }">{{ row.change_description || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作人" width="100">
          <template #default="{ row }">{{ row.operator_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="修改时间" width="160">
          <template #default="{ row }">{{ row.created_at ? new Date(row.created_at).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-popconfirm title="确定要回滚到此版本吗？当前数据将被覆盖。" confirm-button-text="确定" cancel-button-text="取消" @confirm="ctx.handleRollback(row)">
              <template #reference>
                <el-button size="small" type="warning" :loading="ctx.rollbackLoading.value">回滚</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="version-pagination">
        <el-pagination v-model:current-page="ctx.versionPage.value" :page-size="20" :total="ctx.versionTotal.value" layout="total, prev, pager, next" @current-change="ctx.fetchVersionHistory" />
      </div>
    </div>
  </el-dialog>

  <el-dialog v-model="ctx.addLocatorVisible.value" title="添加元素定位" width="500px">
    <el-form :model="ctx.addLocatorForm.value" label-width="100px">
      <el-form-item label="CSS选择器">
        <el-input v-model="ctx.addLocatorForm.value.css_selector" placeholder="例如: #username, .login-btn" />
      </el-form-item>
      <el-form-item label="XPath">
        <el-input v-model="ctx.addLocatorForm.value.xpath" placeholder="例如: //input[@name='username']" />
      </el-form-item>
      <el-form-item label="AI坐标">
        <el-input v-model="ctx.addLocatorForm.value.ai_coordinate" placeholder="例如: 100,200" />
      </el-form-item>
      <el-form-item label="定位方式">
        <el-radio-group v-model="ctx.addLocatorForm.value.locator_type">
          <el-radio value="css">CSS选择器</el-radio>
          <el-radio value="xpath">XPath</el-radio>
          <el-radio value="ai">AI坐标</el-radio>
        </el-radio-group>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="ctx.addLocatorVisible.value = false">取消</el-button>
      <el-button type="primary" @click="ctx.saveAddLocator" :loading="ctx.addLocatorLoading.value">保存</el-button>
    </template>
  </el-dialog>

  <BatchLocatorDialog ref="batchLocatorRef" :project-id="ctx.caseItem.value?.project_id ?? 0" />
</template>

<script setup lang="ts">
import { watch, ref } from 'vue'
import { useCaseDetail } from '@/composables/case/useCaseDetail'
import BatchLocatorDialog from '../BatchLocatorDialog.vue'

const ctx = useCaseDetail()
const batchLocatorRef = ref<InstanceType<typeof BatchLocatorDialog>>()

watch(() => ctx.batchLocatorVisible.value, (val) => {
    if (val) {
        batchLocatorRef.value?.open([])
        ctx.batchLocatorVisible.value = false
    }
})
</script>
