<template>
  <div>
    <div class="page-header">
      <div>
        <h2>调用链路</h2>
        <p class="subtitle">单次调用 & 多轮对话，可继续追问、评分、一键优化 Agent/Skill</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <el-input v-model="filterAgent" placeholder="按 Agent 名称过滤" clearable style="width:200px" />
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <div v-if="selectedRows.length" style="margin-bottom:12px">
      <el-button type="danger" @click="handleBatchDelete">
        批量删除 ({{ selectedRows.length }})
      </el-button>
    </div>

    <el-table :data="displayRows" v-loading="loading" class="data-table"
      row-class-name="clickable-row" @row-click="openRow"
      @selection-change="onSelectionChange">
      <el-table-column type="selection" width="45" />
      <el-table-column label="" width="40">
        <template #default="{ row }">
          <el-tooltip :content="row._isSession ? '多轮对话' : '单次调用'">
            <el-icon :style="{ color: row._isSession ? '#6366f1' : '#94a3b8' }">
              <component :is="row._isSession ? 'ChatLineRound' : 'Lightning'" />
            </el-icon>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="Agent" width="150">
        <template #default="{ row }">
          <span>{{ row.agent_name }}</span>
          <el-tag size="small" style="margin-left:4px">v{{ row.agent_version }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="输入摘要" show-overflow-tooltip>
        <template #default="{ row }">{{ row._summary }}</template>
      </el-table-column>
      <el-table-column label="轮数" width="65" align="center">
        <template #default="{ row }">
          <el-tag v-if="row._isSession" size="small" type="info">{{ row._turnCount }}轮</el-tag>
          <span v-else style="color:#94a3b8">1</span>
        </template>
      </el-table-column>
      <el-table-column label="评分" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.user_rating === 'good'" type="success" size="small">👍</el-tag>
          <el-tag v-else-if="row.user_rating === 'bad'" type="danger" size="small">👎</el-tag>
          <span v-else style="color:#d1d5db">—</span>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="90">
        <template #default="{ row }">{{ row.latency_ms }}ms</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="170">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" align="center">
        <template #default="{ row }">
          <el-button link size="small" @click.stop="openRow(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click.stop="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 详情 Drawer -->
    <el-drawer v-model="showDrawer" :title="drawerTitle" size="60%" destroy-on-close>
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;width:100%">
          <span>{{ drawerTitle }}</span>
          <el-button link type="danger" @click="handleDeleteFromDrawer">删除</el-button>
        </div>
      </template>
      <div v-if="activeRow" class="drawer-body">

        <!-- 会话视图（多轮） -->
        <template v-if="activeRow._isSession">
          <div class="session-turns">
            <div v-for="turn in sessionTurns" :key="turn.id" class="turn-block">
              <!-- 用户输入 -->
              <div class="bubble user-bubble">
                <div class="bubble-role">用户</div>
                <div class="bubble-content">{{ getUserMsg(turn) }}</div>
              </div>
              <!-- Agent 回复 -->
              <div class="bubble agent-bubble">
                <div class="bubble-role" style="display:flex;justify-content:space-between;align-items:center">
                  <span>Agent <el-tag size="small">v{{ turn.agent_version }}</el-tag></span>
                  <div style="display:flex;gap:4px">
                    <el-button link :type="turn.user_rating === 'good' ? 'success' : ''"
                      @click.stop="rateTurn(turn, 'good')">👍</el-button>
                    <el-button link :type="turn.user_rating === 'bad' ? 'danger' : ''"
                      @click.stop="rateTurn(turn, 'bad')">👎</el-button>
                  </div>
                </div>
                <div class="bubble-content">{{ turn.output }}</div>
                <!-- 期望输出编辑 -->
                <div v-if="turn.user_rating === 'bad' || turn.reference_output" style="margin-top:8px">
                  <div style="font-size:12px;color:#94a3b8;margin-bottom:4px">期望输出（用于优化参考）</div>
                  <el-input v-model="refOutputMap[turn.id]" type="textarea" :rows="2" size="small"
                    placeholder="填写期望的正确回答..."
                    @blur="saveRef(turn)" />
                </div>
                <!-- Loop steps 折叠 -->
                <el-collapse v-if="turn.loop_steps?.length" style="margin-top:8px" class="steps-collapse">
                  <el-collapse-item :title="`思考过程（${turn.loop_steps.length}步）`" name="steps">
                    <el-timeline>
                      <el-timeline-item v-for="step in turn.loop_steps" :key="step.round"
                        :timestamp="`第${step.round}轮`" placement="top">
                        <div style="font-size:12px;line-height:1.6">
                          <div v-if="step.thought"><b>思考：</b>{{ step.thought }}</div>
                          <div v-if="step.action"><b>行动：</b>{{ step.action }}</div>
                          <div v-if="step.observation"><b>观察：</b>{{ step.observation?.slice(0, 200) }}</div>
                        </div>
                      </el-timeline-item>
                    </el-timeline>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
            <div v-if="!sessionTurns.length" style="color:#94a3b8;text-align:center;padding:40px">加载中...</div>
          </div>

        </template>

        <!-- 单次 Trace 视图 -->
        <template v-else>
          <el-descriptions :column="3" border size="small" style="margin-bottom:16px">
            <el-descriptions-item label="Agent">{{ activeRow.agent_name }} v{{ activeRow.agent_version }}</el-descriptions-item>
            <el-descriptions-item label="耗时">{{ activeRow.latency_ms }}ms</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="activeRow.status === 'success' ? 'success' : 'danger'" size="small">{{ activeRow.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Tokens">{{ activeRow.prompt_tokens + activeRow.completion_tokens }}</el-descriptions-item>
            <el-descriptions-item label="循环次数">{{ activeRow.total_loops }}</el-descriptions-item>
          </el-descriptions>

          <!-- 输入 -->
          <div class="section-label">用户输入</div>
          <div class="output-box" style="margin-bottom:12px">{{ getUserMsg(activeRow) }}</div>

          <!-- 输出 & 评分 -->
          <div class="section-label" style="display:flex;justify-content:space-between;align-items:center">
            <span>Agent 输出</span>
            <div style="display:flex;gap:4px">
              <el-button link size="small" :type="activeRow.user_rating === 'good' ? 'success' : ''"
                @click="rateTurn(activeRow, 'good')">👍 满意</el-button>
              <el-button link size="small" :type="activeRow.user_rating === 'bad' ? 'danger' : ''"
                @click="rateTurn(activeRow, 'bad')">👎 不满意</el-button>
            </div>
          </div>
          <div class="output-box" style="margin-bottom:12px">{{ activeRow.output }}</div>

          <!-- 期望输出 -->
          <div v-if="activeRow.user_rating === 'bad' || activeRow.reference_output" style="margin-bottom:12px">
            <div class="section-label">期望输出</div>
            <el-input v-model="refOutputMap[activeRow.id]" type="textarea" :rows="3"
              placeholder="填写期望的正确回答（用于优化参考）..."
              @blur="saveRef(activeRow)" />
          </div>

          <!-- Loop steps -->
          <el-collapse v-if="activeRow.loop_steps?.length" style="margin-bottom:16px">
            <el-collapse-item :title="`思考过程（${activeRow.loop_steps.length}步）`" name="steps">
              <el-timeline>
                <el-timeline-item v-for="step in activeRow.loop_steps" :key="step.round"
                  :timestamp="`第${step.round}轮`" placement="top">
                  <el-card class="step-card">
                    <div v-if="step.thought"><b>思考：</b>{{ step.thought }}</div>
                    <div v-if="step.action"><b>行动：</b><el-tag size="small">{{ step.action }}</el-tag></div>
                    <div v-if="step.observation"><b>观察：</b>{{ step.observation?.slice(0, 300) }}</div>
                  </el-card>
                </el-timeline-item>
              </el-timeline>
            </el-collapse-item>
          </el-collapse>

        </template>

        <!-- 优化区域 -->
        <el-divider style="margin: 24px 0 16px" />
        <div class="section-label" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span>从对话优化</span>
        </div>
        <el-form size="small" label-width="80px">
          <el-form-item label="优化目标">
            <el-select v-model="optimizeTargetId" placeholder="选择要优化的 Agent 或 Skill" style="width:100%">
              <el-option-group label="Agents">
                <el-option v-for="a in allAgents" :key="a.id" :label="a.name" :value="`${a.id}|agent`" />
              </el-option-group>
              <el-option-group label="Skills">
                <el-option v-for="s in allSkills" :key="s.id" :label="s.name" :value="`${s.id}|skill`" />
              </el-option-group>
            </el-select>
          </el-form-item>
          <el-form-item label="优化指令">
            <el-input v-model="optimizeInstruction" type="textarea" :rows="2"
              placeholder="可选：描述你希望如何优化这个 Agent 或 Skill..." />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="small" :loading="optimizing"
              @click="doOptimize(!!activeRow._isSession)">
              生成新版本
            </el-button>
          </el-form-item>
          <el-form-item v-if="optimizeResult" label="结果">
            <el-alert :title="`已生成 v${optimizeResult.version}`" type="success" :closable="false" show-icon>
              <template #default>
                <div style="margin-top:4px;font-size:12px">
                  变更说明：{{ optimizeResult.change_summary || '无' }}
                </div>
                <div style="margin-top:8px">
                  <el-button size="small" type="primary"
                    @click="router.push(`/${optimizeResult.target_type === 'agent' ? 'agents' : 'skills'}/${optimizeResult.target_id}`)">
                    去管理新生成的{{ optimizeResult.target_type === 'agent' ? 'Agent' : 'Skill' }}
                  </el-button>
                </div>
              </template>
            </el-alert>
          </el-form-item>
        </el-form>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { traceApi, agentApi, skillApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const traces = ref<any[]>([])
const loading = ref(false)
const filterAgent = ref('')
const selectedRows = ref<any[]>([])
const showDrawer = ref(false)
const activeRow = ref<any>(null)
const sessionTurns = ref<any[]>([])
const continueMsg = ref('')
const continuing = ref(false)
const optimizing = ref(false)
const optimizeInstruction = ref('')
const optimizeTargetId = ref('')
const optimizeResult = ref<any>(null)
const refOutputMap = ref<Record<string, string>>({})
const allAgents = ref<any[]>([])
const allSkills = ref<any[]>([])

// Group traces: session head + individual
const displayRows = computed(() => {
  const seen = new Set<string>()
  const rows: any[] = []
  // first pass: find all sessions
  const sessionMap = new Map<string, any[]>()
  for (const t of traces.value) {
    if (t.session_id) {
      const key = t.session_id
      if (!sessionMap.has(key)) sessionMap.set(key, [])
      sessionMap.get(key)!.push(t)
    }
  }
  for (const t of traces.value) {
    if (t.session_id) {
      const key = t.session_id
      if (seen.has(key)) continue
      seen.add(key)
      const turns = (sessionMap.get(key) || []).sort((a, b) => a.turn_index - b.turn_index)
      const head = turns[0]
      rows.push({
        ...head,
        _isSession: true,
        _turnCount: turns.length,
        _summary: getUserMsg(head).slice(0, 80),
        _sessionId: key,
      })
    } else {
      rows.push({ ...t, _isSession: false, _turnCount: 1, _summary: getUserMsg(t).slice(0, 80) })
    }
  }
  return rows
})

const drawerTitle = computed(() => {
  if (!activeRow.value) return '详情'
  if (activeRow.value._isSession) return `多轮对话 — ${activeRow.value.agent_name} (${activeRow.value._turnCount}轮)`
  return `调用详情 — ${activeRow.value.agent_name}`
})

function getUserMsg(trace: any): string {
  const msgs: any[] = trace.input || []
  const last = msgs.filter((m: any) => m.role === 'user').pop()
  return last?.content || ''
}

const load = async () => {
  loading.value = true
  try {
    const r = await traceApi.list(filterAgent.value || undefined)
    traces.value = r.data
  } finally {
    loading.value = false
  }
}

const onSelectionChange = (rows: any[]) => {
  selectedRows.value = rows
}

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除该调用记录？`, '删除确认', { type: 'warning' })
    await traceApi.delete(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }
}

const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(`确认批量删除 ${selectedRows.value.length} 条记录？`, '删除确认', { type: 'warning' })
    const ids = selectedRows.value.map(r => r.id)
    await traceApi.batchDelete(ids)
    ElMessage.success('批量删除成功')
    selectedRows.value = []
    await load()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }
}

const handleDeleteFromDrawer = async () => {
  if (!activeRow.value) return
  try {
    await ElMessageBox.confirm('确认删除该调用记录？', '删除确认', { type: 'warning' })
    await traceApi.delete(activeRow.value.id)
    ElMessage.success('已删除')
    showDrawer.value = false
    await load()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }
}

const openRow = async (row: any) => {
  activeRow.value = row
  continueMsg.value = ''
  optimizeResult.value = null
  optimizeInstruction.value = ''
  optimizeTargetId.value = ''
  // init ref map
  refOutputMap.value[row.id] = row.reference_output || ''
  if (row._isSession) {
    const r = await traceApi.getSession(row._sessionId)
    sessionTurns.value = r.data
    for (const t of r.data) refOutputMap.value[t.id] = t.reference_output || ''
  }
  showDrawer.value = true
}

const rateTurn = async (trace: any, rating: 'good' | 'bad') => {
  const newRating = trace.user_rating === rating ? null : rating
  await traceApi.rate(trace.id, { user_rating: newRating })
  trace.user_rating = newRating
  // update in main list
  const found = traces.value.find(t => t.id === trace.id)
  if (found) found.user_rating = newRating
}

const saveRef = async (trace: any) => {
  const ref = refOutputMap.value[trace.id]
  if (ref === (trace.reference_output || '')) return
  await traceApi.rate(trace.id, { reference_output: ref || null })
  trace.reference_output = ref || null
}

const doSingleContinue = async () => {
  if (!continueMsg.value.trim()) return
  continuing.value = true
  try {
    const r = await traceApi.continueTrace(activeRow.value.id, { user_message: continueMsg.value })
    continueMsg.value = ''
    // drawer becomes session
    const sessionId = r.data.session_id
    activeRow.value._isSession = true
    activeRow.value._sessionId = sessionId
    const sr = await traceApi.getSession(sessionId)
    sessionTurns.value = sr.data
    activeRow.value._turnCount = sr.data.length
    for (const t of sr.data) refOutputMap.value[t.id] = t.reference_output || ''
    await load()
    ElMessage.success('已追加新对话轮次')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    continuing.value = false
  }
}

const doContinue = async () => {
  if (!continueMsg.value.trim()) return
  continuing.value = true
  try {
    // use the last turn's trace id to continue
    const lastTurn = sessionTurns.value[sessionTurns.value.length - 1]
    const r = await traceApi.continueTrace(lastTurn.id, { user_message: continueMsg.value })
    continueMsg.value = ''
    const sr = await traceApi.getSession(activeRow.value._sessionId)
    sessionTurns.value = sr.data
    activeRow.value._turnCount = sr.data.length
    for (const t of sr.data) refOutputMap.value[t.id] = t.reference_output || ''
    await load()
    ElMessage.success('已追加新对话轮次')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    continuing.value = false
  }
}

const doOptimize = async (isSession: boolean) => {
  if (!optimizeTargetId.value) { ElMessage.warning('请选择要优化的 Agent 或 Skill'); return }
  const [id, type] = optimizeTargetId.value.split('|')
  optimizing.value = true
  optimizeResult.value = null
  try {
    let r: any
    if (isSession) {
      r = await traceApi.optimizeFromSession(activeRow.value._sessionId, {
        target_type: type, target_id: id, instruction: optimizeInstruction.value,
      })
    } else {
      r = await traceApi.optimizeFromTrace(activeRow.value.id, {
        target_type: type, target_id: id, instruction: optimizeInstruction.value,
      })
    }
    optimizeResult.value = { ...r.data, target_type: type, target_id: id }
    ElMessage.success(`已生成新版本 v${r.data.version}，请前往对应 ${type === 'agent' ? 'Agent' : 'Skill'} 详情页查看`)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '优化失败')
  } finally {
    optimizing.value = false
  }
}

watch(filterAgent, () => { if (!filterAgent.value) load() })

onMounted(async () => {
  load()
  const [ar, sr] = await Promise.all([agentApi.list(), skillApi.list()])
  allAgents.value = ar.data
  allSkills.value = sr.data
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
h2 { font-size: 20px; font-weight: 600; }
.subtitle { color: #94a3b8; font-size: 14px; margin-top: 4px; }
.data-table { background: white; border-radius: 8px; }
:deep(.clickable-row) { cursor: pointer; }

.drawer-body { padding: 0 4px; }

/* Session conversation */
.session-turns { display: flex; flex-direction: column; gap: 16px; max-height: 55vh; overflow-y: auto; padding-right: 4px; }
.turn-block { display: flex; flex-direction: column; gap: 8px; }
.bubble { padding: 10px 14px; border-radius: 8px; }
.bubble-role { font-size: 12px; color: #6b7280; font-weight: 600; margin-bottom: 6px; }
.bubble-content { font-size: 13px; white-space: pre-wrap; word-break: break-all; line-height: 1.6; }
.user-bubble { background: #f0f4ff; }
.agent-bubble { background: #f6ffed; }
.steps-collapse { margin-top: 4px; }
:deep(.steps-collapse .el-collapse-item__header) { font-size: 12px; color: #94a3b8; }

/* Single trace */
.section-label { font-weight: 600; margin-bottom: 8px; color: #374151; }
.output-box { background: #f8fafc; padding: 12px; border-radius: 6px; white-space: pre-wrap; font-size: 13px; line-height: 1.6; }
.step-card { font-size: 13px; line-height: 1.7; }

/* Optimize */
.optimize-area { background: #fafafa; border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; }
.optimize-result { margin-top: 10px; }
</style>
