<template>
  <div class="iteration-panel">
    <div class="iteration-panel-header">
      <span class="panel-title">迭代版本</span>
      <el-button type="primary" size="small" @click="ctx.handleAddIterationWrapper" :disabled="!ctx.resourceList.filterForm.project_id">
        <el-icon><Plus /></el-icon>新建迭代
      </el-button>
    </div>

    <div class="iteration-list" v-if="ctx.resourceList.filterForm.project_id">
      <div class="iteration-card" :class="{ active: ctx.iterationManager.selectedIterationId === null }" @click="ctx.handleSelectIterationAndRefresh(null)">
        <div class="iteration-card-info"><span class="iteration-name">全部</span></div>
      </div>

      <template v-for="(iteration, index) in ctx.safeIterationsArray.value" :key="'panel-' + (iteration?.id ?? index)">
        <div v-if="iteration && iteration.id" class="iteration-card" :class="{ active: ctx.iterationManager.selectedIterationId === iteration.id }" @click="ctx.handleSelectIterationAndRefresh(iteration.id)">
          <div class="iteration-card-info">
            <div class="iteration-name-row">
              <span class="iteration-name" :title="iteration?.name">{{ iteration?.name }}</span>
              <el-tag size="small" class="version-tag">{{ iteration?.version }}</el-tag>
            </div>
            <div class="iteration-stats" v-if="iteration && iteration.id">
              <span class="stat-item" v-if="ctx.getIterationStats(iteration.id).files > 0 || ctx.getIterationStats(iteration.id).prototypes > 0">
                <el-icon><Document /></el-icon>{{ ctx.getIterationStats(iteration.id).files }} 个文档
              </span>
              <span class="stat-item" v-if="ctx.getIterationStats(iteration.id).prototypes > 0">
                <el-icon><Picture /></el-icon>{{ ctx.getIterationStats(iteration.id).prototypes }} 个原型
              </span>
            </div>
            <div class="iteration-meta">
              <el-tag :type="ctx.iterationManager.getIterationStatusType(iteration?.status)" size="small">
                {{ ctx.iterationManager.getIterationStatusText(iteration?.status) }}
              </el-tag>
              <span @click.stop>
                <el-dropdown trigger="click" @command="(cmd: string) => iteration && ctx.handleIterationCommandWrapper(cmd, iteration)">
                  <el-icon class="more-icon"><MoreFilled /></el-icon>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">编辑</el-dropdown-item>
                      <el-dropdown-item command="delete">删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </span>
            </div>
          </div>
        </div>
      </template>

      <div class="iteration-card" :class="{ active: ctx.iterationManager.selectedIterationId === 0 }" @click="ctx.handleSelectIterationAndRefresh(0)">
        <div class="iteration-card-info">
          <div class="iteration-name-row">
            <span class="iteration-name">未分类</span>
            <el-tag size="small" type="info" class="version-tag">无迭代</el-tag>
          </div>
        </div>
      </div>
    </div>

    <div class="iteration-empty" v-if="!ctx.resourceList.filterForm.project_id">
      <el-icon :size="40" color="#c0c4cc"><FolderOpened /></el-icon>
      <p class="empty-text">请先选择一个项目</p>
      <p class="empty-hint">选择项目后将显示迭代列表</p>
    </div>

    <div class="iteration-empty" v-else-if="ctx.safeIterationsArray.value.length === 0">
      <el-icon :size="40" color="#c0c4cc"><Plus /></el-icon>
      <p class="empty-text">该项目暂无迭代</p>
      <p class="empty-hint">创建迭代以更好地组织和管理您的需求文档</p>
      <el-button type="primary" size="small" @click="ctx.handleAddIterationWrapper" style="margin-top: 12px">
        <el-icon><Plus /></el-icon>创建第一个迭代
      </el-button>
    </div>

    <el-dialog v-model="ctx.iterationManager.iterationDialogVisible" :title="ctx.iterationManager.iterationDialogMode === 'add' ? '新建迭代' : '编辑迭代'" width="520px" :close-on-click-modal="false">
      <el-form ref="ctx.iterationFormLocalRef.value" :model="ctx.iterationManager.iterationFormData" :rules="ctx.iterationManager.iterationFormRules" label-width="100px">
        <el-form-item label="迭代名称" prop="name"><el-input v-model="ctx.iterationManager.iterationFormData.name" placeholder="请输入迭代名称" /></el-form-item>
        <el-form-item label="版本号" prop="version"><el-input v-model="ctx.iterationManager.iterationFormData.version" placeholder="如 v1.0" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="ctx.iterationManager.iterationFormData.description" type="textarea" :rows="2" placeholder="迭代描述（可选）" /></el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="ctx.iterationManager.iterationFormData.status" placeholder="请选择状态" style="width: 100%">
            <el-option v-for="option in ITERATION_STATUS_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="ctx.iterationManager.iterationFormData.start_date" type="date" placeholder="选择开始日期" style="width: 100%" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="ctx.iterationManager.iterationFormData.end_date" type="date" placeholder="选择结束日期" style="width: 100%" value-format="YYYY-MM-DD" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ctx.iterationManager.iterationDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="ctx.handleIterationSubmitWrapper" :loading="ctx.iterationManager.isSubmitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus, MoreFilled, FolderOpened, Document, Picture } from '@element-plus/icons-vue'
import { useResourceManage, ITERATION_STATUS_OPTIONS } from '@/composables/requirement/useResourceManage'

const ctx = useResourceManage()
</script>

<style scoped>
.iteration-panel { width: 260px; flex-shrink: 0; background: #fafbfc; border: 1px solid #e4e7ed; display: flex; flex-direction: column; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.04); }
.iteration-panel-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 18px; border-bottom: 1px solid #e4e7ed; background: linear-gradient(180deg,#fff 0%,#fafafa 100%); }
.panel-title { font-size: 15px; font-weight: 600; color: #303133; letter-spacing: 0.5px; }
.iteration-list { flex: 1; overflow-y: auto; padding: 8px; }
.iteration-card { padding: 12px 14px; margin-bottom: 6px; border-radius: 8px; cursor: pointer; border: 1px solid transparent; transition: all 0.25s ease; background: #fff; }
.iteration-card:hover { background: #f5f7fa; border-color: #e4e7ed; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.iteration-card.active { background: linear-gradient(135deg,#ecf5ff 0%,#f0f9ff 100%); border-color: #409eff; box-shadow: 0 2px 12px rgba(64,158,255,0.15); }
.iteration-card-info { display: flex; flex-direction: column; gap: 8px; }
.iteration-name-row { display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.iteration-name { font-size: 14px; font-weight: 500; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.iteration-card.active .iteration-name { color: #409eff; font-weight: 600; }
.version-tag { flex-shrink: 0; font-size: 11px; background: #f0f2f5; border-color: #e4e7ed; }
.iteration-stats { display: flex; gap: 10px; font-size: 11px; color: #909399; margin-top: 2px; }
.stat-item { display: flex; align-items: center; gap: 3px; }
.stat-item .el-icon { font-size: 12px; }
.iteration-meta { display: flex; align-items: center; justify-content: space-between; }
.more-icon { cursor: pointer; color: #909399; font-size: 14px; padding: 2px; border-radius: 4px; transition: all 0.2s; }
.more-icon:hover { color: #409eff; background: #ecf5ff; }
.iteration-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; padding: 30px 20px; color: #909399; }
.empty-text { font-size: 14px; font-weight: 500; margin: 0; color: #606266; }
.empty-hint { font-size: 12px; margin: 0; color: #909399; text-align: center; line-height: 1.5; }
</style>
