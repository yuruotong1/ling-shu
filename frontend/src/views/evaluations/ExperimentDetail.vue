<template>
  <div v-if="experiment">
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2>{{ experiment.name }}
          <el-tag size="small" :type="statusType(experiment.status)">{{ experiment.status }}</el-tag>
        </h2>
        <p class="subtitle">{{ experiment.target_type }}: {{ experiment.target_name }}
          <span v-if="experiment.target_version">v{{ experiment.target_version }}</span>
        </p>
      </div>
      <div>
        <el-button type="primary" @click="handleRun" :disabled="experiment.status === 'running'">运行实验</el-button>
      </div>
    </div>

    <!-- 统计摘要 -->
    <el-row :gutter="16" style="margin-bottom:20px">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value" :class="experiment.avg_score >= 0.7 ? 'score-good' : 'score-bad'">
            {{ experiment.avg_score != null ? (experiment.avg_score * 100).toFixed(1) + '分' : '—' }}
          </div>
          <div class="stat-label">平均得分</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ experiment.pass_rate != null ? (experiment.pass_rate * 100).toFixed(1) + '%' : '—' }}</div>
          <div class="stat-label">通过率（≥70分）</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ experiment.total_items }}</div>
          <div class="stat-label">总样本数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value" style="color:#ef4444">{{ experiment.failed_items }}</div>
          <div class="stat-label">失败数</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 自动迭代 -->
    <el-card v-if="experiment.status === 'completed' && experiment.avg_score != null && experiment.avg_score < 0.7"
      class="optimize-card" style="margin-bottom:20px">
      <div class="optimize-header">
        <el-icon style="color:#f59e0b"><Warning /></el-icon>
        <span>评估得分低于阈值（{{ (experiment.avg_score * 100).toFixed(1) }}分 &lt; 70分），建议优化Skill</span>
      </div>
      <div style="margin-top:12px;display:flex;gap:12px;align-items:center">
        <el-input v-model="skillName" placeholder="Skill名称" style="width:200px" />
        <el-input v-model="optimizeInstruction" placeholder="优化方向（可选）" style="width:300px" />
        <el-button type="warning" @click="handleOptimize" :loading="optimizing">AI自动优化Skill</el-button>
      </div>
      <div v-if="optimizeResult" style="margin-top:12px">
        <el-alert type="success" title="优化版本已生成" show-icon>
          <div>新版本 v{{ optimizeResult.version }} 已创建（AI生成），请在Skill详情页确认并发布。</div>
          <div class="change-summary">{{ optimizeResult.change_summary }}</div>
        </el-alert>
      </div>
    </el-card>

    <!-- 结果列表 -->
    <el-card>
      <template #header><span>评估结果详情（{{ results.length }}条）</span></template>
      <el-table :data="results" v-loading="resultsLoading">
        <el-table-column label="输入" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.input?.length ? row.input[row.input.length-1]?.content?.slice(0,80) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="实际输出" show-overflow-tooltip>
          <template #default="{ row }">{{ row.actual_output?.slice(0,100) }}</template>
        </el-table-column>
        <el-table-column label="得分" width="80">
          <template #default="{ row }">
            <span :class="row.score >= 0.7 ? 'score-good' : 'score-bad'">
              {{ row.score != null ? (row.score * 100).toFixed(0) + '分' : '—' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="问题" show-overflow-tooltip>
          <template #default="{ row }">{{ row.issues?.join(', ') }}</template>
        </el-table-column>
        <el-table-column label="优化建议" show-overflow-tooltip>
          <template #default="{ row }">{{ row.suggestion }}</template>
        </el-table-column>
        <el-table-column v-if="results.some(r => r.error)" label="错误" show-overflow-tooltip>
          <template #default="{ row }">
            <span style="color:#ef4444">{{ row.error }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { experimentApi, skillApi } from '@/api'

const route = useRoute()
const experiment = ref<any>(null)
const results = ref<any[]>([])
const resultsLoading = ref(false)
const optimizing = ref(false)
const skillName = ref('')
const optimizeInstruction = ref('')
const optimizeResult = ref<any>(null)

const statusType = (s: string) => ({ pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }[s] || 'info')

const load = async () => {
  const r = await experimentApi.get(route.params.id as string)
  experiment.value = r.data
  resultsLoading.value = true
  try {
    const rr = await experimentApi.results(route.params.id as string)
    results.value = rr.data
  } finally {
    resultsLoading.value = false
  }
}

const handleRun = async () => {
  await experimentApi.run(experiment.value.id)
  ElMessage.success('实验已启动')
  setTimeout(load, 2000)
}

const handleOptimize = async () => {
  if (!skillName.value.trim()) {
    ElMessage.warning('请输入Skill名称')
    return
  }
  optimizing.value = true
  optimizeResult.value = null
  try {
    // 先根据名称找Skill ID
    const sr = await skillApi.list()
    const skill = sr.data.find((s: any) => s.name === skillName.value.trim())
    if (!skill) {
      ElMessage.error(`找不到Skill: ${skillName.value}`)
      return
    }
    const r = await experimentApi.optimize(experiment.value.id, skill.id, optimizeInstruction.value)
    optimizeResult.value = r.data
    ElMessage.success('AI已生成优化版本')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '优化失败')
  } finally {
    optimizing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
h2 { font-size: 20px; font-weight: 600; }
.subtitle { color: #94a3b8; font-size: 14px; margin-top: 4px; }
.stat-card { text-align: center; }
.stat-value { font-size: 28px; font-weight: 700; }
.stat-label { color: #94a3b8; font-size: 13px; margin-top: 4px; }
.score-good { color: #10b981; }
.score-bad { color: #ef4444; }
.optimize-card { border: 1px solid #fbbf24; background: #fffbeb; }
.optimize-header { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.change-summary { margin-top: 4px; color: #6b7280; font-size: 13px; }
</style>
