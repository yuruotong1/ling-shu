<template>
  <div v-if="skill">
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2>{{ skill.name }} <el-tag size="small">v{{ skill.version }}</el-tag>
          <el-tag v-if="skill.eval_score != null"
            :type="skill.eval_score >= 0.7 ? 'success' : 'danger'" size="small" style="margin-left:8px">
            评估: {{ (skill.eval_score * 100).toFixed(0) }}分
          </el-tag>
        </h2>
      </div>
      <div>
        <el-button type="primary" @click="showTest = true">在线测试</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="提示词" name="prompt">
        <el-card>
          <div style="margin-bottom:16px">
            <div class="label">提示词</div>
            <el-input v-model="editForm.prompt" type="textarea" :rows="12" />
          </div>
          <div style="margin-bottom:16px">
            <div class="label">绑定工具 / 知识库</div>
            <el-select v-model="editForm.bound_items" multiple placeholder="选择工具或知识库" style="width:100%">
              <el-option-group v-if="allTools.length" label="注册工具">
                <el-option v-for="t in allTools" :key="t.id" :label="t.name" :value="t.id" />
              </el-option-group>
              <el-option-group v-if="allNamespaces.length" label="知识库">
                <el-option v-for="ns in allNamespaces" :key="'kb:'+ns" :label="ns" :value="'kb:'+ns" />
              </el-option-group>
            </el-select>
          </div>
          <div style="margin-bottom:20px">
            <div class="label">变更摘要</div>
            <el-input v-model="editForm.change_summary" placeholder="描述本次修改内容（可选）" />
          </div>
          <div style="text-align:right">
            <el-button type="primary" @click="handleUpdate" :loading="saving">保存（创建新版本）</el-button>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="版本历史" name="versions">
        <el-table :data="versions" v-loading="vLoading">
          <el-table-column prop="version" label="版本" width="80">
            <template #default="{ row }">v{{ row.version }}</template>
          </el-table-column>
          <el-table-column prop="change_summary" label="变更摘要" />
          <el-table-column prop="created_by" label="来源" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="row.created_by === 'ai' ? 'warning' : 'info'">{{ row.created_by }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="评估得分" width="100">
            <template #default="{ row }">{{ row.eval_score != null ? (row.eval_score * 100).toFixed(0) + '分' : '—' }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间">
            <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" @click="handleRollback(row)">回滚到此版本</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 在线测试 -->
    <el-dialog v-model="showTest" title="在线测试" width="700px">
      <el-input v-model="testInput" type="textarea" :rows="4" placeholder="输入测试内容..." />
      <el-button type="primary" @click="runTest" :loading="testing" style="margin-top:12px">运行</el-button>
      <div v-if="testOutput" style="margin-top:16px">
        <div class="label">输出结果</div>
        <div class="output-text">{{ testOutput }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { skillApi, toolApi, kbApi } from '@/api'

const route = useRoute()
const skill = ref<any>(null)
const versions = ref<any[]>([])
const allTools = ref<any[]>([])
const allNamespaces = ref<string[]>([])
const activeTab = ref('prompt')
const vLoading = ref(false)
const showTest = ref(false)
const saving = ref(false)
const testing = ref(false)
const testInput = ref('')
const testOutput = ref('')
const editForm = ref({ prompt: '', bound_items: [] as string[], change_summary: '' })

const load = async () => {
  const [sr, tr, nsr] = await Promise.all([
    skillApi.get(route.params.id as string),
    toolApi.list(),
    kbApi.namespaces(),
  ])
  skill.value = sr.data
  allTools.value = tr.data
  allNamespaces.value = nsr.data || []
  const tool_items = skill.value.tools?.map((t: any) => t.id) || []
  const kb_items = (skill.value.kb_namespaces || []).map((ns: string) => 'kb:' + ns)
  editForm.value = {
    prompt: skill.value.prompt,
    bound_items: [...tool_items, ...kb_items],
    change_summary: '',
  }
  vLoading.value = true
  const vr = await skillApi.versions(route.params.id as string)
  versions.value = vr.data
  vLoading.value = false
}

const handleUpdate = async () => {
  saving.value = true
  try {
    const tool_ids = editForm.value.bound_items.filter(v => !v.startsWith('kb:'))
    const kb_namespaces = editForm.value.bound_items.filter(v => v.startsWith('kb:')).map(v => v.slice(3))
    await skillApi.update(skill.value.id, { ...editForm.value, tool_ids, kb_namespaces })
    ElMessage.success('已保存，版本已更新')
    await load()
  } finally {
    saving.value = false
  }
}

const handleRollback = async (row: any) => {
  await skillApi.rollback(skill.value.id, row.id)
  ElMessage.success(`已回滚到 v${row.version}`)
  await load()
}

const runTest = async () => {
  if (!testInput.value.trim()) return
  testing.value = true
  testOutput.value = ''
  try {
    const r = await skillApi.test(skill.value.id, {
      messages: [{ role: 'user', content: testInput.value }]
    })
    testOutput.value = r.data.output
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '测试失败')
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
h2 { font-size: 20px; font-weight: 600; }
.label { font-weight: 600; margin-bottom: 8px; }
.prompt-box { background: #1e1e2e; padding: 16px; border-radius: 6px; }
.prompt-box pre { color: #e2e8f0; font-family: monospace; font-size: 13px; white-space: pre-wrap; }
.output-text { background: #f8fafc; padding: 12px; border-radius: 6px; white-space: pre-wrap; }
</style>
