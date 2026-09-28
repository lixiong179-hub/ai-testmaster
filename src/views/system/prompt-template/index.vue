<template>
  <div class="prompt-template-management">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <h2>Prompt 模板管理</h2>
          <el-button type="primary" :icon="Plus" @click="openRegisterDialog()">
            注册新版本
          </el-button>
        </div>
      </template>

      <div v-loading="loading" class="split-layout">
        <!-- 左侧：Prompt Key 列表 -->
        <div class="key-panel">
          <div class="panel-title">Prompt Key 列表</div>
          <el-input
            v-model="filterText"
            placeholder="搜索 Key"
            clearable
            size="small"
            class="filter-input"
          />
          <div class="key-list">
            <div
              v-for="reg in filteredRegistries"
              :key="reg.key"
              class="key-item"
              :class="{ active: reg.key === selectedKey }"
              @click="selectKey(reg.key)"
            >
              <div class="key-name" :title="reg.key">{{ reg.key }}</div>
              <div class="key-meta">
                <el-tag size="small" type="info">{{ reg.versions.length }} 版本</el-tag>
                <el-tag v-if="reg.defaultVersion" size="small" type="success">
                  默认 v{{ reg.defaultVersion.prompt_version }}
                </el-tag>
              </div>
            </div>
            <el-empty
              v-if="filteredRegistries.length === 0"
              description="暂无 Prompt 模板"
              :image-size="60"
            />
          </div>
        </div>

        <!-- 右侧：版本详情 -->
        <div class="detail-panel">
          <template v-if="currentRegistry">
            <div class="detail-header">
              <div class="detail-title">
                <span class="title-text">{{ currentRegistry.key }}</span>
                <el-tag v-if="currentRegistry.defaultVersion" type="success" size="small">
                  当前默认 v{{ currentRegistry.defaultVersion.prompt_version }}
                </el-tag>
                <el-tag v-else type="warning" size="small">未设默认</el-tag>
              </div>
              <el-button
                type="primary"
                size="small"
                :icon="Plus"
                @click="openRegisterDialog(currentRegistry.key)"
              >
                为此 Key 注册新版本
              </el-button>
            </div>

            <div v-loading="actionLoading" class="version-list">
              <el-card
                v-for="ver in currentVersions"
                :key="ver.id"
                class="version-card"
                :class="{ 'is-default': ver.is_default, 'is-disabled': !ver.enabled }"
                shadow="hover"
              >
                <div class="version-head">
                  <div class="version-head-left">
                    <span class="version-no">v{{ ver.prompt_version }}</span>
                    <el-tag v-if="ver.is_default" type="success" size="small">默认</el-tag>
                    <el-tag v-if="!ver.enabled" type="danger" size="small">已禁用</el-tag>
                    <el-tooltip :content="ver.prompt_hash" placement="top">
                      <span class="version-hash">SHA: {{ shortHash(ver.prompt_hash) }}</span>
                    </el-tooltip>
                    <el-tag
                      v-if="hasSameHashElsewhere(ver)"
                      size="small"
                      type="warning"
                      effect="plain"
                    >
                      与其他版本内容相同
                    </el-tag>
                  </div>
                  <span class="version-time">{{ formatTime(ver.created_at) }}</span>
                </div>

                <div v-if="ver.description" class="version-desc">{{ ver.description }}</div>

                <div class="version-content">
                  <pre v-if="isExpanded(ver.id) || !needCollapse(ver.content)">{{ ver.content }}</pre>
                  <pre v-else>{{ getPreview(ver.content) }}</pre>
                  <el-button
                    v-if="needCollapse(ver.content)"
                    link
                    type="primary"
                    size="small"
                    @click="toggleExpand(ver.id)"
                  >
                    {{ isExpanded(ver.id) ? '收起' : '展开全部' }}
                  </el-button>
                </div>

                <div class="version-actions">
                  <el-button
                    size="small"
                    type="primary"
                    :disabled="ver.is_default || !ver.enabled"
                    @click="setDefault(ver)"
                  >
                    设为默认
                  </el-button>
                  <el-button
                    size="small"
                    :disabled="ver.is_default"
                    @click="rollback(ver)"
                  >
                    回滚到此版本
                  </el-button>
                </div>
              </el-card>
            </div>
          </template>

          <el-empty v-else description="请选择左侧 Prompt Key 查看版本详情" />
        </div>
      </div>
    </el-card>

    <!-- 注册新版本对话框 -->
    <el-dialog
      v-model="registerDialogVisible"
      title="注册新版本"
      width="700px"
      destroy-on-close
    >
      <el-form
        :ref="setRegisterFormRef"
        :model="registerForm"
        :rules="registerRules"
        label-width="100px"
      >
        <el-form-item label="Prompt Key" prop="prompt_key">
          <el-input
            v-model="registerForm.prompt_key"
            placeholder="如 case_generation、locator_optimize"
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="registerForm.description"
            type="textarea"
            :rows="2"
            placeholder="版本描述（选填）"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input
            v-model="registerForm.content"
            type="textarea"
            :rows="12"
            placeholder="请输入 Prompt 内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="registerDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="actionLoading" @click="submitRegister">
            注册
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import type { FormInstance } from 'element-plus'
import { usePromptTemplate } from './usePromptTemplate'

const {
  loading,
  actionLoading,
  filterText,
  filteredRegistries,
  selectedKey,
  currentRegistry,
  currentVersions,
  registerDialogVisible,
  registerFormRef,
  registerForm,
  registerRules,
  selectKey,
  toggleExpand,
  isExpanded,
  needCollapse,
  getPreview,
  openRegisterDialog,
  submitRegister,
  setDefault,
  rollback,
  formatTime,
  shortHash,
  hasSameHashElsewhere,
} = usePromptTemplate()

const setRegisterFormRef = (el: unknown): void => {
  registerFormRef.value = (el as FormInstance | null) ?? null
}
</script>

<style scoped>
.prompt-template-management { padding: 20px; }
.page-card { margin-bottom: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header h2 { margin: 0; font-size: 18px; color: #303133; }

.split-layout { display: flex; gap: 16px; min-height: 520px; }

/* 左侧 Key 列表面板 */
.key-panel {
  width: 280px; flex-shrink: 0; border: 1px solid #ebeef5; border-radius: 4px;
  display: flex; flex-direction: column; overflow: hidden;
}
.panel-title {
  padding: 10px 12px; font-weight: 600; font-size: 14px; color: #303133;
  border-bottom: 1px solid #ebeef5; background: #fafafa;
}
.filter-input { padding: 8px 12px; }
.key-list { flex: 1; overflow-y: auto; padding: 4px 8px; }
.key-item { padding: 8px 10px; border-radius: 4px; cursor: pointer; transition: background 0.2s; }
.key-item:hover { background: #f5f7fa; }
.key-item.active { background: #ecf5ff; }
.key-name {
  font-size: 14px; color: #303133;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.key-meta { margin-top: 4px; display: flex; gap: 6px; flex-wrap: wrap; }

/* 右侧版本详情面板 */
.detail-panel { flex: 1; min-width: 0; overflow-y: auto; }
.detail-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px; flex-wrap: wrap; gap: 8px;
}
.detail-title { display: flex; align-items: center; gap: 8px; }
.title-text { font-size: 16px; font-weight: 600; color: #303133; }
.version-list { display: flex; flex-direction: column; gap: 12px; }

.version-card { border-left: 3px solid transparent; }
.version-card.is-default { border-left-color: #67c23a; }
.version-card.is-disabled { opacity: 0.7; }
.version-head {
  display: flex; justify-content: space-between; align-items: center;
  gap: 8px; flex-wrap: wrap;
}
.version-head-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.version-no { font-weight: 600; color: #303133; }
.version-hash, .version-time { font-size: 12px; color: #909399; }
.version-hash { font-family: monospace; }
.version-desc { margin-top: 6px; font-size: 13px; color: #606266; }

.version-content { margin-top: 8px; }
.version-content pre {
  margin: 0 0 8px 0; padding: 8px 10px; background: #f5f7fa; border-radius: 4px;
  font-size: 12px; color: #303133; white-space: pre-wrap; word-break: break-word;
  max-height: 320px; overflow-y: auto;
}
.version-actions { display: flex; gap: 8px; }
.dialog-footer { width: 100%; display: flex; justify-content: flex-end; gap: 10px; }

@media (max-width: 768px) {
  .prompt-template-management { padding: 10px; }
  .card-header { flex-direction: column; align-items: flex-start; gap: 10px; }
  .split-layout { flex-direction: column; }
  .key-panel { width: 100%; max-height: 240px; }
}
</style>
