<template>
  <div v-if="agent">
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2>
          {{ agent.name }}
          <el-tag size="small">v{{ agent.version }}</el-tag>
          <el-tag v-if="agent.active_version_id" type="success" size="small" style="margin-left:4px">
            线上 v{{ versions.find(v => v.id === agent.active_version_id)?.version }}
          </el-tag>
        </h2>
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
            <div class="label" style="display:flex;justify-content:space-between;align-items:center">
              <span>系统提示词</span>
              <AiGeneratePrompt type="agent" @generated="(val: string) => editForm.system_prompt = val" />
            </div>
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
          <div class="code-tabs">
            <el-radio-group v-model="codeLang" size="small" style="margin-bottom: 12px;">
              <el-radio-button label="python">Python</el-radio-button>
              <el-radio-button label="js">JavaScript</el-radio-button>
              <el-radio-button label="java">Java</el-radio-button>
              <el-radio-button label="go">Go</el-radio-button>
            </el-radio-group>
            <div v-show="codeLang === 'python'" class="code-block-wrap">
              <el-button class="copy-btn" size="small" @click="copyCode('python')">复制</el-button>
              <pre class="code-block">{{ codeSnippets.python }}</pre>
            </div>
            <div v-show="codeLang === 'js'" class="code-block-wrap">
              <el-button class="copy-btn" size="small" @click="copyCode('js')">复制</el-button>
              <pre class="code-block">{{ codeSnippets.js }}</pre>
            </div>
            <div v-show="codeLang === 'java'" class="code-block-wrap">
              <el-button class="copy-btn" size="small" @click="copyCode('java')">复制</el-button>
              <pre class="code-block">{{ codeSnippets.java }}</pre>
            </div>
            <div v-show="codeLang === 'go'" class="code-block-wrap">
              <el-button class="copy-btn" size="small" @click="copyCode('go')">复制</el-button>
              <pre class="code-block">{{ codeSnippets.go }}</pre>
            </div>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="返回格式" name="format">
        <el-card>
          <div style="margin-bottom:16px">
            <div class="label">当前返回格式</div>
            <div v-if="agent.response_format" class="schema-box">
              <pre>{{ JSON.stringify(agent.response_format, null, 2) }}</pre>
            </div>
            <el-empty v-else description="未配置返回格式，Agent 输出为自由文本" :image-size="60" />
          </div>

          <template v-if="authStore.isAdmin">
            <el-divider>管理员配置区（仅 admin 可见）</el-divider>
            <el-form label-width="100px" size="small">
              <el-form-item label="JSON Schema">
                <el-input v-model="formatForm.schemaText" type="textarea" :rows="12"
                  placeholder='{"type":"object","properties":{"intent":{"type":"string"}},"required":["intent"]}'
                  :status="formatError ? 'error' : ''" />
                <div v-if="formatError" style="color:#f56c6c;font-size:12px;margin-top:4px">{{ formatError }}</div>
              </el-form-item>
              <el-form-item>
                <el-button @click="showTestSchema = true">Schema 测试</el-button>
                <el-button @click="showGenerateSchema = true">AI 生成</el-button>
                <el-button type="primary" :loading="formatSaving" @click="handleFormatSave">保存</el-button>
                <el-button @click="clearFormat">清除</el-button>
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
          <el-table :data="versions" :loading="vLoading">
            <el-table-column label="版本" width="90">
              <template #default="{ row }">
                <span>v{{ row.version }}</span>
                <el-tag v-if="row.id === agent.active_version_id" type="success" size="small" style="margin-left:4px">线上</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="change_summary" label="变更摘要" width="120" show-overflow-tooltip />
            <el-table-column label="系统提示词" min-width="160">
              <template #default="{ row }">
                <span style="white-space:pre-wrap">{{ row.system_prompt?.slice(0, 60) }}{{ row.system_prompt?.length > 60 ? '...' : '' }}</span>
                <el-button v-if="row.system_prompt?.length > 60" link size="small" type="primary" @click="openVersionDetail(row)" style="margin-left:4px">查看完整</el-button>
              </template>
            </el-table-column>
            <el-table-column label="Skill配置" min-width="120">
              <template #default="{ row }">
                <span v-if="!row.skills_snapshot?.length">—</span>
                <span v-else>
                  {{ row.skills_snapshot.map((s: any) => s.name).join(', ').slice(0, 40) }}
                  {{ row.skills_snapshot.map((s: any) => s.name).join(', ').length > 40 ? '...' : '' }}
                </span>
                <el-button v-if="row.skills_snapshot?.length" link size="small" type="primary" @click="openVersionDetail(row)" style="margin-left:4px">查看</el-button>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="170">
              <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
            </el-table-column>
            <el-table-column label="操作" width="220">
              <template #default="{ row }">
                <template v-if="row._isCurrent">
                  <el-tag size="small" type="success">当前版本</el-tag>
                </template>
                <template v-else>
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
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="调用链路" name="traces">
        <el-card>
          <el-table :data="agentTraces" :loading="tracesLoading" class="data-table">
            <el-table-column label="输入摘要" show-overflow-tooltip>
              <template #default="{ row }">
                <span>{{ getTraceSummary(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="输出" show-overflow-tooltip>
              <template #default="{ row }">{{ row.output?.slice(0, 60) }}</template>
            </el-table-column>
            <el-table-column label="类型" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.session_id ? 'primary' : 'info'">{{ row.session_id ? '多轮' : '单轮' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="耗时" width="90">
              <template #default="{ row }">{{ row.latency_ms }}ms</template>
            </el-table-column>
            <el-table-column label="时间" width="170">
              <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center">
              <template #default="{ row }">
                <el-button link size="small" @click="openTraceDetail(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="评估数据集" name="datasets">
        <el-card>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <span class="label">评估数据集</span>
            <el-button type="primary" size="small" @click="showCreateEvalSet = true">创建数据集</el-button>
          </div>
          <el-table :data="agentEvalSets" :loading="evalSetsLoading" class="data-table">
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="description" label="描述" show-overflow-tooltip />
            <el-table-column label="样本数" width="90" align="center">
              <template #default="{ row }">{{ row.item_count || 0 }}</template>
            </el-table-column>
            <el-table-column label="时间" width="170">
              <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
            </el-table-column>
            <el-table-column label="操作" width="150" align="center">
              <template #default="{ row }">
                <el-button link size="small" @click="openEvalSet(row)">查看</el-button>
                <el-button link type="danger" size="small" @click="deleteEvalSet(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="实验对比" name="experiments">
        <el-card>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <span class="label">实验对比</span>
            <el-button type="primary" size="small" @click="showCreateExperiment = true">创建实验</el-button>
          </div>
          <el-table :data="agentExperiments" :loading="experimentsLoading" class="data-table">
            <el-table-column prop="name" label="名称" />
            <el-table-column label="评估器" width="120">
              <template #default="{ row }">{{ row.evaluator?.name || '—' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'completed' ? 'success' : row.status === 'running' ? 'warning' : 'info'">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="均分" width="80" align="center">
              <template #default="{ row }">{{ row.avg_score != null ? (row.avg_score * 100).toFixed(0) + '分' : '—' }}</template>
            </el-table-column>
            <el-table-column label="时间" width="170">
              <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="center">
              <template #default="{ row }">
                <el-button link size="small" @click="router.push(`/experiments/${row.id}`)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 在线测试 -->
    <el-dialog v-model="showTest" title="在线测试" width="700px" top="5vh" destroy-on-close>
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
          <el-input v-model="testInput" type="textarea" :rows="3" placeholder="Enter 发送，Shift+Enter 换行" @keydown.enter.exact.prevent="runTest" />
          <div style="margin-top:8px;display:flex;justify-content:flex-end;gap:8px">
            <el-button @click="clearTest">清空对话</el-button>
            <el-button type="primary" @click="runTest" :loading="testing">发送</el-button>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- Schema 测试对话框 -->
    <el-dialog v-model="showTestSchema" title="Schema 测试" width="600px">
      <el-form label-width="100px">
        <el-form-item label="当前 Schema">
          <div class="output-text" style="max-height:160px;overflow:auto">{{ formatForm.schemaText || '（未填写）' }}</div>
        </el-form-item>
        <el-form-item label="测试数据">
          <el-input v-model="testSchemaData" type="textarea" :rows="6" placeholder='{"intent":"查询","confidence":0.95,"reason":"用户询问订单状态"}' />
        </el-form-item>
        <el-form-item v-if="testSchemaResult">
          <div :style="{ color: testSchemaResult.startsWith('✅') ? '#67c23a' : '#f56c6c' }">{{ testSchemaResult }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTestSchema = false">关闭</el-button>
        <el-button type="primary" @click="doTestSchema">运行测试</el-button>
      </template>
    </el-dialog>

    <!-- AI 生成 Schema 对话框 -->
    <el-dialog v-model="showGenerateSchema" title="AI 生成 Schema" width="600px">
      <el-form label-width="100px">
        <el-form-item label="描述需求">
          <el-input v-model="schemaDesc" type="textarea" :rows="4" placeholder="例如：一个意图识别结果，包含意图类别（查询/购买/投诉）、置信度（0-1之间的小数）、判断理由" />
        </el-form-item>
        <el-form-item>
          <el-button type="warning" :loading="generatingSchema" @click="doGenerateSchema">🤖 AI 生成 Schema</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateSchema = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 版本详情对话框 -->
    <el-dialog v-model="showVersionDetail" :title="`版本详情 v${versionDetail?.version}`" width="700px" destroy-on-close>
      <div v-if="versionDetail">
        <div class="label">系统提示词</div>
        <div class="output-text" style="max-height:300px;overflow:auto;margin-bottom:16px;white-space:pre-wrap">{{ versionDetail.system_prompt }}</div>
        <div class="label">Skill 配置</div>
        <el-table v-if="versionDetail.skills_snapshot?.length" :data="versionDetail.skills_snapshot" size="small" border>
          <el-table-column prop="name" label="名称" width="150" />
          <el-table-column prop="description" label="描述" show-overflow-tooltip />
        </el-table>
        <div v-else style="color:#94a3b8;font-size:13px">无 Skill 配置</div>
      </div>
      <template #footer>
        <el-button @click="showVersionDetail = false">关闭</el-button>
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

    <!-- 创建评估集对话框 -->
    <el-dialog v-model="showCreateEvalSet" title="创建评估数据集" width="500px" destroy-on-close>
      <el-form :model="evalSetForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="evalSetForm.name" placeholder="数据集名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="evalSetForm.description" placeholder="描述该数据集的用途..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateEvalSet = false">取消</el-button>
        <el-button type="primary" @click="createEvalSet">创建</el-button>
      </template>
    </el-dialog>

    <!-- 创建实验对话框 -->
    <el-dialog v-model="showCreateExperiment" title="创建实验" width="500px" destroy-on-close>
      <el-form :model="experimentForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="experimentForm.name" placeholder="实验名称" />
        </el-form-item>
        <el-form-item label="评估器" required>
          <el-select v-model="experimentForm.evaluator_id" placeholder="选择评估器" style="width:100%">
            <el-option v-for="e in allEvaluators" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据集" required>
          <el-select v-model="experimentForm.eval_set_id" placeholder="选择数据集" style="width:100%">
            <el-option v-for="s in agentEvalSets" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateExperiment = false">取消</el-button>
        <el-button type="primary" @click="createExperiment">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { agentApi, skillApi, agentFormatApi, traceApi, evalSetApi, experimentApi, evaluatorApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import AiGeneratePrompt from '@/components/AiGeneratePrompt.vue'

const route = useRoute()
const router = useRouter()
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
const formatError = ref('')
const formatForm = ref({ schemaText: '' })
const showTestSchema = ref(false)
const showGenerateSchema = ref(false)
const schemaDesc = ref('')
const testSchemaData = ref('')
const testSchemaResult = ref('')
const generatingSchema = ref(false)

const testInput = ref('')
const testMessages = ref<{role: string, content: string, loop_steps?: any[]}[]>([])
const chatMessagesRef = ref<HTMLElement | null>(null)
const testSessionId = ref<string | null>(null)
const editForm = ref({ name: '', system_prompt: '', skill_ids: [] as string[], max_loops: 10 })
const showCreateSkill = ref(false)
const skillSaving = ref(false)
const skillForm = ref({ name: '', description: '', prompt: '' })
const showVersionDetail = ref(false)
const versionDetail = ref<any>(null)

const agentTraces = ref<any[]>([])
const tracesLoading = ref(false)
const agentEvalSets = ref<any[]>([])
const evalSetsLoading = ref(false)
const showCreateEvalSet = ref(false)
const evalSetForm = ref({ name: '', description: '' })
const agentExperiments = ref<any[]>([])
const experimentsLoading = ref(false)
const showCreateExperiment = ref(false)
const experimentForm = ref({ name: '', evaluator_id: '', eval_set_id: '' })
const allEvaluators = ref<any[]>([])

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
  formatForm.value.schemaText = agent.value.response_format ? JSON.stringify(agent.value.response_format, null, 2) : ''
  formatError.value = ''
  vLoading.value = true
  const vr = await agentApi.versions(route.params.id as string)
  // 将当前版本作为第一条记录插入版本历史
  const currentVersion = {
    id: agent.value.id,
    version: agent.value.version,
    system_prompt: agent.value.system_prompt,
    change_summary: '当前版本',
    skills_snapshot: (agent.value.skills || []).map((s: any) => ({ id: s.id, name: s.name, description: s.description })),
    created_at: agent.value.updated_at,
    _isCurrent: true,
  }
  versions.value = [currentVersion, ...vr.data]
  vLoading.value = false

  // 加载关联数据
  tracesLoading.value = true
  evalSetsLoading.value = true
  experimentsLoading.value = true
  const [tr, esr, exr, evr] = await Promise.all([
    traceApi.list(undefined, route.params.id as string).catch(() => ({ data: [] })),
    evalSetApi.list(route.params.id as string).catch(() => ({ data: [] })),
    experimentApi.list(route.params.id as string).catch(() => ({ data: [] })),
    evaluatorApi.list().catch(() => ({ data: [] })),
  ])
  agentTraces.value = tr.data
  tracesLoading.value = false
  agentEvalSets.value = esr.data
  evalSetsLoading.value = false
  agentExperiments.value = exr.data
  experimentsLoading.value = false
  allEvaluators.value = evr.data
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

const openVersionDetail = (row: any) => {
  versionDetail.value = row
  showVersionDetail.value = true
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

const checkJson = () => {
  formatError.value = ''
  if (!formatForm.value.schemaText.trim()) return
  try {
    JSON.parse(formatForm.value.schemaText)
    ElMessage.success('JSON 格式合法')
  } catch {
    formatError.value = 'JSON 格式不正确，请检查'
  }
}

const handleFormatSave = async () => {
  formatError.value = ''
  let schema: any = null
  if (formatForm.value.schemaText.trim()) {
    try {
      schema = JSON.parse(formatForm.value.schemaText)
    } catch {
      formatError.value = 'JSON 格式不正确，请检查'
      return
    }
  }
  formatSaving.value = true
  try {
    await agentFormatApi.update(agent.value.id, { response_format: schema })
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
  formatError.value = ''
  formatSaving.value = true
  try {
    await agentFormatApi.update(agent.value.id, { response_format: null })
    ElMessage.success('已清除返回格式')
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    formatSaving.value = false
  }
}

const doTestSchema = async () => {
  testSchemaResult.value = ''
  let schema: any
  let data: any
  try {
    schema = JSON.parse(formatForm.value.schemaText)
  } catch {
    testSchemaResult.value = '❌ Schema JSON 格式错误，请先修正'
    return
  }
  try {
    data = JSON.parse(testSchemaData.value)
  } catch {
    testSchemaResult.value = '❌ 测试数据 JSON 格式错误'
    return
  }
  try {
    const r = await agentFormatApi.test(agent.value.id, { schema, data })
    if (r.data.valid) {
      testSchemaResult.value = '✅ 验证通过，数据符合 Schema'
    } else {
      testSchemaResult.value = '❌ ' + r.data.error
    }
  } catch (e: any) {
    testSchemaResult.value = e.response?.data?.detail || '测试失败'
  }
}

const doGenerateSchema = async () => {
  if (!schemaDesc.value.trim()) {
    ElMessage.warning('请先描述你想要的输出格式')
    return
  }
  generatingSchema.value = true
  testSchemaResult.value = ''
  try {
    const r = await agentFormatApi.generate(agent.value.id, { description: schemaDesc.value })
    const generated = r.data.schema
    if (generated) {
      formatForm.value.schemaText = JSON.stringify(generated, null, 2)
      ElMessage.success('AI 已生成 Schema，已填充到输入框')
    } else {
      ElMessage.error('生成失败，未返回有效 Schema')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    generatingSchema.value = false
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
    const r = await agentApi.test(agent.value.id, { messages, session_id: testSessionId.value })
    testMessages.value.push({
      role: 'assistant',
      content: r.data.output,
      loop_steps: r.data.loop_steps || []
    })
    testSessionId.value = r.data.session_id || null
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
  testSessionId.value = null
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

const getTraceSummary = (trace: any) => {
  const msgs: any[] = trace.input || []
  const last = msgs.filter((m: any) => m.role === 'user').pop()
  return last?.content || ''
}

const openTraceDetail = (row: any) => {
  window.open(`/#/traces?highlight=${row.id}`, '_blank')
}

const openEvalSet = (row: any) => {
  window.open(`/#/datasets?highlight=${row.id}`, '_blank')
}

const deleteEvalSet = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除数据集 "${row.name}"？`, '删除确认', { type: 'warning' })
    await evalSetApi.delete(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

const createEvalSet = async () => {
  if (!evalSetForm.value.name.trim()) {
    ElMessage.warning('请输入数据集名称')
    return
  }
  try {
    await evalSetApi.create({
      ...evalSetForm.value,
      agent_id: agent.value.id,
      target_name: agent.value.name,
    })
    ElMessage.success('创建成功')
    showCreateEvalSet.value = false
    evalSetForm.value = { name: '', description: '' }
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  }
}

const createExperiment = async () => {
  if (!experimentForm.value.name.trim()) {
    ElMessage.warning('请输入实验名称')
    return
  }
  if (!experimentForm.value.evaluator_id || !experimentForm.value.eval_set_id) {
    ElMessage.warning('请选择评估器和数据集')
    return
  }
  try {
    await experimentApi.create({
      ...experimentForm.value,
      agent_id: agent.value.id,
      target_type: 'agent',
      target_name: agent.value.name,
      target_version: agent.value.version,
    })
    ElMessage.success('创建成功')
    showCreateExperiment.value = false
    experimentForm.value = { name: '', evaluator_id: '', eval_set_id: '' }
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
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

</style>
