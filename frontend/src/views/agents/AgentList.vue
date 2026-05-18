<template>
  <div>
    <div class="page-header">
      <div>
        <h2>Agent 管理</h2>
        <p class="subtitle">智能决策单元，负责思考→行动→观察循环</p>
      </div>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 创建 Agent
      </el-button>
    </div>

    <el-table :data="agents" v-loading="loading" class="data-table">
      <el-table-column prop="name" label="名称" />
      <el-table-column label="绑定Skill数">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ row.skills?.length || 0 }} 个Skill</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="版本">
        <template #default="{ row }"><el-tag size="small">v{{ row.version }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="max_loops" label="最大循环" width="100" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/agents/${row.id}`)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建对话框 -->
    <el-dialog v-model="showCreate" title="创建 Agent" width="700px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="e.g. 客服系统" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="Agent功能描述" />
        </el-form-item>
        <el-form-item label="系统提示词" required>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span />
            <AiGeneratePrompt type="agent" @generated="(val: string) => form.system_prompt = val" />
          </div>
          <el-input v-model="form.system_prompt" type="textarea" :rows="6"
            placeholder="定义Agent的角色、推理规则、可用Skill及适用场景..." />
        </el-form-item>
        <el-form-item label="绑定Skill">
          <div style="display:flex;gap:8px">
            <el-select v-model="form.skill_ids" multiple placeholder="选择Skill" style="flex:1">
              <el-option v-for="s in allSkills" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
            <el-button @click="showCreateSkill = true"><el-icon><Plus /></el-icon> 创建Skill</el-button>
          </div>
        </el-form-item>
        <el-form-item label="模型配置">
          <el-select v-model="form.model_config_id" clearable placeholder="选择模型配置" style="width:100%">
            <el-option v-for="mc in allModelConfigs" :key="mc.id" :label="mc.name" :value="mc.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="最大循环次数">
          <el-input-number v-model="form.max_loops" :min="1" :max="50" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="saving">创建</el-button>
      </template>
    </el-dialog>

    <!-- 创建Skill对话框 -->
    <el-dialog v-model="showCreateSkill" title="创建 Skill" width="600px" destroy-on-close>
      <el-form :model="skillForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="skillForm.name" placeholder="e.g. 用例生成" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="skillForm.description" placeholder="Skill功能描述" />
        </el-form-item>
        <el-form-item label="提示词" required>
          <el-input v-model="skillForm.prompt" type="textarea" :rows="6" placeholder="提示词内容..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateSkill = false">取消</el-button>
        <el-button type="primary" @click="handleCreateSkill" :loading="skillSaving">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { agentApi, skillApi, modelConfigApi } from '@/api'
import AiGeneratePrompt from '@/components/AiGeneratePrompt.vue'

const agents = ref<any[]>([])
const allSkills = ref<any[]>([])
const allModelConfigs = ref<any[]>([])
const loading = ref(false)
const showCreate = ref(false)
const saving = ref(false)
const showCreateSkill = ref(false)
const skillSaving = ref(false)
const form = ref({ name: '', description: '', system_prompt: '', skill_ids: [] as string[], model_config_id: null as string | null, max_loops: 10 })
const skillForm = ref({ name: '', description: '', prompt: '' })

const load = async () => {
  loading.value = true
  try {
    const [ar, sr, mr] = await Promise.all([agentApi.list(), skillApi.list(), modelConfigApi.list()])
    agents.value = ar.data
    allSkills.value = sr.data
    allModelConfigs.value = mr.data
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  saving.value = true
  try {
    await agentApi.create(form.value)
    ElMessage.success('创建成功')
    showCreate.value = false
    form.value = { name: '', description: '', system_prompt: '', skill_ids: [], model_config_id: null, max_loops: 10 }
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row: any) => {
  await ElMessageBox.confirm(`确认删除 Agent "${row.name}"？`, '删除确认', { type: 'warning' })
  await agentApi.delete(row.id)
  ElMessage.success('已删除')
  await load()
}

const handleCreateSkill = async () => {
  skillSaving.value = true
  try {
    const r = await skillApi.create({ ...skillForm.value, tool_ids: [], kb_namespaces: [] })
    ElMessage.success('创建成功')
    showCreateSkill.value = false
    skillForm.value = { name: '', description: '', prompt: '' }
    const sr = await skillApi.list()
    allSkills.value = sr.data
    form.value.skill_ids.push(r.data.id)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    skillSaving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
h2 { font-size: 20px; font-weight: 600; }
.subtitle { color: #94a3b8; font-size: 14px; margin-top: 4px; }
.data-table { background: white; border-radius: 8px; }
</style>
