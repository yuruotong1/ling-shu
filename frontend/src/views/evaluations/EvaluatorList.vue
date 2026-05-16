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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { evaluatorApi } from '@/api'

const evaluators = ref<any[]>([])
const loading = ref(false)
const showCreate = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref({ name: '', description: '', prompt: '', score_range: [0, 1] as number[] })

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
