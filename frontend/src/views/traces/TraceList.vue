<template>
  <div>
    <div class="page-header">
      <div>
        <h2>调用链路</h2>
        <p class="subtitle">每次Agent调用的完整Trace，包含思考→行动→观察全过程</p>
      </div>
      <div>
        <el-input v-model="filterAgent" placeholder="按Agent名称过滤" clearable style="width:200px;margin-right:8px" />
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <el-table :data="traces" v-loading="loading" class="data-table">
      <el-table-column prop="agent_name" label="Agent" width="150" />
      <el-table-column prop="agent_version" label="版本" width="80">
        <template #default="{ row }"><el-tag size="small">v{{ row.agent_version }}</el-tag></template>
      </el-table-column>
      <el-table-column label="输入" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.input?.length ? row.input[row.input.length-1]?.content?.slice(0,80) : '' }}
        </template>
      </el-table-column>
      <el-table-column label="输出" show-overflow-tooltip>
        <template #default="{ row }">{{ row.output?.slice(0,80) }}</template>
      </el-table-column>
      <el-table-column prop="total_loops" label="循环次数" width="90" />
      <el-table-column label="耗时" width="100">
        <template #default="{ row }">{{ row.latency_ms }}ms</template>
      </el-table-column>
      <el-table-column label="Tokens" width="120">
        <template #default="{ row }">{{ row.prompt_tokens + row.completion_tokens }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="180">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button size="small" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Trace详情 -->
    <el-dialog v-model="showDetail" title="调用链路详情" width="800px">
      <div v-if="activeTrace">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="Agent">{{ activeTrace.agent_name }} v{{ activeTrace.agent_version }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ activeTrace.latency_ms }}ms</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="activeTrace.status === 'success' ? 'success' : 'danger'" size="small">{{ activeTrace.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Prompt Tokens">{{ activeTrace.prompt_tokens }}</el-descriptions-item>
          <el-descriptions-item label="Completion Tokens">{{ activeTrace.completion_tokens }}</el-descriptions-item>
          <el-descriptions-item label="循环次数">{{ activeTrace.total_loops }}</el-descriptions-item>
        </el-descriptions>

        <div style="margin-top:16px">
          <div class="section-label">循环过程</div>
          <el-timeline v-if="activeTrace.loop_steps?.length">
            <el-timeline-item v-for="step in activeTrace.loop_steps" :key="step.round"
              :timestamp="`第${step.round}轮`" placement="top">
              <el-card class="step-card">
                <div v-if="step.thought"><b>思考：</b>{{ step.thought }}</div>
                <div v-if="step.action"><b>行动：</b><el-tag size="small">{{ step.action }}</el-tag></div>
                <div v-if="step.observation" style="margin-top:4px">
                  <b>观察：</b><span style="color:#6b7280">{{ step.observation?.slice(0,300) }}</span>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <div v-else style="color:#94a3b8">无循环步骤记录</div>
        </div>

        <div style="margin-top:16px">
          <div class="section-label">最终输出</div>
          <div class="output-box">{{ activeTrace.output }}</div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { traceApi } from '@/api'

const traces = ref<any[]>([])
const loading = ref(false)
const filterAgent = ref('')
const showDetail = ref(false)
const activeTrace = ref<any>(null)

const load = async () => {
  loading.value = true
  try {
    const r = await traceApi.list(filterAgent.value || undefined)
    traces.value = r.data
  } finally {
    loading.value = false
  }
}

const openDetail = (trace: any) => {
  activeTrace.value = trace
  showDetail.value = true
}

watch(filterAgent, () => {
  if (filterAgent.value === '') load()
})

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
h2 { font-size: 20px; font-weight: 600; }
.subtitle { color: #94a3b8; font-size: 14px; margin-top: 4px; }
.data-table { background: white; border-radius: 8px; }
.section-label { font-weight: 600; margin-bottom: 8px; }
.step-card { font-size: 13px; line-height: 1.7; }
.output-box { background: #f8fafc; padding: 12px; border-radius: 6px; white-space: pre-wrap; font-size: 13px; }
</style>
