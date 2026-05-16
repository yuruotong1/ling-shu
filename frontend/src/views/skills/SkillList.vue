<template>
  <div>
    <div class="page-header">
      <div>
        <h2>Skill 管理</h2>
        <p class="subtitle">Agent的内部执行单元，封装提示词和工具调用</p>
      </div>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 创建 Skill
      </el-button>
    </div>

    <el-table :data="skills" v-loading="loading" class="data-table">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column label="绑定工具">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ row.tools?.length || 0 }} 个工具</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="80">
        <template #default="{ row }"><el-tag size="small">v{{ row.version }}</el-tag></template>
      </el-table-column>
      <el-table-column label="评估得分" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.eval_score != null" :type="row.eval_score >= 0.7 ? 'success' : 'danger'" size="small">
            {{ (row.eval_score * 100).toFixed(0) }}分
          </el-tag>
          <span v-else style="color:#94a3b8">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/skills/${row.id}`)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="创建 Skill" width="800px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="e.g. 用例生成" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="Skill功能描述（供Agent决策调用）" />
        </el-form-item>
        <el-form-item label="提示词" required>
          <el-input v-model="form.prompt" type="textarea" :rows="10"
            placeholder="# Skill名称&#10;&#10;你是一个专业的...&#10;&#10;## 规则&#10;- ..." />
        </el-form-item>
        <el-form-item label="绑定工具">
          <el-select v-model="form.bound_items" multiple placeholder="选择工具或知识库（可选）" style="width:100%">
            <el-option-group v-if="allTools.length" label="注册工具">
              <el-option v-for="t in allTools" :key="t.id" :label="t.name" :value="t.id" />
            </el-option-group>
            <el-option-group v-if="allNamespaces.length" label="知识库">
              <el-option v-for="ns in allNamespaces" :key="'kb:'+ns" :label="ns" :value="'kb:'+ns" />
            </el-option-group>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="saving">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { skillApi, toolApi, kbApi } from '@/api'

const skills = ref<any[]>([])
const allTools = ref<any[]>([])
const allNamespaces = ref<string[]>([])
const loading = ref(false)
const showCreate = ref(false)
const saving = ref(false)
const form = ref({ name: '', description: '', prompt: '', bound_items: [] as string[] })

const load = async () => {
  loading.value = true
  try {
    const [sr, tr, nsr] = await Promise.all([skillApi.list(), toolApi.list(), kbApi.namespaces()])
    skills.value = sr.data
    allTools.value = tr.data
    allNamespaces.value = nsr.data || []
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  saving.value = true
  try {
    const tool_ids = form.value.bound_items.filter(v => !v.startsWith('kb:'))
    const kb_namespaces = form.value.bound_items.filter(v => v.startsWith('kb:')).map(v => v.slice(3))
    await skillApi.create({ ...form.value, tool_ids, kb_namespaces })
    ElMessage.success('创建成功')
    showCreate.value = false
    form.value = { name: '', description: '', prompt: '', bound_items: [] }
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row: any) => {
  await ElMessageBox.confirm(`确认删除 Skill "${row.name}"？`, '删除确认', { type: 'warning' })
  await skillApi.delete(row.id)
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
