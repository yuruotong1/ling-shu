<template>
  <el-button type="warning" size="small" @click="show = true">🤖 AI 生成</el-button>

  <el-dialog v-model="show" title="AI 生成提示词" width="600px">
    <el-form label-width="80px">
      <el-form-item label="类型">
        <el-tag>{{ typeLabel }}</el-tag>
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="desc" type="textarea" :rows="4"
          placeholder="描述你想要实现的功能，AI 会自动生成提示词..." />
      </el-form-item>
      <el-form-item v-if="result">
        <el-input v-model="result" type="textarea" :rows="6" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="show = false">关闭</el-button>
      <el-button v-if="result" type="primary" @click="apply">应用</el-button>
      <el-button type="warning" :loading="loading" @click="doGenerate">生成</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { aiGenerateApi } from '@/api'

const props = defineProps<{
  type: 'agent' | 'skill' | 'evaluator'
}>()
const emit = defineEmits<{
  (e: 'generated', val: string): void
}>()

const show = ref(false)
const desc = ref('')
const result = ref('')
const loading = ref(false)

const typeLabel = computed(() => {
  const map: Record<string, string> = { agent: 'Agent 系统提示词', skill: 'Skill 提示词', evaluator: '评估器提示词' }
  return map[props.type] || '提示词'
})

const doGenerate = async () => {
  if (!desc.value.trim()) {
    ElMessage.warning('请先描述功能需求')
    return
  }
  loading.value = true
  result.value = ''
  try {
    const r = await aiGenerateApi.prompt({ type: props.type, description: desc.value })
    result.value = r.data.prompt
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成失败')
  } finally {
    loading.value = false
  }
}

const apply = () => {
  emit('generated', result.value)
  show.value = false
  desc.value = ''
  result.value = ''
}
</script>
