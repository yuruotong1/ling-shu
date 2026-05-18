<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <div class="login-header">
        <span class="logo-icon">🧠</span>
        <h2>灵枢引擎</h2>
        <p>AI Agent 生产优化平台</p>
      </div>
      <el-form :model="form" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock"
            size="large" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="handleLogin">
          登录
        </el-button>
      </el-form>
      <div class="login-hint">默认：admin / admin123</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const form = ref({ username: '', password: '' })

const handleLogin = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await authApi.login(form.value.username, form.value.password)
    authStore.setAuth(res.data.access_token, res.data.role, res.data.username)
    ElMessage.success(`欢迎，${res.data.username}`)
    router.push('/')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
}
.login-card {
  width: 380px;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.12);
}
.login-header {
  text-align: center;
  margin-bottom: 28px;
}
.logo-icon { font-size: 40px; }
h2 { font-size: 22px; font-weight: 700; margin: 8px 0 4px; }
p { color: #94a3b8; font-size: 13px; }
.login-hint {
  text-align: center;
  color: #aaa;
  font-size: 12px;
  margin-top: 12px;
}
</style>
