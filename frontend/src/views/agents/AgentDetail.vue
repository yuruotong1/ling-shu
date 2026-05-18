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
            <el-descriptions-item label="名称">
              <el-input v-model="editForm.name" size="small" placeholder="Agent名称" />
            </el-descriptions-item>
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
            <div style="display:flex;gap:8px">
              <el-select v-model="editForm.skill_ids" multiple placeholder="选择Skill" style="flex:1">
                <el-option v-for="s in allSkills" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
              <el-button @click="showCreateSkill = true"><el-icon><Plus /></el-icon> 创建Skill</el-button>
            </div>
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

      <!-- ── 返回格式（Response Format）── -->
      <el-tab-pane name="format">
        <template #label>
          <span>
            返回格式
            <el-tag v-if="agent.response_format_locked" type="danger" size="small" style="margin-left:4px">已锁定</el-tag>
            <el-tag v-else-if="agent.response_format" type="success" size="small" style="margin-left:4px">已配置</el-tag>
          </span>
        </template>
        <el-card>
          <!-- 当前格式展示 -->
          <div style="margin-bottom:16px">
            <div class="label">当前返回格式</div>
            <el-alert v-if="agent.response_format_locked" type="warning" :closable="false" style="margin-bottom:12px">
              该 Agent 的返回格式已被管理员锁定，业务人员无法修改。
            </el-alert>
            <div v-if="agent.response_format" class="schema-box">
              <pre>{{ JSON.stringify(agent.response_format, null, 2) }}</pre>
            </div>
            <el-empty v-else description="未配置返回格式，Agent 输出为自由文本" :image-size="60" />
          </div>

          <!-- 管理员配置区 -->
          <template v-if="authStore.isAdmin">
            <el-divider>管理员配置区（仅 admin 可见）</el-divider>

            <!-- 帮助文档 -->
            <el-collapse style="margin-bottom:16px">
              <el-collapse-item name="help">
                <template #title>
                  <span style="font-weight:600;color:#6366f1">📖 如何配置返回格式？（点击展开说明）</span>
                </template>
                <div class="help-doc">
                  <p><b>什么是返回格式？</b><br>配置后，Agent 输出将被强制为 JSON 对象，不符合时自动重试（最多 2 次），适合与下游系统对接。</p>
                  <p style="margin-top:8px"><b>实现方式：</b>提示词注入，无需模型原生支持，与 Qwen、DeepSeek、GPT、Claude 等所有模型兼容。</p>
                  <p style="margin-top:8px"><b>可视化编辑器支持的字段类型（标量）：</b></p>
                  <el-table :data="typeHelpRows" size="small" border style="margin-top:4px">
                    <el-table-column prop="type" label="类型" width="100" />
                    <el-table-column prop="desc" label="说明" />
                    <el-table-column prop="example" label="示例值" width="120" />
                  </el-table>
                  <p style="margin-top:8px;color:#6366f1">如需数组或嵌套对象字段，直接在下方 JSON Schema 文本框手动编写即可。</p>
                </div>
              </el-collapse-item>
            </el-collapse>

            <!-- 快捷模板 -->
            <div style="margin-bottom:16px">
              <div class="label">快捷模板</div>
              <div style="display:flex;gap:8px;flex-wrap:wrap">
                <el-button size="small" v-for="tpl in presetTemplates" :key="tpl.name"
                  @click="applyTemplate(tpl)">{{ tpl.name }}</el-button>
              </div>
            </div>

            <!-- 可视化字段编辑器 -->
            <div style="margin-bottom:16px">
              <div class="label">字段编辑器 <span style="font-weight:400;color:#94a3b8;font-size:12px">（添加字段后自动生成 JSON Schema）</span></div>
              <el-table :data="formatFields" border size="small" style="margin-bottom:8px">
                <el-table-column label="字段名" width="140">
                  <template #default="{ row }">
                    <el-input v-model="row.name" size="small" placeholder="field_name" @input="syncSchema" />
                  </template>
                </el-table-column>
                <el-table-column label="类型" width="120">
                  <template #default="{ row }">
                    <el-select v-model="row.type" size="small" @change="syncSchema">
                      <el-option v-for="t in fieldTypes" :key="t" :label="t" :value="t" />
                    </el-select>
                  </template>
                </el-table-column>
                <el-table-column label="枚举值（逗号分隔，可选）" min-width="160">
                  <template #default="{ row }">
                    <el-input v-model="row.enum" size="small" placeholder="值1,值2,值3（仅 string 类型有效）"
                      :disabled="row.type !== 'string'" @input="syncSchema" />
                  </template>
                </el-table-column>
                <el-table-column label="说明" min-width="140">
                  <template #default="{ row }">
                    <el-input v-model="row.description" size="small" @input="syncSchema" />
                  </template>
                </el-table-column>
                <el-table-column label="必填" width="70" align="center">
                  <template #default="{ row }">
                    <el-checkbox v-model="row.required" @change="syncSchema" />
                  </template>
                </el-table-column>
                <el-table-column label="" width="60" align="center">
                  <template #default="{ $index }">
                    <el-button link type="danger" size="small" @click="removeField($index)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-button size="small" @click="addField">+ 添加字段</el-button>
            </div>

            <!-- JSON Schema 原始编辑 -->
            <el-form label-width="110px" size="small">
              <el-form-item label="JSON Schema">
                <el-input v-model="formatForm.schemaText" type="textarea" :rows="10"
                  placeholder='{"type":"object","properties":{...},"required":[]}'
                  :status="schemaError ? 'error' : ''" @input="parseSchemaToFields" />
                <div v-if="schemaError" style="color:#f56c6c;font-size:12px;margin-top:4px">{{ schemaError }}</div>
              </el-form-item>
              <el-form-item label="锁定格式">
                <el-switch v-model="formatForm.locked" active-text="锁定（operator 不可改）" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="formatSaving" @click="handleFormatSave">保存格式配置</el-button>
                <el-button @click="clearFormat" style="margin-left:8px">清除格式（自由输出）</el-button>
              </el-form-item>
            </el-form>
          </template>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="版本历史" name="versions">
        <el-card>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
            <div>
              <span class="label">线上版本：</span>
              <el-tag v-if="agent.active_version_id" type="success">
                固定 v{{ versions.find(v => v.id === agent.active_version_id)?.version || '?' }}
              </el-tag>
              <el-tag v-else type="info">最新版本（自动）</el-tag>
            </div>
            <el-button v-if="agent.active_version_id && authStore.isAdmin" size="small" @click="handleUnpin">
              取消固定（恢复最新）
            </el-button>
          </div>
          <el-table :data="versions" v-loading="vLoading">
            <el-table-column label="版本" width="90">
              <template #default="{ row }">
                <span>v{{ row.version }}</span>
                <el-tag v-if="row.id === agent.active_version_id" type="success" size="small" style="margin-left:4px">线上</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="change_summary" label="变更摘要" />
            <el-table-column prop="created_at" label="时间" width="170">
              <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
            </el-table-column>
            <el-table-column label="操作" width="220">
              <template #default="{ row }">
                <el-button size="small" @click="handleRollback(row)">回滚（覆盖当前）</el-button>
                <el-button v-if="authStore.isAdmin" size="small" type="primary"
                  :disabled="row.id === agent.active_version_id"
                  @click="handleSetActive(row)">
                  {{ row.id === agent.active_version_id ? '已上线' : '设为线上' }}
                </el-button>
                <el-button v-if="authStore.isAdmin" size="small" type="danger"
                  :disabled="row.id === agent.active_version_id"
                  @click="handleDeleteVersion(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 在线测试 -->
    <el-dialog v-model="showTest" title="在线测试" width="700px" top="5vh">
      <div class="chat-container">
        <div class="chat-messages" ref="chatMessagesRef">
          <div v-if="testMessages.length === 0" class="chat-empty">
            <el-empty description="开始与Agent对话" :image-size="80" />
          </div>
          <div v-for="(msg, idx) in testMessages" :key="idx" class="chat-message" :class="msg.role">
            <div class="chat-bubble">
              <div class="chat-role">{{ msg.role === 'user' ? '用户' : 'Agent' }}</div>
              <div class="chat-content">{{ msg.content }}</div>
            </div>
            <div v-if="msg.role === 'assistant' && msg.loop_steps?.length" style="margin-top:8px">
              <el-timeline>
                <el-timeline-item v-for="step in msg.loop_steps" :key="step.round"
                  :timestamp="`第${step.round}轮`" placement="top">
                  <el-card class="step-card">
                    <div><b>思考：</b>{{ step.thought }}</div>
                    <div><b>行动：</b>{{ step.action }}</div>
                    <div v-if="step.observation !== msg.content"><b>观察：</b>{{ step.observation?.slice(0,200) }}</div>
                  </el-card>
                </el-timeline-item>
              </el-timeline>
            </div>
          </div>
        </div>
        <div class="chat-input-area">
          <el-input v-model="testInput" type="textarea" :rows="3" placeholder="输入消息...按Ctrl+Enter发送" @keydown.ctrl.enter.prevent="runTest" />
          <div style="margin-top:8px;display:flex;justify-content:flex-end;gap:8px">
            <el-button @click="clearTest">清空对话</el-button>
            <el-button type="primary" @click="runTest" :loading="testing">发送</el-button>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 创建Skill对话框 -->
    <el-dialog v-model="showCreateSkill" title="创建 Skill" width="600px">
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
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { agentApi, skillApi, agentFormatApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const authStore = useAuthStore()
const agent = ref<any>(null)
const versions = ref<any[]>([])
const allSkills = ref<any[]>([])
const activeTab = ref('info')
const codeLang = ref('python')
const vLoading = ref(false)
const showTest = ref(false)
const saving = ref(false)
const testing = ref(false)
const formatSaving = ref(false)
const schemaError = ref('')
const testInput = ref('')
const testMessages = ref<{role: string, content: string, loop_steps?: any[]}[]>([])
const chatMessagesRef = ref<HTMLElement | null>(null)
const editForm = ref({ name: '', system_prompt: '', skill_ids: [] as string[], max_loops: 10 })
const showCreateSkill = ref(false)
const skillSaving = ref(false)
const skillForm = ref({ name: '', description: '', prompt: '' })
const formatForm = ref({ schemaText: '', locked: false })

interface FormatField { name: string; type: string; enum: string; description: string; required: boolean }
const fieldTypes = ['string', 'number', 'integer', 'boolean']
const formatFields = ref<FormatField[]>([])

const typeHelpRows = [
  { type: 'string', desc: '文本字符串，可配置枚举限定取值范围', example: '"满意"' },
  { type: 'number', desc: '小数数字（含整数）', example: '0.95' },
  { type: 'integer', desc: '整数', example: '3' },
  { type: 'boolean', desc: '布尔值', example: 'true / false' },
]

const presetTemplates = [
  {
    name: '文本分类',
    fields: [
      { name: 'label', type: 'string', enum: '', description: '分类标签', required: true },
      { name: 'confidence', type: 'number', enum: '', description: '置信度（0-1）', required: true },
      { name: 'reason', type: 'string', enum: '', description: '判断理由', required: false },
    ]
  },
  {
    name: '意图识别',
    fields: [
      { name: 'intent', type: 'string', enum: '查询,购买,投诉,咨询,其他', description: '意图类别', required: true },
      { name: 'confidence', type: 'number', enum: '', description: '置信度（0-1）', required: true },
      { name: 'reason', type: 'string', enum: '', description: '判断理由', required: true },
    ]
  },
  {
    name: '情感分析',
    fields: [
      { name: 'sentiment', type: 'string', enum: '正面,负面,中性', description: '情感倾向', required: true },
      { name: 'score', type: 'number', enum: '', description: '情感强度（-1 到 1）', required: true },
    ]
  },
  {
    name: '评分结果',
    fields: [
      { name: 'score', type: 'integer', enum: '', description: '评分（1-5）', required: true },
      { name: 'summary', type: 'string', enum: '', description: '评价摘要', required: true },
    ]
  },
]

const addField = () => formatFields.value.push({ name: '', type: 'string', enum: '', description: '', required: true })
const removeField = (idx: number) => { formatFields.value.splice(idx, 1); syncSchema() }

const applyTemplate = (tpl: any) => {
  formatFields.value = tpl.fields.map((f: any) => ({ ...f }))
  syncSchema()
}

const syncSchema = () => {
  const props: any = {}
  const required: string[] = []
  for (const f of formatFields.value) {
    if (!f.name) continue
    const prop: any = { type: f.type }
    if (f.description) prop.description = f.description
    if (f.type === 'string' && f.enum) {
      prop.enum = f.enum.split(',').map((s: string) => s.trim()).filter(Boolean)
    }
    props[f.name] = prop
    if (f.required) required.push(f.name)
  }
  if (Object.keys(props).length === 0) { formatForm.value.schemaText = ''; return }
  const schema = { type: 'object', properties: props, required }
  formatForm.value.schemaText = JSON.stringify(schema, null, 2)
  schemaError.value = ''
}

const parseSchemaToFields = () => {
  if (!formatForm.value.schemaText.trim()) { formatFields.value = []; return }
  try {
    const schema = JSON.parse(formatForm.value.schemaText)
    schemaError.value = ''
    if (schema.type === 'object' && schema.properties) {
      const required: string[] = schema.required || []
      formatFields.value = Object.entries(schema.properties).map(([name, prop]: any) => ({
        name,
        type: prop.type || 'string',
        enum: prop.enum ? prop.enum.join(',') : '',
        description: prop.description || '',
        required: required.includes(name),
      }))
    }
  } catch {
    schemaError.value = 'JSON 格式不正确，请检查'
  }
}

const handleFormatSave = async () => {
  schemaError.value = ''
  let schema: any = null
  if (formatForm.value.schemaText.trim()) {
    try {
      schema = JSON.parse(formatForm.value.schemaText)
    } catch {
      schemaError.value = 'JSON 格式不正确，请检查'
      return
    }
  }
  formatSaving.value = true
  try {
    await agentFormatApi.update(agent.value.id, {
      response_format: schema,
      response_format_locked: formatForm.value.locked,
    })
    ElMessage.success('返回格式已更新')
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    formatSaving.value = false
  }
}

const clearFormat = async () => {
  formatForm.value.schemaText = ''
  formatFields.value = []
  formatSaving.value = true
  try {
    await agentFormatApi.update(agent.value.id, { response_format: null, response_format_locked: false })
    ElMessage.success('已清除返回格式')
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    formatSaving.value = false
  }
}

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
    name: agent.value.name,
    system_prompt: agent.value.system_prompt,
    skill_ids: agent.value.skills?.map((s: any) => s.id) || [],
    max_loops: agent.value.max_loops,
  }
  formatForm.value = {
    schemaText: agent.value.response_format ? JSON.stringify(agent.value.response_format, null, 2) : '',
    locked: agent.value.response_format_locked || false,
  }
  parseSchemaToFields()
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

const handleSetActive = async (row: any) => {
  await agentApi.setActiveVersion(agent.value.id, row.id)
  ElMessage.success(`v${row.version} 已设为线上版本`)
  await load()
}

const handleUnpin = async () => {
  await agentApi.unpinVersion(agent.value.id)
  ElMessage.success('已取消版本固定，恢复使用最新版本')
  await load()
}

const handleDeleteVersion = async (row: any) => {
  try {
    await agentApi.deleteVersion(agent.value.id, row.id)
    ElMessage.success(`v${row.version} 已删除`)
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

const runTest = async () => {
  if (!testInput.value.trim() || !agent.value) return
  const userContent = testInput.value.trim()
  testMessages.value.push({ role: 'user', content: userContent })
  testInput.value = ''
  testing.value = true
  try {
    const messages = testMessages.value.map(m => ({ role: m.role, content: m.content }))
    const r = await agentApi.test(agent.value.id, { messages })
    testMessages.value.push({
      role: 'assistant',
      content: r.data.output,
      loop_steps: r.data.loop_steps || []
    })
    setTimeout(() => {
      chatMessagesRef.value?.scrollTo({ top: chatMessagesRef.value.scrollHeight, behavior: 'smooth' })
    }, 50)
  } catch (e: any) {
    const errMsg = e.response?.data?.detail || '测试失败'
    ElMessage.error(errMsg)
    testMessages.value.push({ role: 'assistant', content: '【错误】' + errMsg })
  } finally {
    testing.value = false
  }
}

const clearTest = () => {
  testMessages.value = []
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
    editForm.value.skill_ids.push(r.data.id)
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
.label { font-weight: 600; margin-bottom: 8px; color: #374151; }
.test-output { margin-top: 16px; }
.output-label { font-weight: 600; margin-bottom: 8px; }
.output-text { background: #f8fafc; padding: 12px; border-radius: 6px; white-space: pre-wrap; }
.step-card { font-size: 13px; line-height: 1.6; }
.chat-container { display: flex; flex-direction: column; height: 70vh; }
.chat-messages { flex: 1; overflow-y: auto; padding: 8px; }
.chat-empty { display: flex; align-items: center; justify-content: center; height: 100%; }
.chat-message { margin-bottom: 16px; }
.chat-message.user { text-align: right; }
.chat-message.user .chat-bubble { background: #e6f7ff; margin-left: auto; max-width: 80%; }
.chat-message.assistant .chat-bubble { background: #f6ffed; max-width: 80%; }
.chat-bubble { display: inline-block; padding: 10px 14px; border-radius: 8px; text-align: left; }
.chat-role { font-size: 12px; color: #8c8c8c; margin-bottom: 4px; }
.chat-content { white-space: pre-wrap; word-break: break-word; }
.chat-input-area { border-top: 1px solid #eee; padding-top: 12px; }
.api-header { margin-bottom: 16px; }
.api-meta { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 10px; padding: 12px 16px; background: #f8fafc; border-radius: 6px; font-size: 13px; color: #374151; }
.meta-item b { color: #1e293b; }
.code-tabs { margin-top: 4px; }
.code-block-wrap { position: relative; }
.copy-btn { position: absolute; top: 10px; right: 10px; z-index: 1; }
.code-block { background: #1e293b; color: #e2e8f0; padding: 16px 40px 16px 16px; border-radius: 6px; font-family: 'Fira Code', 'Consolas', monospace; font-size: 13px; line-height: 1.6; overflow-x: auto; white-space: pre; margin: 0; }
.schema-box { background: #1e1e2e; padding: 16px; border-radius: 6px; }
.schema-box pre { color: #e2e8f0; font-family: monospace; font-size: 13px; white-space: pre-wrap; }
.help-doc { font-size: 13px; line-height: 1.8; color: #374151; padding: 4px 0; }
</style>
