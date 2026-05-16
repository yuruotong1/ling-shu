<template>
  <div>
    <div class="page-header">
      <div>
        <h2>实验对比</h2>
        <p class="subtitle">运行评估实验，对比不同版本效果</p>
      </div>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 创建实验
      </el-button>
    </div>

    <el-table :data="experiments" v-loading="loading" class="data-table">
      <el-table-column prop="name" label="实验名称" />
      <el-table-column label="评估目标">
        <template #default="{ row }">
          <el-tag size="small" :type="row.target_type === 'agent' ? 'primary' : 'warning'">{{ row.target_type }}</el-tag>
          {{ row.target_name }}
          <span v-if="row.target_version">v{{ row.target_version }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="平均得分" width="100">
        <template #default="{ row }">
          <span v-if="row.avg_score != null" :class="row.avg_score >= 0.7 ? 'score-good' : 'score-bad'">
            {{ (row.avg_score * 100).toFixed(1) }}分
          </span>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="通过率" width="100">
        <template #default="{ row }">
          {{ row.pass_rate != null ? (row.pass_rate * 100).toFixed(1) + '%' : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="样本数" width="100">
        <template #default="{ row }">{{ row.total_items }} / {{ row.failed_items }}失败</template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="handleRun(row)" :disabled="row.status === 'running'">运行</el-button>
          <el-button size="small" @click="$router.push(`/experiments/${row.id}`)">详情</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="创建实验" width="600px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="实验名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="评估目标类型">
          <el-select v-model="form.target_type" style="width:100%" @change="form.target_name = ''">
            <el-option label="Agent" value="agent" />
            <el-option label="Skill" value="skill" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标名称" required>
          <el-select v-model="form.target_name" style="width:100%" placeholder="请选择">
            <el-option v-if="form.target_type === 'agent'" v-for="a in agents" :key="a.id" :label="a.name" :value="a.name" />
            <el-option v-if="form.target_type === 'skill'" v-for="s in skills" :key="s.id" :label="s.name" :value="s.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标版本">
          <el-input-number v-model="form.target_version" :min="1" placeholder="留空=最新版本" />
        </el-form-item>
        <el-form-item label="评估器" required>
          <el-select v-model="form.evaluator_id" style="width:100%">
            <el-option v-for="ev in evaluators" :key="ev.id" :label="ev.name" :value="ev.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="评估集" required>
          <el-select v-model="form.eval_set_id" style="width:100%">
            <el-option v-for="s in evalSets" :key="s.id" :label="`${s.name}（${s.item_count}条）`" :value="s.id" />
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
import { experimentApi, evaluatorApi, evalSetApi, agentApi, skillApi } from '@/api'

const experiments = ref<any[]>([])
const evaluators = ref<any[]>([])
const evalSets = ref<any[]>([])
const agents = ref<any[]>([])
const skills = ref<any[]>([])
const loading = ref(false)
const showCreate = ref(false)
const saving = ref(false)
const form = ref({ name: '', target_type: 'agent', target_name: '', target_version: null as number | null, evaluator_id: '', eval_set_id: '' })

const statusType = (s: string) => ({ pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }[s] || 'info')

const load = async () => {
  loading.value = true
  try {
    const [er, evr, sr, ar, skr] = await Promise.all([
      experimentApi.list(), evaluatorApi.list(), evalSetApi.list(), agentApi.list(), skillApi.list()
    ])
    experiments.value = er.data
    evaluators.value = evr.data
    evalSets.value = sr.data
    agents.value = ar.data
    skills.value = skr.data
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  saving.value = true
  try {
    const data = { ...form.value }
    if (!data.target_version) delete (data as any).target_version
    await experimentApi.create(data)
    ElMessage.success('创建成功')
    showCreate.value = false
    await load()
  } finally {
    saving.value = false
  }
}

const handleRun = async (exp: any) => {
  await experimentApi.run(exp.id)
  ElMessage.success('实验已启动（后台运行）')
  setTimeout(load, 2000)
}

const handleDelete = async (exp: any) => {
  await ElMessageBox.confirm(`确认删除实验 "${exp.name}"？`, '删除确认', { type: 'warning' })
  await experimentApi.delete(exp.id)
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
.score-good { color: #10b981; font-weight: 600; }
.score-bad { color: #ef4444; font-weight: 600; }
</style>
