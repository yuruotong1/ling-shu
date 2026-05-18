<template>
  <div>
    <div class="page-header">
      <div>
        <h2>用户管理</h2>
        <p class="subtitle">管理平台账号与权限角色</p>
      </div>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 新建用户
      </el-button>
    </div>

    <el-table :data="users" v-loading="loading" class="data-table">
      <el-table-column prop="username" label="用户名" />
      <el-table-column label="角色" width="120">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">{{ row.role }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" :type="row.is_active ? 'warning' : 'success'"
            @click="toggleActive(row)">{{ row.is_active ? '禁用' : '启用' }}</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建 -->
    <el-dialog v-model="showCreate" title="新建用户" width="420px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="createForm.username" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="createForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createForm.role" style="width:100%">
            <el-option label="admin（管理员）" value="admin" />
            <el-option label="operator（业务人员）" value="operator" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑 -->
    <el-dialog v-model="showEdit" title="编辑用户" width="420px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input :value="editTarget?.username" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="editForm.password" type="password" show-password placeholder="不修改留空" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role" style="width:100%">
            <el-option label="admin（管理员）" value="admin" />
            <el-option label="operator（业务人员）" value="operator" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { userApi } from '@/api'

const users = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const showCreate = ref(false)
const showEdit = ref(false)
const editTarget = ref<any>(null)
const createForm = ref({ username: '', password: '', role: 'operator' })
const editForm = ref({ password: '', role: 'operator' })

const load = async () => {
  loading.value = true
  try {
    const res = await userApi.list()
    users.value = res.data
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  saving.value = true
  try {
    await userApi.create(createForm.value)
    ElMessage.success('创建成功')
    showCreate.value = false
    createForm.value = { username: '', password: '', role: 'operator' }
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    saving.value = false
  }
}

const openEdit = (row: any) => {
  editTarget.value = row
  editForm.value = { password: '', role: row.role }
  showEdit.value = true
}

const handleEdit = async () => {
  saving.value = true
  try {
    const payload: any = { role: editForm.value.role }
    if (editForm.value.password) payload.password = editForm.value.password
    await userApi.update(editTarget.value.id, payload)
    ElMessage.success('已更新')
    showEdit.value = false
    await load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  } finally {
    saving.value = false
  }
}

const toggleActive = async (row: any) => {
  await userApi.update(row.id, { is_active: !row.is_active })
  ElMessage.success(row.is_active ? '已禁用' : '已启用')
  await load()
}

const handleDelete = async (row: any) => {
  await ElMessageBox.confirm(`确认删除用户 "${row.username}"？`, '删除确认', { type: 'warning' })
  await userApi.delete(row.id)
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
</style>
