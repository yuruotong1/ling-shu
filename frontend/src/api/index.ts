import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

// ---- Agent ----
export const agentApi = {
  list: () => api.get('/agents'),
  create: (data: any) => api.post('/agents', data),
  get: (id: string) => api.get(`/agents/${id}`),
  update: (id: string, data: any) => api.put(`/agents/${id}`, data),
  delete: (id: string) => api.delete(`/agents/${id}`),
  versions: (id: string) => api.get(`/agents/${id}/versions`),
  rollback: (id: string, versionId: string) => api.post(`/agents/${id}/rollback/${versionId}`),
  test: (id: string, data: any) => api.post(`/agents/${id}/test`, data),
}

// ---- Skill ----
export const skillApi = {
  list: () => api.get('/skills'),
  create: (data: any) => api.post('/skills', data),
  get: (id: string) => api.get(`/skills/${id}`),
  update: (id: string, data: any) => api.put(`/skills/${id}`, data),
  delete: (id: string) => api.delete(`/skills/${id}`),
  versions: (id: string) => api.get(`/skills/${id}/versions`),
  rollback: (id: string, versionId: string) => api.post(`/skills/${id}/rollback/${versionId}`),
  test: (id: string, data: any) => api.post(`/skills/${id}/test`, data),
}

// ---- Tool ----
export const toolApi = {
  list: () => api.get('/tools'),
  create: (data: any) => api.post('/tools', data),
  get: (id: string) => api.get(`/tools/${id}`),
  update: (id: string, data: any) => api.put(`/tools/${id}`, data),
  delete: (id: string) => api.delete(`/tools/${id}`),
  test: (id: string, params: any) => api.post(`/tools/${id}/test`, { params }),
}

// ---- Model Config ----
export const modelConfigApi = {
  list: () => api.get('/model-configs'),
  create: (data: any) => api.post('/model-configs', data),
  get: (id: string) => api.get(`/model-configs/${id}`),
  update: (id: string, data: any) => api.put(`/model-configs/${id}`, data),
  delete: (id: string) => api.delete(`/model-configs/${id}`),
  test: (id: string) => api.post(`/model-configs/${id}/test`),
}

// ---- Evaluator ----
export const evaluatorApi = {
  list: () => api.get('/evaluators'),
  create: (data: any) => api.post('/evaluators', data),
  update: (id: string, data: any) => api.put(`/evaluators/${id}`, data),
  delete: (id: string) => api.delete(`/evaluators/${id}`),
}

// ---- Evaluation Set ----
export const evalSetApi = {
  list: () => api.get('/evaluation-sets'),
  create: (data: any) => api.post('/evaluation-sets', data),
  delete: (id: string) => api.delete(`/evaluation-sets/${id}`),
  listItems: (setId: string) => api.get(`/evaluation-sets/${setId}/items`),
  addItem: (setId: string, data: any) => api.post(`/evaluation-sets/${setId}/items`, data),
  deleteItem: (setId: string, itemId: string) => api.delete(`/evaluation-sets/${setId}/items/${itemId}`),
}

// ---- Experiment ----
export const experimentApi = {
  list: () => api.get('/experiments'),
  create: (data: any) => api.post('/experiments', data),
  get: (id: string) => api.get(`/experiments/${id}`),
  run: (id: string) => api.post(`/experiments/${id}/run`),
  results: (id: string) => api.get(`/experiments/${id}/results`),
  optimize: (expId: string, skillId: string, instruction?: string) =>
    api.post(`/experiments/${expId}/optimize-skill?skill_id=${skillId}&instruction=${encodeURIComponent(instruction || '')}`),
  delete: (id: string) => api.delete(`/experiments/${id}`),
}

// ---- Trace ----
export const traceApi = {
  list: (agentName?: string) => api.get('/traces', { params: { agent_name: agentName } }),
  get: (id: string) => api.get(`/traces/${id}`),
}

// ---- Knowledge Base ----
export const kbApi = {
  namespaces: () => api.get('/kb/namespaces'),
  deleteNamespace: (ns: string) => api.delete(`/kb/${encodeURIComponent(ns)}`),
  renameNamespace: (ns: string, newName: string) => api.post(`/kb/${encodeURIComponent(ns)}/rename`, { new_name: newName }),
  registerTools: (ns: string) => api.post(`/kb/${encodeURIComponent(ns)}/register-tools`),
  listDocs: (ns: string) => api.get(`/kb/${encodeURIComponent(ns)}/documents`),
  uploadDoc: (ns: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post(`/kb/${encodeURIComponent(ns)}/documents`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  deleteDoc: (ns: string, id: string) => api.delete(`/kb/${encodeURIComponent(ns)}/documents/${id}`),
  search: (ns: string, query: string, topK = 5) => api.post(`/kb/${encodeURIComponent(ns)}/search`, { query, top_k: topK }),
  listData: (ns: string) => api.get(`/kb/${encodeURIComponent(ns)}/data`),
  writeData: (ns: string, key: string, value: string) => api.post(`/kb/${encodeURIComponent(ns)}/data`, { key, value }),
  deleteData: (ns: string, key: string) => api.delete(`/kb/${encodeURIComponent(ns)}/data/${encodeURIComponent(key)}`),
}

export default api
