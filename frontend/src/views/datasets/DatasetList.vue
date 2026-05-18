<template>
  <div>
    <div class="page-header">
      <div>
        <h2>数据集管理</h2>
        <p class="subtitle">评估集：为评估器提供标准测试用例</p>
      </div>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 新建评估集
      </el-button>
    </div>

    <el-row :gutter="16">
      <el-col :span="12" v-for="s in sets" :key="s.id">
        <el-card class="set-card" @click="openSet(s)">
          <div class="set-header">
            <span class="set-name">{{ s.name }}</span>
            <el-tag size="small">{{ s.item_count }} 条样本</el-tag>
          </div>
          <div class="set-desc">{{ s.description || '暂无描述' }}</div>
          <div class="set-meta">
            <el-tag size="small" type="info">{{ s.data_type }}</el-tag>
            <span v-if="s.target_name" style="margin-left:8px;color:#94a3b8">目标: {{ s.target_name }}</span>
          </div>
          <div class="set-footer">
            <span>{{ new Date(s.created_at).toLocaleDateString('zh-CN') }}</span>
            <el-button size="small" type="danger" @click.stop="handleDelete(s)">删除</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 创建评估集 -->
    <el-dialog v-model="showCreate" title="新建评估集" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="名称" required><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="createForm.description" /></el-form-item>
        <el-form-item label="数据粒度">
          <el-select v-model="createForm.data_type">
            <el-option label="Agent级别" value="agent" />
            <el-option label="Skill级别" value="skill" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标名称">
          <el-input v-model="createForm.target_name" placeholder="Agent或Skill名称（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="saving">创建</el-button>
      </template>
    </el-dialog>

    <!-- 评估集详情 & 添加样本 -->
    <el-dialog v-model="showSetDetail" :title="`评估集: ${activeSet?.name}`" width="900px">
      <div style="margin-bottom:12px;display:flex;justify-content:flex-end">
        <el-button type="primary" size="small" @click="openAddItem">
          <el-icon><Plus /></el-icon> 添加样本
        </el-button>
      </div>
      <el-table :data="items" v-loading="itemsLoading" max-height="400">
        <el-table-column label="输入" show-overflow-tooltip>
          <template #default="{ row }">{{ inputPreview(row.input) }}</template>
        </el-table-column>
        <el-table-column prop="reference_output" label="参考输出" show-overflow-tooltip />
        <el-table-column prop="eval_score" label="评分" width="80">
          <template #default="{ row }">{{ row.eval_score != null ? (row.eval_score * 100).toFixed(0) + '分' : '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="handleDeleteItem(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 添加样本 -->
    <el-dialog v-model="showAddItem" title="添加评估样本" width="800px" @close="resetAddItem">
      <el-tabs v-model="addTab" @tab-change="onTabChange">
        <!-- 从调用链路选择 -->
        <el-tab-pane label="从调用链路选择" name="trace">
          <div class="trace-toolbar">
            <el-input v-model="traceFilter" placeholder="按Agent名称过滤" clearable style="width:200px" @input="filterTraces" />
            <span class="trace-hint">已选 {{ selectedTraces.length }} 条</span>
          </div>
          <el-table
            ref="traceTableRef"
            :data="filteredTraces"
            v-loading="tracesLoading"
            max-height="360"
            @selection-change="selectedTraces = $event"
          >
            <el-table-column type="selection" width="45" />
            <el-table-column prop="agent_name" label="Agent" width="130" />
            <el-table-column label="用户输入" show-overflow-tooltip>
              <template #default="{ row }">{{ inputPreview(row.input) }}</template>
            </el-table-column>
            <el-table-column label="输出" show-overflow-tooltip>
              <template #default="{ row }">{{ row.output?.slice(0, 80) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="时间" width="150">
              <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
            </el-table-column>
          </el-table>
          <div style="text-align:right;margin-top:12px">
            <el-button @click="showAddItem = false">取消</el-button>
            <el-button type="primary" @click="handleImportTraces" :loading="savingItem" :disabled="!selectedTraces.length">
              导入选中 ({{ selectedTraces.length }})
            </el-button>
          </div>
        </el-tab-pane>

        <!-- 手动填写 -->
        <el-tab-pane label="手动填写" name="manual">
          <el-form :model="itemForm" label-width="100px" style="margin-top:12px">
            <el-form-item label="用户输入" required>
              <el-input v-model="itemForm.input_text" type="textarea" :rows="3" placeholder="用户输入内容" />
            </el-form-item>
            <el-form-item label="参考输出">
              <el-input v-model="itemForm.reference_output" type="textarea" :rows="3" placeholder="期望的输出（可选）" />
            </el-form-item>
          </el-form>
          <div style="text-align:right">
            <el-button @click="showAddItem = false">取消</el-button>
            <el-button type="primary" @click="handleAddItem" :loading="savingItem">添加</el-button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { evalSetApi, traceApi } from '@/api'

const sets = ref<any[]>([])
const items = ref<any[]>([])
const loading = ref(false)
const itemsLoading = ref(false)
const showCreate = ref(false)
const showSetDetail = ref(false)
const showAddItem = ref(false)
const saving = ref(false)
const savingItem = ref(false)
const activeSet = ref<any>(null)
const createForm = ref({ name: '', description: '', data_type: 'agent', target_name: '' })
const itemForm = ref({ input_text: '', reference_output: '' })

const addTab = ref('trace')
const allTraces = ref<any[]>([])
const tracesLoading = ref(false)
const traceFilter = ref('')
const selectedTraces = ref<any[]>([])
const traceTableRef = ref()

const filteredTraces = computed(() => {
  if (!traceFilter.value) return allTraces.value
  return allTraces.value.filter(t => t.agent_name.includes(traceFilter.value))
})

const inputPreview = (input: any) => {
  if (!input) return ''
  if (Array.isArray(input)) {
    const last = input[input.length - 1]
    return last?.content?.slice(0, 80) || ''
  }
  return String(input).slice(0, 80)
}

const filterTraces = () => { /* computed handles it */ }

const load = async () => {
  loading.value = true
  try {
    const r = await evalSetApi.list()
    sets.value = r.data
  } finally {
    loading.value = false
  }
}

const openSet = async (s: any) => {
  activeSet.value = s
  showSetDetail.value = true
  itemsLoading.value = true
  try {
    const r = await evalSetApi.listItems(s.id)
    items.value = r.data
  } finally {
    itemsLoading.value = false
  }
}

const openAddItem = () => {
  addTab.value = 'manual'
  showAddItem.value = true
}

const resetAddItem = () => {
  itemForm.value = { input_text: '', reference_output: '' }
  traceFilter.value = ''
  selectedTraces.value = []
  allTraces.value = []
}

const onTabChange = async (tab: string) => {
  if (tab === 'trace' && allTraces.value.length === 0) {
    tracesLoading.value = true
    try {
      const agentName = activeSet.value?.data_type === 'agent' ? activeSet.value?.target_name : undefined
      const r = await traceApi.list(agentName || undefined)
      allTraces.value = r.data
    } finally {
      tracesLoading.value = false
    }
  }
}

const handleCreate = async () => {
  saving.value = true
  try {
    await evalSetApi.create(createForm.value)
    ElMessage.success('创建成功')
    showCreate.value = false
    createForm.value = { name: '', description: '', data_type: 'agent', target_name: '' }
    await load()
  } finally {
    saving.value = false
  }
}

const handleDelete = async (s: any) => {
  await ElMessageBox.confirm(`确认删除评估集 "${s.name}"？`, '删除确认', { type: 'warning' })
  await evalSetApi.delete(s.id)
  ElMessage.success('已删除')
  await load()
}

const handleAddItem = async () => {
  savingItem.value = true
  try {
    await evalSetApi.addItem(activeSet.value.id, {
      input: [{ role: 'user', content: itemForm.value.input_text }],
      reference_output: itemForm.value.reference_output || null,
      data_type: activeSet.value.data_type,
    })
    ElMessage.success('已添加')
    showAddItem.value = false
    itemForm.value = { input_text: '', reference_output: '' }
    const r = await evalSetApi.listItems(activeSet.value.id)
    items.value = r.data
    await load()
  } finally {
    savingItem.value = false
  }
}

const handleImportTraces = async () => {
  if (!selectedTraces.value.length) return
  savingItem.value = true
  try {
    for (const trace of selectedTraces.value) {
      await evalSetApi.addItem(activeSet.value.id, {
        input: trace.input,
        reference_output: trace.output || null,
        data_type: activeSet.value.data_type,
      })
    }
    ElMessage.success(`已导入 ${selectedTraces.value.length} 条`)
    showAddItem.value = false
    const r = await evalSetApi.listItems(activeSet.value.id)
    items.value = r.data
    await load()
  } finally {
    savingItem.value = false
  }
}

const handleDeleteItem = async (item: any) => {
  await evalSetApi.deleteItem(activeSet.value.id, item.id)
  ElMessage.success('已删除')
  const r = await evalSetApi.listItems(activeSet.value.id)
  items.value = r.data
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
h2 { font-size: 20px; font-weight: 600; }
.subtitle { color: #94a3b8; font-size: 14px; margin-top: 4px; }
.set-card { margin-bottom: 16px; cursor: pointer; transition: box-shadow 0.2s; }
.set-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.set-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
.set-name { font-weight: 600; }
.set-desc { font-size: 13px; color: #6b7280; margin-bottom: 8px; }
.set-meta { margin-bottom: 8px; }
.set-footer { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: #94a3b8; }
.trace-toolbar { display: flex; align-items: center; gap: 12px; margin: 12px 0 8px; }
.trace-hint { font-size: 13px; color: #6b7280; }
</style>
