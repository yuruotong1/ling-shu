<template>
  <router-view v-if="$route.meta.public" />
  <el-container v-else class="app-container">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <span class="logo-icon">🧠</span>
        <span class="logo-text">灵枢引擎</span>
      </div>
      <el-menu :default-active="$route.path" router class="sidebar-menu">
        <el-menu-item index="/agents">
          <el-icon><Connection /></el-icon>
          <span>Agent 管理</span>
        </el-menu-item>
        <el-menu-item index="/skills">
          <el-icon><Tools /></el-icon>
          <span>Skill 管理</span>
        </el-menu-item>
        <el-menu-item index="/tools">
          <el-icon><Link /></el-icon>
          <span>工具管理</span>
        </el-menu-item>
        <el-menu-item index="/model-configs">
          <el-icon><Cpu /></el-icon>
          <span>模型配置</span>
        </el-menu-item>
        <el-divider />
        <el-menu-item index="/evaluators">
          <el-icon><DataAnalysis /></el-icon>
          <span>评估器</span>
        </el-menu-item>
        <el-menu-item index="/datasets">
          <el-icon><Files /></el-icon>
          <span>数据集</span>
        </el-menu-item>
        <el-menu-item index="/experiments">
          <el-icon><TrendCharts /></el-icon>
          <span>实验对比</span>
        </el-menu-item>
        <el-menu-item index="/traces">
          <el-icon><List /></el-icon>
          <span>调用链路</span>
        </el-menu-item>
        <el-divider v-if="authStore.isAdmin" />
        <el-menu-item v-if="authStore.isAdmin" index="/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>

      <div class="user-bar">
        <el-tag :type="authStore.isAdmin ? 'danger' : 'info'" size="small">
          {{ authStore.isAdmin ? 'admin' : 'operator' }}
        </el-tag>
        <span class="username">{{ authStore.username }}</span>
        <el-button link size="small" @click="handleLogout" style="color:#94a3b8">退出</el-button>
      </div>
    </el-aside>
    <el-main class="main-content">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const handleLogout = async () => {
  await ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' })
  authStore.logout()
  router.push('/login')
}
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body, #app { height: 100%; }
.app-container { height: 100vh; }

.sidebar {
  background: #1a1a2e;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 10px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  flex-shrink: 0;
}
.logo-icon { font-size: 24px; }
.logo-text { color: #e2e8f0; font-size: 16px; font-weight: 700; letter-spacing: 1px; }

.sidebar-menu {
  background: transparent !important;
  border: none !important;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}
/* 美化滚动条 */
.sidebar-menu::-webkit-scrollbar { width: 4px; }
.sidebar-menu::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 2px; }
.sidebar-menu::-webkit-scrollbar-track { background: transparent; }
.sidebar-menu .el-menu-item {
  color: #94a3b8 !important;
  height: 46px;
  margin: 2px 8px;
  border-radius: 6px;
}
.sidebar-menu .el-menu-item:hover,
.sidebar-menu .el-menu-item.is-active {
  background: rgba(99, 102, 241, 0.2) !important;
  color: #818cf8 !important;
}
.sidebar-menu .el-divider { border-color: rgba(255,255,255,0.1); margin: 8px 16px; }

.user-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,0.1);
  flex-shrink: 0;
}
.username { color: #94a3b8; font-size: 13px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.main-content {
  background: #f8fafc;
  padding: 24px;
  overflow-y: auto;
}
</style>
