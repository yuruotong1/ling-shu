<template>
  <div>
    <div class="page-header">
      <div>
        <h2>评估器</h2>
        <p class="subtitle">定义"什么叫好"，量化Agent/Skill输出质量</p>
      </div>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 创建评估器
      </el-button>
    </div>

    <el-table :data="evaluators" v-loading="loading" class="data-table">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column label="评分范围" width="100">
        <template #default="{ row }">{{ row.score_range[0] }} ~ {{ row.score_range[1] }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" :title="editingId ? '编辑评估器' : '创建评估器'" width="700px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="e.g. 用例质量评估" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" />
        </el-form-item>
        <el-form-item label="评估提示词" required>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span />
            <div style="display:flex;gap:8px">
              <AiGeneratePrompt type="evaluator" @generated="(val: string) => form.prompt = val" />
              <el-button size="small" type="warning" @click="showGenEv = true">🤖 AI 一键生成</el-button>
            </div>
          </div>
          <el-input v-model="form.prompt" type="textarea" :rows="8"
            placeholder="你是一个评审专家。请根据以下标准对输出评分：&#10;1. 准确性：...&#10;2. 完整性：..." />
        </el-form-item>
        <el-form-item label="评分区间">
          <el-input-number v-model="form.score_range[0]" :min="0" :max="100" style="width:120px" /> 到
          <el-input-number v-model="form.score_range[1]" :min="0" :max="100" style="width:120px;margin-left:8px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- AI 一键生成评估器 -->
    <el-dialog v-model="showGenEv" title="AI 一键生成评估器" width="650px">
      <el-form label-width="100px">
        <el-form-item label="需求描述">
          <el-input v-model="genEvDesc" type="textarea" :rows="4"
            placeholder="例如：我想评估测试用例的质量，维度包括覆盖度、可执行性、完整性，评分 0-1 分" />
        </el-form-item>
        <el-form-item v-if="genEvResult">
          <el-alert type="success" :closable="false">
            <template #title>AI 已生成以下配置，点击「应用」即可填充</template>
          </el-alert>
          <el-descriptions :column="1" size="small" border style="margin-top:8px">
            <el-descriptions-item label="名称">{{ genEvResult.name }}</el-descriptions-item>
            <el-descriptions-item label="描述">{{ genEvResult.description }}</el-descriptions-item>
            <el-descriptions-item label="评分区间">{{ genEvResult.score_range?.join(' ~ ') }}</el-descriptions-item>
          </el-descriptions>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenEv = false">关闭</el-button>
        <el-button v-if="genEvResult" type="primary" @click="applyGenEv">应用</el-button>
        <el-button type="warning" :loading="genEvLoading" @click="doGenEv">🤖 AI 生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { evaluatorApi, aiGenerateApi } from '@/api'
import AiGeneratePrompt from '@/components/AiGeneratePrompt.vue'

const evaluators = ref<any[]>([])
const loading = ref(false)
const showCreate = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref({ name: '', description: '', prompt: '', score_range: [0, 1] as number[] })

// AI 一键生成评估器
const showGenEv = ref(false)
const genEvDesc = ref('')
const genEvResult = ref<any>(null)
const genEvLoading = ref(false)

const load = async () => {
  loading.value = true
  try {
    const r = await evaluatorApi.list()
    evaluators.value = r.data
  } finally {
    loading.value = false
  }
}

const openEdit = (ev: any) => {
  editingId.value = ev.id
  form.value = { ...ev }
  showCreate.value = true
}

const handleSave = async () => {
  saving.value = true
  try {
    if (editingId.value) {
      await evaluatorApi.update(editingId.value, form.value)
    } else {
      await evaluatorApi.create(form.value)
    }
    ElMessage.success('保存成功')
    showCreate.value = false
    editingId.value = null
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const doGenEv = async () => {
  if (!genEvDesc.value.trim()) {
    ElMessage.warning('请先描述评估需求')
    return
  }
  genEvLoading.value = true
  genEvResult.value = null
  try {
    const r = await aiGenerateApi.evaluator({ description: genEvDesc.value })
    genEvResult.value = r.data.evaluator
    ElMessage.success('AI 已生成评估器配置')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    genEvLoading.value = false
  }
}

const applyGenEv = () => {
  const ev = genEvResult.value
  if (!ev) return
  form.value.name = ev.name || form.value.name
  form.value.description = ev.description || form.value.description
  form.value.prompt = ev.prompt || form.value.prompt
  if (ev.score_range && Array.isArray(ev.score_range) && ev.score_range.length >= 2) {
    form.value.score_range = [ev.score_range[0], ev.score_range[1]]
  }
  showGenEv.value = false
  genEvDesc.value = ''
  genEvResult.value = null
  ElMessage.success('已填充到表单')
}

const handleDelete = async (ev: any) => {
  await ElMessageBox.confirm(`确认删除评估器 "${ev.name}"？`, '删除确认', { type: 'warning' })
  await evaluatorApi.delete(ev.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
h2 { font-size: 20px; font-weight: 600; }
.subtitle { color: #94a3b8; font-size: 14px; margin-top: 4px; }
.data-table { background: white; border-radius: 8px; }
</style>
