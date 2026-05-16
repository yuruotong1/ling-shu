<template>
  <div v-if="agent">
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2>{{ agent.name }} <el-tag size="small">v{{ agent.version }}</el-tag></h2>
        <p class="subtitle">{{ agent.description }}</p>
      </div>
      <div>
        <el-button type="primary" @click="showTest = true">在线测试</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="基本信息" name="info">
        <el-card>
          <el-descriptions :column="2" border style="margin-bottom:20px">
            <el-descriptions-item label="名称">{{ agent.name }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="agent.status === 'active' ? 'success' : 'info'">{{ agent.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="版本">v{{ agent.version }}</el-descriptions-item>
            <el-descriptions-item label="最大循环次数">
              <el-input-number v-model="editForm.max_loops" :min="1" :max="50" size="small" />
            </el-descriptions-item>
          </el-descriptions>
          <div style="margin-bottom:16px">
            <div class="label">系统提示词</div>
            <el-input v-model="editForm.system_prompt" type="textarea" :rows="8" />
          </div>
          <div style="margin-bottom:20px">
            <div class="label">绑定Skill</div>
            <el-select v-model="editForm.skill_ids" multiple placeholder="选择Skill" style="width:100%">
              <el-option v-for="s in allSkills" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </div>
          <div style="text-align:right">
            <el-button type="primary" @click="handleUpdate" :loading="saving">保存</el-button>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="接口调用" name="api">
        <el-card>
          <div class="api-header">
            <div class="label">外部调用接口</div>
            <div class="api-meta">
              <span class="meta-item"><b>接口地址：</b>{{ baseUrl }}/v1/chat/completions</span>
              <span class="meta-item"><b>模型名称：</b>{{ agent.name }}</span>
              <span class="meta-item"><b>鉴权方式：</b>Bearer Token</span>
            </div>
          </div>
          <el-tabs v-model="codeLang" class="code-tabs">
            <el-tab-pane label="Python" name="python">
              <div class="code-block-wrap">
                <el-button class="copy-btn" size="small" @click="copyCode('python')">复制</el-button>
                <pre class="code-block">{{ codeSnippets.python }}</pre>
              </div>
            </el-tab-pane>
            <el-tab-pane label="JavaScript" name="js">
              <div class="code-block-wrap">
                <el-button class="copy-btn" size="small" @click="copyCode('js')">复制</el-button>
                <pre class="code-block">{{ codeSnippets.js }}</pre>
              </div>
            </el-tab-pane>
            <el-tab-pane label="Java" name="java">
              <div class="code-block-wrap">
                <el-button class="copy-btn" size="small" @click="copyCode('java')">复制</el-button>
                <pre class="code-block">{{ codeSnippets.java }}</pre>
              </div>
            </el-tab-pane>
            <el-tab-pane label="Go" name="go">
              <div class="code-block-wrap">
                <el-button class="copy-btn" size="small" @click="copyCode('go')">复制</el-button>
                <pre class="code-block">{{ codeSnippets.go }}</pre>
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="版本历史" name="versions">
        <el-table :data="versions" v-loading="vLoading">
          <el-table-column prop="version" label="版本" width="80">
            <template #default="{ row }">v{{ row.version }}</template>
          </el-table-column>
          <el-table-column prop="change_summary" label="变更摘要" />
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
    <el-dialog v-model="showTest" title="在线测试" width="800px">
      <div class="test-area">
        <el-input v-model="testInput" type="textarea" :rows="4" placeholder="输入测试内容..." />
        <el-button type="primary" @click="runTest" :loading="testing" style="margin-top:12px">运行</el-button>
        <div v-if="testOutput" class="test-output">
          <div class="output-label">输出结果</div>
          <div class="output-text">{{ testOutput }}</div>
          <div v-if="loopSteps.length" style="margin-top:16px">
            <div class="output-label">Agent循环过程</div>
            <el-timeline>
              <el-timeline-item v-for="step in loopSteps" :key="step.round"
                :timestamp="`第${step.round}轮`" placement="top">
                <el-card class="step-card">
                  <div><b>思考：</b>{{ step.thought }}</div>
                  <div><b>行动：</b>{{ step.action }}</div>
                  <div v-if="step.observation !== testOutput"><b>观察：</b>{{ step.observation?.slice(0,200) }}</div>
                </el-card>
              </el-timeline-item>
            </el-timeline>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { agentApi, skillApi } from '@/api'

const route = useRoute()
const agent = ref<any>(null)
const versions = ref<any[]>([])
const allSkills = ref<any[]>([])
const activeTab = ref('info')
const codeLang = ref('python')
const vLoading = ref(false)
const showTest = ref(false)
const saving = ref(false)
const testing = ref(false)
const testInput = ref('')
const testOutput = ref('')
const loopSteps = ref<any[]>([])
const editForm = ref({ system_prompt: '', skill_ids: [] as string[], max_loops: 10 })

const baseUrl = computed(() => `${window.location.protocol}//${window.location.hostname}:8000`)

const codeSnippets = computed(() => {
  const name = agent.value?.name || 'your-agent'
  const url = baseUrl.value
  const model = name
  const apiKey = 'sk-platform-dev'

  return {
    python: `from openai import OpenAI

client = OpenAI(
    api_key="${apiKey}",
    base_url="${url}/v1",
)

response = client.chat.completions.create(
    model="${model}",
    messages=[{"role": "user", "content": "你好"}],
)

print(response.choices[0].message.content)`,

    js: `import OpenAI from "openai";

const client = new OpenAI({
    apiKey: "${apiKey}",
    baseURL: "${url}/v1",
    dangerouslyAllowBrowser: true,
});

const response = await client.chat.completions.create({
    model: "${model}",
    messages: [{ role: "user", content: "你好" }],
});

console.log(response.choices[0].message.content);`,

    java: `// 依赖：OkHttp 4.x
import okhttp3.*;
import java.io.IOException;

OkHttpClient client = new OkHttpClient();

String body = """
    {
        "model": "${model}",
        "messages": [{"role": "user", "content": "你好"}]
    }
    """;

Request request = new Request.Builder()
    .url("${url}/v1/chat/completions")
    .addHeader("Authorization", "Bearer ${apiKey}")
    .addHeader("Content-Type", "application/json")
    .post(RequestBody.create(body, MediaType.parse("application/json")))
    .build();

try (Response response = client.newCall(request).execute()) {
    System.out.println(response.body().string());
}`,

    go: `package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
)

func main() {
    payload, _ := json.Marshal(map[string]any{
        "model": "${model}",
        "messages": []map[string]string{
            {"role": "user", "content": "你好"},
        },
    })

    req, _ := http.NewRequest("POST", "${url}/v1/chat/completions", bytes.NewBuffer(payload))
    req.Header.Set("Authorization", "Bearer ${apiKey}")
    req.Header.Set("Content-Type", "application/json")

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    body, _ := io.ReadAll(resp.Body)
    fmt.Println(string(body))
}`,
  }
})

const copyCode = (lang: string) => {
  const code = codeSnippets.value[lang as keyof typeof codeSnippets.value]
  navigator.clipboard.writeText(code).then(() => ElMessage.success('已复制到剪贴板'))
}

const load = async () => {
  const [ar, sr] = await Promise.all([agentApi.get(route.params.id as string), skillApi.list()])
  agent.value = ar.data
  allSkills.value = sr.data
  editForm.value = {
    system_prompt: agent.value.system_prompt,
    skill_ids: agent.value.skills?.map((s: any) => s.id) || [],
    max_loops: agent.value.max_loops,
  }
  vLoading.value = true
  const vr = await agentApi.versions(route.params.id as string)
  versions.value = vr.data
  vLoading.value = false
}

const handleUpdate = async () => {
  saving.value = true
  try {
    await agentApi.update(agent.value.id, editForm.value)
    ElMessage.success('已保存')
    await load()
  } finally {
    saving.value = false
  }
}

const handleRollback = async (row: any) => {
  await agentApi.rollback(agent.value.id, row.id)
  ElMessage.success(`已回滚到 v${row.version}`)
  await load()
}

const runTest = async () => {
  if (!testInput.value.trim()) return
  testing.value = true
  testOutput.value = ''
  loopSteps.value = []
  try {
    const r = await agentApi.test(agent.value.id, {
      messages: [{ role: 'user', content: testInput.value }]
    })
    testOutput.value = r.data.output
    loopSteps.value = r.data.loop_steps || []
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
.subtitle { color: #94a3b8; font-size: 14px; margin-top: 4px; }
.label { font-weight: 600; margin-bottom: 8px; color: #374151; }
.test-output { margin-top: 16px; }
.output-label { font-weight: 600; margin-bottom: 8px; }
.output-text { background: #f8fafc; padding: 12px; border-radius: 6px; white-space: pre-wrap; }
.step-card { font-size: 13px; line-height: 1.6; }
.api-header { margin-bottom: 16px; }
.api-meta { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 10px; padding: 12px 16px; background: #f8fafc; border-radius: 6px; font-size: 13px; color: #374151; }
.meta-item b { color: #1e293b; }
.code-tabs { margin-top: 4px; }
.code-block-wrap { position: relative; }
.copy-btn { position: absolute; top: 10px; right: 10px; z-index: 1; }
.code-block { background: #1e293b; color: #e2e8f0; padding: 16px 40px 16px 16px; border-radius: 6px; font-family: 'Fira Code', 'Consolas', monospace; font-size: 13px; line-height: 1.6; overflow-x: auto; white-space: pre; margin: 0; }
</style>
