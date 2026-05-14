import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
});

export const SUPPORTED_FILE_EXTENSIONS = [
  'md', 'pdf', 'docx', 'doc', 'txt', 'xlsx', 'xls',
  'pptx', 'ppt', 'py', 'js', 'ts', 'java', 'c', 'cpp',
  'go', 'rs', 'html', 'htm', 'tex', 'rtf', 'csv', 'json',
  'yaml', 'yml', 'xml', 'sql', 'sh', 'bat', 'ps1',
  'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'wma', 'opus', 'webm',
  'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv',
];

export function validateUploadFile(file: File): string | null {
  if (file.size === 0) {
    return `文件 "${file.name}" 为空文件，不支持上传空文件`;
  }
  const ext = file.name.split('.').pop()?.toLowerCase();
  if (!ext || !SUPPORTED_FILE_EXTENSIONS.includes(ext)) {
    return `文件 "${file.name}" 的格式 (.${ext || '未知'}) 不被支持，请上传支持的文件类型`;
  }
  return null;
}

export interface StreamEvent {
  type: string;
  role?: string;
  content?: string;
  message?: string;
  iteration?: number;
  output?: string;
  critic_feedbacks?: string[];
  satisfied?: boolean;
  doc_id?: string;
  outline?: any;
  step?: string;
  percentage?: number;
  template?: string;
  filename?: string;
  file?: GeneratedFile;
  error?: string;
  skill_name?: string;
  suggested_mode?: string;
  reason?: string;
  conv_id?: string;
  title?: string;
  transcript?: string;
  method?: string;
  output_complete?: boolean;
  remaining_iterations?: number;
  approved?: boolean;
}

export interface GeneratedFile {
  filename: string;
  file_path: string;
  file_format: string;
  file_name: string;
  file_size: number;
  download_url: string;
  conv_id?: string;
  stored_filename?: string;
  relative_path?: string;
}

export interface MaterialTemplate {
  key: string;
  name: string;
  prompt: string;
  file_format: string;
  file_name: string;
  icon: string;
}

export async function* streamPost(url: string, body: any, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
  const response = await fetch(`/api${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  if (!response.body) throw new Error('No response body');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          if (data === '[DONE]') return;
          try {
            yield JSON.parse(data);
          } catch (e) {
            // skip malformed data
          }
        }
      }
    }
  } catch (e) {
    if (e instanceof Error && e.name === 'AbortError') {
      return;
    }
    throw e;
  }
}

export async function* streamUpload(url: string, formData: FormData, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
  const response = await fetch(`/api${url}`, {
    method: 'POST',
    body: formData,
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  if (!response.body) throw new Error('No response body');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          if (data === '[DONE]') return;
          try {
            yield JSON.parse(data);
          } catch (e) {
            // skip malformed data
          }
        }
      }
    }
  } catch (e) {
    if (e instanceof Error && e.name === 'AbortError') {
      return;
    }
    throw e;
  }
}

export const apiClient = {
  health: () => api.get('/health'),
  getProviders: () => api.get('/providers'),
  switchProvider: (provider: string, modelName?: string, apiKey?: string) =>
    api.post('/switch', { provider, model_name: modelName, api_key: apiKey }),
  getModels: () => api.get('/models'),
  getTaskModelMap: () => api.get('/task-model-map'),
  getProvidersDetail: () => api.get('/providers/detail'),

  discoverModels: (baseUrl: string, apiKey: string, providerId?: string, save: boolean = true) =>
    api.post('/models/discover', { base_url: baseUrl, api_key: apiKey, provider_id: providerId, save }),

  discoverExistingModels: () => api.post('/models/discover-existing'),

  testModel: (baseUrl: string, apiKey: string, modelName: string) =>
    api.post('/models/test', { base_url: baseUrl, api_key: apiKey, model_name: modelName }),

  addProvider: (baseUrl: string, apiKey: string, providerId?: string, providerName?: string, autoTest: boolean = true, autoFallbackChain: boolean = true) =>
    api.post('/providers/add', { base_url: baseUrl, api_key: apiKey, provider_id: providerId, provider_name: providerName, auto_test: autoTest, auto_fallback_chain: autoFallbackChain }),

  reloadModels: () => api.post('/models/reload'),

  generateMeetingMinutes: (transcript: string, language: string = 'zh', modelOverride?: string) =>
    api.post('/meeting/minutes', { transcript, language, model_override: modelOverride }),

  summarizeLiterature: (filePath: string, query: string = '请生成这篇文献的详细摘要', modelOverride?: string) =>
    api.post('/literature/summarize', { file_path: filePath, query, model_override: modelOverride }),

  uploadPDF: async (file: File, onProgress?: (progress: number) => void) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/tasks/upload-pdf', formData, {
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress((event.loaded / event.total) * 100);
        }
      },
    });
  },

  uploadLiteratureFile: async (file: File, mode: string = 'literature', convId?: string, onProgress?: (progress: number) => void) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mode', mode);
    if (convId) formData.append('conv_id', convId);
    return api.post('/literature/upload', formData, {
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress((event.loaded / event.total) * 100);
        }
      },
    });
  },

  uploadAudio: async (file: File, language: string = 'zh', mode: string = 'meeting', convId?: string, onProgress?: (progress: number) => void) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('language', language);
    formData.append('mode', mode);
    if (convId) formData.append('conv_id', convId);
    return api.post('/meeting/upload-audio', formData, {
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress((event.loaded / event.total) * 100);
        }
      },
    });
  },

  transcribeAudioSync: async (file: File, language: string = 'zh', mode: string = 'meeting', convId?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('language', language);
    formData.append('mode', mode);
    if (convId) formData.append('conv_id', convId);
    return api.post('/meeting/transcribe-sync', formData, {
      timeout: 180000,
    });
  },

  saveMeetingMinutes: (content: string, convId?: string, mode: string = 'meeting') =>
    api.post('/meeting/save-minutes', { content, conv_id: convId, mode }),

  polishText: (text: string, targetLanguage: string = 'auto', style: string = 'academic', modelOverride?: string, convId?: string) =>
    api.post('/polish', { text, target_language: targetLanguage, style, model_override: modelOverride, conv_id: convId }),

  detectPolishLanguage: (text: string) =>
    api.post('/polish/detect-language', { text }),

  uploadPolishFile: async (file: File, mode: string = 'polish', convId?: string, onProgress?: (progress: number) => void) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mode', mode);
    if (convId) formData.append('conv_id', convId);
    return api.post('/polish/upload', formData, {
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress((event.loaded / event.total) * 100);
        }
      },
    });
  },

  polishFile: (filePath: string, targetLanguage: string = 'auto', style: string = 'academic', userInstruction: string = '', inplace: boolean = false, modelOverride?: string, convId?: string) =>
    api.post('/polish/file', { file_path: filePath, target_language: targetLanguage, style, user_instruction: userInstruction, inplace, model_override: modelOverride, conv_id: convId }),

  downloadPolishFile: (filename: string, filePath?: string, mode: string = 'polish', convId?: string) =>
    filePath ? `/api/polish/download/${filename}?file_path=${encodeURIComponent(filePath)}&mode=${mode}&conv_id=${convId || ''}` : `/api/polish/download/${filename}?mode=${mode}&conv_id=${convId || ''}`,

  generatePPT: (topic: string, content: string = '', style: string = 'academic', template: string = 'default', modelOverride?: string, convId?: string) =>
    api.post('/ppt/generate', { topic, content, style, template, model_override: modelOverride, conv_id: convId }),

  renderPPTX: (outline: any, template: string = 'default', mode: string = 'ppt', convId?: string) =>
    api.post('/ppt/render', { outline, template, mode, conv_id: convId }),

  getPPTTemplates: () => api.get('/ppt/templates'),

  askAboutDocument: (docId: string, question: string, modelOverride?: string, convId?: string) =>
    api.post('/literature/ask', { doc_id: docId, question, model_override: modelOverride, conv_id: convId }),

  updateFilesConvId: (files: any[], convId: string, mode: string = 'general') =>
    api.post('/files/update-conv-id', { files, conv_id: convId, mode }),

  chat: (message: string, systemPrompt?: string, modelOverride?: string, autoGenerateFile?: boolean, fileFormat?: string, convId?: string, mode: string = 'chat') =>
    api.post('/chat', { message, system_prompt: systemPrompt, model_override: modelOverride, auto_generate_file: autoGenerateFile, file_format: fileFormat, conv_id: convId, mode }),

  getChatFiles: () => api.get('/chat/files'),

  downloadChatFile: (filename: string, mode: string = 'chat', convId?: string) => `/api/chat/download/${filename}?mode=${mode}&conv_id=${convId || ''}`,

  getMaterialTemplates: () => api.get('/chat/material-templates'),

  generateFile: (content: string, fileFormat: string = 'md', fileName: string = '内容', convId?: string, mode: string = 'chat') =>
    api.post('/chat/generate-file', { content, file_format: fileFormat, file_name: fileName, conv_id: convId, mode }),

  getTokenUsage: () => api.get('/token-usage'),

  getTasks: (status?: string) => api.get('/tasks', { params: { status } }),
  getTask: (taskId: string) => api.get(`/tasks/${taskId}`),

  getOfflineDemo: (taskType: string) => api.get(`/offline/demo/${taskType}`),

  createConversation: (taskType: string, initialMessage?: string) =>
    api.post('/conversations', { task_type: taskType, initial_message: initialMessage }),
  listConversations: (limit: number = 50, offset: number = 0, taskType?: string) =>
    api.get('/conversations', { params: { limit, offset, task_type: taskType } }),
  listConversationsByType: () => api.get('/conversations/by-type'),
  getConversation: (convId: string) => api.get(`/conversations/${convId}`),
  deleteConversation: (convId: string) => api.delete(`/conversations/${convId}`),
  addMessage: (convId: string, role: string, content: string) =>
    api.post('/conversations/message', { conv_id: convId, role, content }),
  generateTitle: (convId: string) =>
    api.post('/conversations/generate-title', { conv_id: convId }),
  searchConversations: (keyword: string, limit: number = 20) =>
    api.get(`/conversations/search/${keyword}`, { params: { limit } }),

  listSkills: () => api.get('/skills'),
  getSkill: (name: string) => api.get(`/skills/${name}`),
  executeSkill: (name: string, context: any, modelOverride?: string) =>
    api.post(`/skills/${name}/execute`, { context, model_override: modelOverride }),
  deleteSkill: (name: string) => api.delete(`/skills/${name}`),
  reloadSkills: () => api.post('/skills/reload'),
  importSkillFromGit: (url: string, branch: string = 'main', subpath: string = '') =>
    api.post('/skills/import/git', { url, branch, subpath }),
  importSkillFromZip: async (file: File, onProgress?: (progress: number) => void) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/skills/import/upload', formData, {
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress((event.loaded / event.total) * 100);
        }
      },
    });
  },

  importSkillFromFolder: async (formData: FormData, onProgress?: (progress: number) => void) => {
    return api.post('/skills/import/folder', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress((event.loaded / event.total) * 100);
        }
      },
    });
  },

  importSkillFromUrl: async (url: string) => {
    return api.post('/skills/import/url', { url });
  },

  uploadFile: async (file: File, mode: string = 'chat', convId?: string, subdir?: string, onProgress?: (progress: number) => void) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mode', mode);
    if (convId) formData.append('conv_id', convId);
    if (subdir) formData.append('subdir', subdir);
    return api.post('/files/upload', formData, {
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress((event.loaded / event.total) * 100);
        }
      },
    });
  },
};
