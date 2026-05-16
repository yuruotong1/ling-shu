import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/agents' },
    { path: '/agents', component: () => import('@/views/agents/AgentList.vue') },
    { path: '/agents/:id', component: () => import('@/views/agents/AgentDetail.vue') },
    { path: '/skills', component: () => import('@/views/skills/SkillList.vue') },
    { path: '/skills/:id', component: () => import('@/views/skills/SkillDetail.vue') },
    { path: '/tools', component: () => import('@/views/tools/ToolList.vue') },
    { path: '/model-configs', component: () => import('@/views/model-configs/ModelConfigList.vue') },
    { path: '/evaluators', component: () => import('@/views/evaluations/EvaluatorList.vue') },
    { path: '/datasets', component: () => import('@/views/datasets/DatasetList.vue') },
    { path: '/experiments', component: () => import('@/views/evaluations/ExperimentList.vue') },
    { path: '/experiments/:id', component: () => import('@/views/evaluations/ExperimentDetail.vue') },
    { path: '/traces', component: () => import('@/views/traces/TraceList.vue') },
  ]
})

export default router
