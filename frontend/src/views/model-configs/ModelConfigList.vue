<template>
  <div>
    <div class="page-header">
      <div>
        <h2>模型配置</h2>
        <p class="subtitle">配置LLM供应商，支持OpenAI/Azure/Anthropic/自定义endpoint</p>
      </div>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon> 添加模型
      </el-button>
    </div>

    <el-row :gutter="16">
      <el-col :span="8" v-for="mc in configs" :key="mc.id">
        <el-card class="mc-card">
          <div class="mc-header">
            <span class="mc-name">{{ mc.name }}</span>
            <el-tag size="small" :type="mc.is_active ? 'success' : 'info'">{{ mc.is_active ? '启用' : '禁用' }}</el-tag>
          </div>
          <div class="mc-info">
            <div><b>供应商：</b>{{ mc.provider }}</div>
            <div><b>默认模型：</b>{{ mc.default_model }}</div>
            <div class="mc-endpoint"><b>Endpoint：</b>{{ mc.endpoint }}</div>
          </div>
          <div class="mc-actions">
            <el-button size="small" @click="handleTest(mc)" :loading="testingId === mc.id">测试连接</el-button>
            <el-button size="small" @click="openEdit(mc)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(mc)">删除</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="showCreate" :title="editingId ? '编辑模型配置' : '添加模型配置'" width="600px" @close="resetForm">
      <el-form :model="form" label-width="120px">
        <el-form-item label="配置名称" required>
          <el-input v-model="form.name" placeholder="e.g. OpenAI-GPT4" />
        </el-form-item>
        <el-form-item label="供应商">
          <el-select v-model="form.provider" style="width:100%">
            <el-option label="OpenAI" value="openai" />
            <el-option label="Azure OpenAI" value="azure" />
            <el-option label="Anthropic" value="anthropic" />
            <el-option label="自定义endpoint" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Endpoint" required>
          <el-input v-model="form.endpoint" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <div style="width:100%">
            <div v-if="editingId && hasExistingKey" style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
              <el-tag type="success" size="small">已设置</el-tag>
              <span style="font-size:12px;color:#6b7280;">当前：{{ apiKeyPreview }}，留空则保留，填写则替换</span>
            </div>
            <el-input v-model="form.api_key" type="password" show-password :placeholder="editingId && hasExistingKey ? '输入新 Key 以替换' : 'sk-...'" />
          </div>
        </el-form-item>
        <el-form-item label="默认模型" required>
          <el-input v-model="form.default_model" placeholder="gpt-4o / claude-3-5-sonnet-..." />
        </el-form-item>
        <el-form-item label="temperature">
          <el-slider v-model="form.default_params.temperature" :min="0" :max="2" :step="0.1" show-input />
        </el-form-item>
        <el-form-item label="max_tokens">
          <el-input-number v-model="form.default_params.max_tokens" :min="100" :max="32000" :step="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modelConfigApi } from '@/api'

const EMPTY_FORM = () => ({ name: '', provider: 'openai', endpoint: 'https://api.openai.com/v1', api_key: '', default_model: 'gpt-4o', default_params: { temperature: 0.7, max_tokens: 2000 } })

const configs = ref<any[]>([])
const loading = ref(false)
const showCreate = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const testingId = ref<string | null>(null)
const hasExistingKey = ref(false)
const apiKeyPreview = ref('')
const form = ref(EMPTY_FORM())

const resetForm = () => {
  editingId.value = null
  hasExistingKey.value = false
  apiKeyPreview.value = ''
  form.value = EMPTY_FORM()
}

const load = async () => {
  loading.value = true
  try {
    const r = await modelConfigApi.list()
    configs.value = r.data
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  resetForm()
  showCreate.value = true
}

const openEdit = (mc: any) => {
  editingId.value = mc.id
  hasExistingKey.value = !!mc.has_api_key
  apiKeyPreview.value = mc.api_key_preview || ''
  form.value = {
    name: mc.name,
    provider: mc.provider,
    endpoint: mc.endpoint,
    api_key: '',
    default_model: mc.default_model,
    default_params: { ...mc.default_params },
  }
  showCreate.value = true
}

const handleSave = async () => {
  saving.value = true
  try {
    // 明确构造 payload，只包含后端需要的字段
    const base = {
      name: form.value.name,
      provider: form.value.provider,
      endpoint: form.value.endpoint,
      default_model: form.value.default_model,
      default_params: form.value.default_params,
    }
    if (editingId.value) {
      // 编辑：只有用户填了新 key 才更新，否则保留原 key
      const payload: any = { ...base }
      if (form.value.api_key) payload.api_key = form.value.api_key
      await modelConfigApi.update(editingId.value, payload)
    } else {
      // 新建：直接带上 api_key（可为空）
      await modelConfigApi.create({ ...base, api_key: form.value.api_key || undefined })
    }
    ElMessage.success('保存成功')
    showCreate.value = false
    resetForm()
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const handleTest = async (mc: any) => {
  testingId.value = mc.id
  try {
    const r = await modelConfigApi.test(mc.id)
    if (r.data.success) {
      ElMessage.success(`连接成功，模型回复：${r.data.response || '(空)'}`)
    } else {
      ElMessage.error(r.data.error || '连接失败')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message || '请求异常')
  } finally {
    testingId.value = null
  }
}

const handleDelete = async (mc: any) => {
  await ElMessageBox.confirm(`确认删除模型配置 "${mc.name}"？`, '删除确认', { type: 'warning' })
  await modelConfigApi.delete(mc.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
h2 { font-size: 20px; font-weight: 600; }
.subtitle { color: #94a3b8; font-size: 14px; margin-top: 4px; }
.mc-card { margin-bottom: 16px; }
.mc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.mc-name { font-size: 16px; font-weight: 600; }
.mc-info { font-size: 13px; line-height: 1.8; color: #374151; }
.mc-endpoint { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mc-actions { margin-top: 12px; }
</style>
