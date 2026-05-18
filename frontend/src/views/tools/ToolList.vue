<template>
  <div>
    <div class="page-header">
      <div>
        <h2>工具管理</h2>
        <p class="subtitle">HTTP/HTTPS外部能力接入，供Skill调用</p>
      </div>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon> 注册工具
      </el-button>
    </div>

    <!-- 内置工具 -->
    <div class="section-title">内置工具</div>
    <div class="builtin-row">
      <el-card class="builtin-card" shadow="never">
        <div class="builtin-header">
          <el-icon class="builtin-icon"><DataBoard /></el-icon>
          <div>
            <div class="builtin-name">知识库</div>
            <div class="builtin-desc">向量检索 · 文档存储 · 键值数据 — 每个Skill自动分配命名空间</div>
          </div>
        </div>
        <div style="text-align:right;margin-top:12px">
          <el-button type="primary" @click="showKb = true">管理</el-button>
        </div>
      </el-card>
    </div>

    <div class="section-title" style="margin-top:24px">工具操作</div>

    <el-table :data="tools" v-loading="loading" class="data-table" row-key="id"
      :expand-row-keys="expandedIds" @expand-change="onExpandChange">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="inline-form" v-if="editForms[row.id]">
            <!-- 工具名称 / 描述 -->
            <el-form :model="editForms[row.id]" label-width="100px" style="margin-bottom:16px">
              <el-row :gutter="16">
                <el-col :span="12">
                  <el-form-item label="工具名称">
                    <el-input v-model="editForms[row.id].name" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="工具描述">
                    <el-input v-model="editForms[row.id].description" />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>

            <!-- 知识库工具：固定操作步骤展示 -->
            <template v-if="row.tool_type === 'builtin_kb'">
              <div class="step-section-label">操作步骤（内置，共 {{ KB_STEP_DEFS.length }} 个）</div>
              <el-row :gutter="12" style="margin-bottom:16px">
                <el-col :span="6" v-for="sd in KB_STEP_DEFS" :key="sd.op">
                  <div class="kb-step-card">
                    <div class="kb-step-header">
                      <el-tag size="small" type="success">{{ sd.name }}</el-tag>
                    </div>
                    <div class="kb-step-desc">{{ sd.description }}</div>
                    <div class="kb-step-params">
                      <span v-for="k in Object.keys(sd.schema?.properties || {})" :key="k" class="kb-step-param">{{ k }}</span>
                    </div>
                  </div>
                </el-col>
              </el-row>
            </template>

            <!-- HTTP 工具：可编辑操作步骤列表 -->
            <template v-else-if="stepForms[row.id]">
              <div class="step-section-label">操作步骤</div>
              <div v-for="(step, idx) in stepForms[row.id]" :key="idx" class="step-form-card">
                <div class="step-form-header">
                  <span class="step-num">步骤 {{ idx + 1 }}</span>
                  <el-button size="small" type="danger" text @click="removeStep(row.id, idx)"
                    :disabled="stepForms[row.id].length <= 1">
                    <el-icon><Delete /></el-icon> 删除
                  </el-button>
                </div>
                <el-form :model="step" label-width="100px">
                  <el-row :gutter="16">
                    <el-col :span="12">
                      <el-form-item label="步骤名称">
                        <el-input v-model="step.name" placeholder="如：创建用户" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="请求方法">
                        <el-select v-model="step.method" style="width:100%">
                          <el-option v-for="m in ['GET','POST','PUT','DELETE']" :key="m" :label="m" :value="m" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <el-form-item label="描述">
                    <el-input v-model="step.description" placeholder="功能描述（供LLM决策是否调用）" />
                  </el-form-item>
                  <el-form-item label="API地址">
                    <el-input v-model="step.api_url" placeholder="https://..." />
                  </el-form-item>
                  <el-form-item label="认证方式">
                    <el-select v-model="step.auth_type" style="width:100%" @change="step.auth_config = {}">
                      <el-option label="无认证" value="none" />
                      <el-option label="Bearer Token" value="bearer" />
                      <el-option label="API Key Header" value="apikey" />
                    </el-select>
                  </el-form-item>
                  <el-form-item v-if="step.auth_type === 'bearer'" label="Token">
                    <el-input v-model="step.auth_config.token" type="password" show-password />
                  </el-form-item>
                  <el-form-item v-if="step.auth_type === 'apikey'" label="Header名">
                    <el-input v-model="step.auth_config.key_name" placeholder="X-API-Key" />
                  </el-form-item>
                  <el-form-item v-if="step.auth_type === 'apikey'" label="Key值">
                    <el-input v-model="step.auth_config.key_value" type="password" show-password />
                  </el-form-item>
                  <el-form-item label="入参Schema">
                    <el-input v-model="step.schema_str" type="textarea" :rows="3"
                      placeholder='{"type":"object","properties":{...}}' />
                  </el-form-item>
                </el-form>
              </div>
              <div style="padding:4px 0 16px">
                <el-button size="small" @click="addStep(row.id)">
                  <el-icon><Plus /></el-icon> 添加步骤
                </el-button>
              </div>
            </template>

            <div>
              <el-button type="primary" @click="handleSave(row.id)" :loading="savingId === row.id">保存</el-button>
              <el-button @click="collapseRow(row.id)">取消</el-button>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column label="类型/方法" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.tool_type === 'builtin_kb'" size="small" type="success">知识库</el-tag>
          <el-tag v-else size="small">{{ row.method }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="API地址 / 知识库" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.tool_type === 'builtin_kb'" style="color:#6b7280;font-size:13px">
            {{ row.kb_namespace }} · {{ opLabel(row.kb_operation) }}
          </span>
          <span v-else>{{ row.api_url }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="call_count" label="调用次数" width="100" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.tool_type !== 'builtin_kb'" size="small" type="success" @click="openTest(row)">测试连通</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 注册工具 -->
    <el-dialog v-model="showCreate" title="注册工具" width="700px">
      <el-form :model="createForm" label-width="110px">
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" />
        </el-form-item>
        <el-form-item label="描述" required>
          <el-input v-model="createForm.description" placeholder="功能描述（供LLM决策是否调用）" />
        </el-form-item>
        <el-form-item label="API地址" required>
          <el-input v-model="createForm.api_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="请求方法">
          <el-select v-model="createForm.method">
            <el-option v-for="m in ['GET','POST','PUT','DELETE']" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="认证方式">
          <el-select v-model="createAuthType" @change="createForm.auth_config = {}">
            <el-option label="无认证" value="none" />
            <el-option label="Bearer Token" value="bearer" />
            <el-option label="API Key Header" value="apikey" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="createAuthType === 'bearer'" label="Token">
          <el-input v-model="createForm.auth_config.token" type="password" show-password />
        </el-form-item>
        <el-form-item v-if="createAuthType === 'apikey'" label="Header名">
          <el-input v-model="createForm.auth_config.key_name" placeholder="X-API-Key" />
        </el-form-item>
        <el-form-item v-if="createAuthType === 'apikey'" label="Key值">
          <el-input v-model="createForm.auth_config.key_value" type="password" show-password />
        </el-form-item>
        <el-form-item label="入参Schema">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span />
            <el-button size="small" @click="showGenerateSchema = true">🤖 AI 生成 Schema</el-button>
          </div>
          <el-input v-model="createSchemaStr" type="textarea" :rows="5"
            placeholder='{"type":"object","properties":{...}}' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">注册</el-button>
      </template>
    </el-dialog>

    <!-- AI 生成 Schema 对话框 -->
    <el-dialog v-model="showGenerateSchema" title="AI 生成入参 Schema" width="600px">
      <el-form label-width="100px">
        <el-form-item label="描述需求">
          <el-input v-model="schemaDesc" type="textarea" :rows="4" placeholder="例如：查询订单接口，需要订单号（字符串）、开始时间、结束时间" />
        </el-form-item>
        <el-form-item>
          <el-button type="warning" :loading="generatingSchema" @click="doGenerateSchema">🤖 AI 生成 Schema</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateSchema = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 知识库管理 -->
    <el-dialog v-model="showKb" title="知识库管理" width="860px" @open="kbOnOpen">
      <div class="kb-layout">
        <!-- 左侧知识库列表 -->
        <div class="kb-sidebar">
          <div class="kb-ns-header">
            <span>知识库</span>
            <el-button size="small" type="primary" @click="showNewNs = true">
              <el-icon><Plus /></el-icon> 新建
            </el-button>
          </div>
          <div v-for="ns in namespaces" :key="ns"
            :class="['kb-ns-item', { active: activeNs === ns }]"
            @click="selectNs(ns)">
            <template v-if="renamingNs === ns">
              <el-input
                v-model="renameValue"
                size="small"
                @click.stop
                @keyup.enter="confirmRename(ns)"
                @keyup.esc="renamingNs = ''"
                style="width:100%"
                autofocus
              />
            </template>
            <template v-else>
              <span class="kb-ns-name">{{ ns }}</span>
              <span class="kb-ns-actions" @click.stop>
                <el-tooltip content="重命名" placement="top">
                  <el-icon class="kb-action-icon" @click.stop="startRename(ns)"><Edit /></el-icon>
                </el-tooltip>
                <el-tooltip content="删除" placement="top">
                  <el-icon class="kb-action-icon danger" @click.stop="deleteNs(ns)"><Delete /></el-icon>
                </el-tooltip>
              </span>
            </template>
          </div>
          <div v-if="!namespaces.length" class="kb-ns-empty">暂无知识库，点击新建</div>
        </div>

        <!-- 右侧内容 -->
        <div class="kb-content">
          <div v-if="!activeNs" class="kb-placeholder">← 选择或新建知识库</div>
          <template v-else>
          <div class="kb-register-bar">
            <span class="kb-register-tip">为「{{ activeNs }}」注册可供 Skill 调用的操作工具</span>
            <el-button size="small" type="primary" @click="handleRegisterTools" :loading="registering">
              一键注册操作工具
            </el-button>
          </div>
          <el-tabs v-model="kbTab">

            <!-- 文档 -->
            <el-tab-pane label="文档" name="docs">
              <div class="kb-toolbar">
                <el-upload :before-upload="uploadDoc" :show-file-list="false" accept=".txt,.md,.markdown">
                  <el-button type="primary" size="small" :loading="uploading">
                    <el-icon><Upload /></el-icon> 上传文档
                  </el-button>
                </el-upload>
                <span class="kb-hint">支持 .txt / .md</span>
              </div>
              <el-table :data="kbDocs" v-loading="docsLoading" size="small">
                <el-table-column prop="filename" label="文件名" />
                <el-table-column prop="chunk_count" label="分块数" width="80" />
                <el-table-column label="上传时间" width="160">
                  <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
                </el-table-column>
                <el-table-column label="操作" width="80">
                  <template #default="{ row }">
                    <el-button size="small" type="danger" @click="deleteDoc(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <!-- 键值 -->
            <el-tab-pane label="键值数据" name="kv">
              <div class="kb-toolbar">
                <el-input v-model="kvKey" placeholder="键" style="width:160px" size="small" />
                <el-input v-model="kvValue" placeholder="值" style="width:260px;margin:0 8px" size="small" />
                <el-button type="primary" size="small" @click="writeKv" :loading="kvSaving">写入</el-button>
              </div>
              <el-table :data="kbKvList" v-loading="kvLoading" size="small">
                <el-table-column prop="key" label="键" width="180" />
                <el-table-column prop="value" label="值" show-overflow-tooltip />
                <el-table-column label="时间" width="160">
                  <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
                </el-table-column>
                <el-table-column label="操作" width="80">
                  <template #default="{ row }">
                    <el-button size="small" type="danger" @click="deleteKv(row.key)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <!-- 搜索 -->
            <el-tab-pane label="语义检索" name="search">
              <div class="kb-toolbar">
                <el-input v-model="searchQuery" placeholder="输入检索词..." style="flex:1" size="small" />
                <el-input-number v-model="searchTopK" :min="1" :max="20" size="small" style="width:90px;margin:0 8px" />
                <el-button type="primary" size="small" @click="runSearch" :loading="searching">检索</el-button>
              </div>
              <div v-for="(r, i) in searchResults" :key="i" class="search-result">
                <div class="search-meta">
                  <el-tag size="small">{{ r.source }}</el-tag>
                  <span class="search-score">匹配度 {{ (r.score * 100).toFixed(0) }}%</span>
                </div>
                <div class="search-text">{{ r.content }}</div>
              </div>
              <div v-if="searchResults.length === 0 && !searching" style="color:#94a3b8;font-size:13px;margin-top:12px">
                输入关键词后点击检索
              </div>
            </el-tab-pane>

          </el-tabs>
          </template>
        </div>
      </div>

      <!-- 新建知识库 -->
      <el-dialog v-model="showNewNs" title="新建知识库" width="360px" append-to-body>
        <el-input v-model="newNsName" placeholder="知识库名称，如：产品文档、用例库" @keyup.enter="createNs" />
        <template #footer>
          <el-button @click="showNewNs = false">取消</el-button>
          <el-button type="primary" @click="createNs">创建</el-button>
        </template>
      </el-dialog>
    </el-dialog>

    <!-- 测试 -->
    <el-dialog v-model="showTestDialog" title="连通测试" width="600px">
      <el-input v-model="testParamsStr" type="textarea" :rows="4" placeholder='{"key": "value"}' />
      <el-button type="primary" @click="runTest" :loading="testing" style="margin-top:12px">发送请求</el-button>
      <div v-if="testResult" style="margin-top:16px">
        <el-alert :type="testResult.success ? 'success' : 'error'"
          :title="testResult.success ? '请求成功' : '请求失败'" show-icon>
          <pre style="white-space:pre-wrap;margin-top:8px">{{ testResult.output || testResult.error }}</pre>
        </el-alert>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { toolApi, kbApi, aiGenerateApi } from '@/api'

const tools = ref<any[]>([])
const loading = ref(false)
const showCreate = ref(false)
const showTestDialog = ref(false)
const creating = ref(false)
const testing = ref(false)
const savingId = ref<string | null>(null)
const testingId = ref<string | null>(null)
const testParamsStr = ref('{}')
const testResult = ref<any>(null)
const expandedIds = ref<string[]>([])
const showGenerateSchema = ref(false)
const schemaDesc = ref('')
const generatingSchema = ref(false)

// per-row edit state
const editForms = ref<Record<string, any>>({})
const authTypes = ref<Record<string, string>>({})
const schemaStrs = ref<Record<string, string>>({})

// per-row step forms
const stepForms = ref<Record<string, any[]>>({})

const KB_STEP_DEFS = [
  { op: 'search', name: '查询', description: '根据关键词检索知识库内容', schema: { properties: { query: {}, top_k: {} } } },
  { op: 'add',    name: '新增', description: '写入新的知识条目（键值对）', schema: { properties: { key: {}, value: {} } } },
  { op: 'delete', name: '删除', description: '删除指定键名的知识条目', schema: { properties: { key: {} } } },
  { op: 'list',   name: '列举', description: '列出所有知识条目', schema: { properties: {} } },
]

const _makeStep = (s?: any) => ({
  name: s?.name || '',
  description: s?.description || '',
  api_url: s?.api_url || '',
  method: s?.method || 'POST',
  auth_type: s?.auth_config?.type || 'none',
  auth_config: { ...(s?.auth_config || {}) },
  schema_str: JSON.stringify(s?.input_schema || {}, null, 2),
})

const addStep = (id: string) => {
  stepForms.value[id] = [...(stepForms.value[id] || []), _makeStep()]
}

const removeStep = (id: string, idx: number) => {
  stepForms.value[id] = stepForms.value[id].filter((_: any, i: number) => i !== idx)
}

// create form
const createAuthType = ref('none')
const createSchemaStr = ref('{"type":"object","properties":{}}')
const createForm = ref({ name: '', description: '', api_url: '', method: 'POST', auth_config: {} as any, input_schema: {} })

const load = async () => {
  loading.value = true
  try {
    const r = await toolApi.list()
    tools.value = r.data
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  createForm.value = { name: '', description: '', api_url: '', method: 'POST', auth_config: {}, input_schema: {} }
  createAuthType.value = 'none'
  createSchemaStr.value = '{"type":"object","properties":{}}'
  showCreate.value = true
}

const openEdit = (row: any) => {
  editForms.value[row.id] = { name: row.name, description: row.description }
  if (row.tool_type !== 'builtin_kb') {
    const rawSteps: any[] = row.steps || []
    stepForms.value[row.id] = rawSteps.length
      ? rawSteps.map(_makeStep)
      : [_makeStep(row)]  // 向后兼容：从工具字段派生一个步骤
  }
  if (!expandedIds.value.includes(row.id)) {
    expandedIds.value = [...expandedIds.value, row.id]
  }
}

const collapseRow = (id: string) => {
  expandedIds.value = expandedIds.value.filter(i => i !== id)
}

const onExpandChange = (row: any, expanded: boolean) => {
  if (expanded) {
    openEdit(row)
  } else {
    collapseRow(row.id)
  }
}

const handleSave = async (id: string) => {
  const base = editForms.value[id]
  const row = tools.value.find((t: any) => t.id === id)
  savingId.value = id
  try {
    if (row?.tool_type === 'builtin_kb') {
      await toolApi.update(id, { name: base.name, description: base.description })
    } else {
      const steps = (stepForms.value[id] || []).map((s: any) => {
        let input_schema = {}
        try { input_schema = JSON.parse(s.schema_str || '{}') } catch {
          ElMessage.error(`步骤"${s.name}"的入参Schema不是有效JSON`); throw new Error('invalid json')
        }
        const auth_config = s.auth_type !== 'none' ? { ...s.auth_config, type: s.auth_type } : {}
        return { name: s.name, description: s.description, api_url: s.api_url, method: s.method, auth_config, input_schema }
      })
      await toolApi.update(id, { name: base.name, description: base.description, steps })
    }
    ElMessage.success('保存成功')
    collapseRow(id)
    await load()
  } catch (e: any) {
    if (e.message !== 'invalid json') ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    savingId.value = null
  }
}

const handleCreate = async () => {
  try {
    createForm.value.input_schema = JSON.parse(createSchemaStr.value)
  } catch {
    ElMessage.error('入参Schema不是有效JSON')
    return
  }
  if (createAuthType.value !== 'none') {
    createForm.value.auth_config.type = createAuthType.value
  } else {
    createForm.value.auth_config = {}
  }
  creating.value = true
  try {
    await toolApi.create(createForm.value)
    ElMessage.success('注册成功')
    showCreate.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '注册失败')
  } finally {
    creating.value = false
  }
}

const doGenerateSchema = async () => {
  if (!schemaDesc.value.trim()) {
    ElMessage.warning('请先描述入参需求')
    return
  }
  generatingSchema.value = true
  try {
    const r = await aiGenerateApi.schema({ description: schemaDesc.value })
    const generated = r.data.schema
    if (generated) {
      createSchemaStr.value = JSON.stringify(generated, null, 2)
      ElMessage.success('AI 已生成 Schema，已填充到输入框')
      showGenerateSchema.value = false
    } else {
      ElMessage.error('生成失败，未返回有效 Schema')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    generatingSchema.value = false
  }
}

const openTest = (row: any) => {
  testingId.value = row.id
  testParamsStr.value = '{}'
  testResult.value = null
  showTestDialog.value = true
}

const runTest = async () => {
  testing.value = true
  testResult.value = null
  try {
    const params = JSON.parse(testParamsStr.value)
    const r = await toolApi.test(testingId.value!, params)
    testResult.value = r.data
  } catch (e: any) {
    testResult.value = { success: false, error: e.message }
  } finally {
    testing.value = false
  }
}

const handleDelete = async (row: any) => {
  await ElMessageBox.confirm(`确认删除工具 "${row.name}"？`, '删除确认', { type: 'warning' })
  await toolApi.delete(row.id)
  ElMessage.success('已删除')
  await load()
}

// ---- Knowledge Base ----
const showKb = ref(false)
const namespaces = ref<string[]>([])
const activeNs = ref('')
const kbTab = ref('docs')
const showNewNs = ref(false)
const newNsName = ref('')
const renamingNs = ref('')
const renameValue = ref('')
const registering = ref(false)

const OP_LABELS: Record<string, string> = { search: '查询', add: '新增', delete: '删除', list: '列举' }
const opLabel = (op: string) => OP_LABELS[op] || op

const kbDocs = ref<any[]>([])
const docsLoading = ref(false)
const uploading = ref(false)

const kbKvList = ref<any[]>([])
const kvLoading = ref(false)
const kvSaving = ref(false)
const kvKey = ref('')
const kvValue = ref('')

const searchQuery = ref('')
const searchTopK = ref(5)
const searching = ref(false)
const searchResults = ref<any[]>([])

const kbOnOpen = async () => {
  const r = await kbApi.namespaces()
  namespaces.value = r.data
  if (namespaces.value.length && !activeNs.value) {
    await selectNs(namespaces.value[0])
  }
}

const selectNs = async (ns: string) => {
  activeNs.value = ns
  kbTab.value = 'docs'
  searchResults.value = []
  await loadDocs()
  await loadKv()
}

const loadDocs = async () => {
  docsLoading.value = true
  try {
    const r = await kbApi.listDocs(activeNs.value)
    kbDocs.value = r.data
  } finally {
    docsLoading.value = false
  }
}

const loadKv = async () => {
  kvLoading.value = true
  try {
    const r = await kbApi.listData(activeNs.value)
    kbKvList.value = r.data
  } finally {
    kvLoading.value = false
  }
}

const uploadDoc = async (file: File) => {
  uploading.value = true
  try {
    await kbApi.uploadDoc(activeNs.value, file)
    ElMessage.success(`已上传 ${file.name}`)
    await loadDocs()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
  return false
}

const deleteDoc = async (row: any) => {
  await kbApi.deleteDoc(activeNs.value, row.id)
  ElMessage.success('已删除')
  await loadDocs()
}

const writeKv = async () => {
  if (!kvKey.value.trim()) return
  kvSaving.value = true
  try {
    await kbApi.writeData(activeNs.value, kvKey.value.trim(), kvValue.value)
    ElMessage.success('已写入')
    kvKey.value = ''
    kvValue.value = ''
    await loadKv()
  } finally {
    kvSaving.value = false
  }
}

const deleteKv = async (key: string) => {
  await kbApi.deleteData(activeNs.value, key)
  ElMessage.success('已删除')
  await loadKv()
}

const runSearch = async () => {
  if (!searchQuery.value.trim()) return
  searching.value = true
  try {
    const r = await kbApi.search(activeNs.value, searchQuery.value, searchTopK.value)
    searchResults.value = r.data.results
    if (!searchResults.value.length) ElMessage.info('未找到相关内容')
  } finally {
    searching.value = false
  }
}

const createNs = async () => {
  const ns = newNsName.value.trim()
  if (!ns) return
  if (!namespaces.value.includes(ns)) {
    await kbApi.writeData(ns, '__init__', '1')
    namespaces.value = [...namespaces.value, ns]
    await kbApi.registerTools(ns)
    await load()
  }
  showNewNs.value = false
  newNsName.value = ''
  await selectNs(ns)
}

const handleRegisterTools = async () => {
  registering.value = true
  try {
    const r = await kbApi.registerTools(activeNs.value)
    const created: string[] = r.data.created
    if (created.length) {
      ElMessage.success(`已注册 ${created.length} 个工具：${created.join('、')}`)
      await load()
    } else {
      ElMessage.info('操作工具已全部注册，无需重复创建')
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '注册失败')
  } finally {
    registering.value = false
  }
}

const startRename = (ns: string) => {
  renamingNs.value = ns
  renameValue.value = ns
}

const confirmRename = async (oldNs: string) => {
  const newNs = renameValue.value.trim()
  renamingNs.value = ''
  if (!newNs || newNs === oldNs) return
  try {
    await kbApi.renameNamespace(oldNs, newNs)
    const idx = namespaces.value.indexOf(oldNs)
    if (idx !== -1) namespaces.value[idx] = newNs
    await load()
    if (activeNs.value === oldNs) await selectNs(newNs)
    ElMessage.success('重命名成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '重命名失败')
  }
}

const deleteNs = async (ns: string) => {
  await ElMessageBox.confirm(`确认删除知识库"${ns}"及其所有数据和工具操作？`, '删除确认', { type: 'warning' })
  await kbApi.deleteNamespace(ns)
  namespaces.value = namespaces.value.filter(n => n !== ns)
  if (activeNs.value === ns) {
    activeNs.value = ''
    kbDocs.value = []
    kbKvList.value = []
  }
  await load()
  ElMessage.success('已删除')
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
h2 { font-size: 20px; font-weight: 600; }
.subtitle { color: #94a3b8; font-size: 14px; margin-top: 4px; }
.data-table { background: white; border-radius: 8px; }
.inline-form { padding: 16px 40px 8px; background: #f8fafc; }
.section-title { font-weight: 600; font-size: 14px; color: #374151; margin-bottom: 12px; }
.builtin-row { display: flex; gap: 16px; margin-bottom: 8px; }
.builtin-card { width: 360px; }
.builtin-header { display: flex; align-items: flex-start; gap: 12px; }
.builtin-icon { font-size: 28px; color: #6366f1; margin-top: 2px; }
.builtin-name { font-weight: 600; font-size: 15px; margin-bottom: 4px; }
.builtin-desc { font-size: 12px; color: #6b7280; line-height: 1.5; }

/* KB dialog */
.kb-layout { display: flex; gap: 0; height: 500px; }
.kb-sidebar { width: 180px; border-right: 1px solid #e5e7eb; padding: 8px 0; overflow-y: auto; flex-shrink: 0; }
.kb-ns-header { display: flex; justify-content: space-between; align-items: center; padding: 4px 12px 8px; font-size: 12px; color: #6b7280; font-weight: 600; }
.kb-ns-item { display: flex; align-items: center; padding: 7px 10px; font-size: 13px; cursor: pointer; border-radius: 4px; margin: 2px 6px; }
.kb-ns-item:hover { background: #f3f4f6; }
.kb-ns-item.active { background: #eff6ff; color: #2563eb; font-weight: 500; }
.kb-ns-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kb-ns-actions { display: none; align-items: center; gap: 4px; flex-shrink: 0; }
.kb-ns-item:hover .kb-ns-actions { display: flex; }
.kb-action-icon { font-size: 13px; color: #6b7280; padding: 2px; border-radius: 3px; cursor: pointer; }
.kb-action-icon:hover { color: #2563eb; background: #dbeafe; }
.kb-action-icon.danger:hover { color: #dc2626; background: #fee2e2; }
.kb-ns-empty { padding: 12px; font-size: 12px; color: #94a3b8; text-align: center; }
.kb-content { flex: 1; padding: 0 16px; overflow-y: auto; }
.kb-placeholder { display: flex; align-items: center; justify-content: center; height: 100%; color: #94a3b8; font-size: 14px; }
.step-section-label { font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid #e5e7eb; }
.step-form-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 12px; background: #fafafa; }
.step-form-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.step-num { font-size: 13px; font-weight: 600; color: #6366f1; }
.kb-step-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; background: #f9fafb; }
.kb-step-header { margin-bottom: 6px; }
.kb-step-desc { font-size: 12px; color: #6b7280; margin-bottom: 8px; line-height: 1.4; }
.kb-step-params { display: flex; flex-wrap: wrap; gap: 4px; }
.kb-step-param { font-size: 11px; background: #e0f2fe; color: #0369a1; padding: 1px 6px; border-radius: 4px; }
.kb-register-bar { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px; margin-bottom: 12px; }
.kb-register-tip { font-size: 13px; color: #0369a1; }
.kb-toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.kb-hint { font-size: 12px; color: #94a3b8; }
.search-result { border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px 12px; margin-bottom: 10px; }
.search-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.search-score { font-size: 12px; color: #6b7280; }
.search-text { font-size: 13px; color: #374151; line-height: 1.6; white-space: pre-wrap; }
</style>
