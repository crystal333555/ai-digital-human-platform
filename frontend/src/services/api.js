import axios from 'axios'

const API_BASE = '/api/v1'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export { api }

// 头像管理API
export const avatarAPI = {
  upload: (formData) => api.post('/avatars/upload', formData, {
    headers: { 'Content-Type': undefined },
  }),
  list: () => api.get('/avatars/'),
  get: (id) => api.get(`/avatars/${id}`),
  update: (id, data) => api.put(`/avatars/${id}`, data),
  delete: (id) => api.delete(`/avatars/${id}`),
  removeBg: (id) => api.post(`/avatars/${id}/remove-bg`),
  backgrounds: () => api.get('/avatars/backgrounds/list'),
}

// 音色管理API
export const voiceAPI = {
  upload: (formData) => api.post('/voices/upload', formData, {
    headers: { 'Content-Type': undefined },  // 让 axios 自动设置 multipart boundary
  }),
  list: () => api.get('/voices/'),
  get: (id) => api.get(`/voices/${id}`),
  clone: (id) => api.post(`/voices/${id}/clone`, {}, { timeout: 120000 }),
  preview: (id, text) => api.get(`/voices/${id}/preview`, { params: { text }, timeout: 120000 }),
  delete: (id) => api.delete(`/voices/${id}`),
}

// 音色库API（预置音色 + 混合）
export const voiceLibAPI = {
  categories: () => api.get('/voice-lib/categories'),
  presets: (params) => api.get('/voice-lib/presets', { params }),
  presetDetail: (id) => api.get(`/voice-lib/presets/${id}`),
  testPreset: (id, text) => api.post(`/voice-lib/presets/${id}/test`, null, { params: { text } }),
  cloneToMine: (id, name) => api.post(`/voice-lib/presets/${id}/clone-to-mine`, { custom_name: name }),
  blend: (data) => api.post('/voice-lib/blend', data),
  blendPreview: (data) => api.post('/voice-lib/blend/preview', data),
  saveBlend: (data) => api.post('/voice-lib/blend/save', data),
  suggestRatios: (data) => api.post('/voice-lib/blend/suggest', data),
}

// 对话API
export const chatAPI = {
  createConversation: (data) => api.post('/chat/conversations', data),
  listConversations: () => api.get('/chat/conversations'),
  getMessages: (id) => api.get(`/chat/conversations/${id}/messages`),
  sendMessage: (data) => api.post('/chat/send', data),
}

// TTS API
export const ttsAPI = {
  synthesize: (data) => api.post('/tts/synthesize', data),
  voices: (lang) => api.get('/tts/voices', { params: { language: lang } }),
  test: (data) => api.post('/tts/test', data),
}

// WebSocket封装
export function createWebSocket(conversationId) {
  const wsUrl = `ws://localhost:8000/api/v1/chat/ws/${conversationId}`
  return new WebSocket(wsUrl)
}

// PPT API
export const pptAPI = {
  upload: (formData) => api.post('/ppt/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  listProjects: () => api.get('/ppt/projects'),
  getProject: (id) => api.get(`/ppt/projects/${id}`),
  updateProject: (id, data) => api.put(`/ppt/projects/${id}`, data),
  deleteProject: (id) => api.delete(`/ppt/projects/${id}`),
  updateSlide: (projectId, slideId, data) => api.put(`/ppt/projects/${projectId}/slides/${slideId}`, data),
  generateAll: (projectId, data) => api.post(`/ppt/projects/${projectId}/generate`, data),
  generateSlide: (projectId, slideId, data) => api.post(`/ppt/projects/${projectId}/slides/${slideId}/generate`, data),
  getSlideStatus: (projectId, slideId) => api.get(`/ppt/projects/${projectId}/slides/${slideId}/status`),
  mergeSlides: (projectId, slideIds) => api.post(`/ppt/projects/${projectId}/merge`, { slide_ids: slideIds }),
  getTask: (taskId) => api.get(`/ppt/tasks/${taskId}`),
  cancelTask: (taskId) => api.post(`/ppt/tasks/${taskId}/cancel`),
}
