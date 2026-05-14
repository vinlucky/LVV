<template>
  <div class="relative space-y-3">
    <div v-if="uploadedFiles.length > 0" class="flex items-center space-x-2 overflow-x-auto pb-1">
      <div
        v-for="(f, idx) in uploadedFiles"
        :key="idx"
        class="flex-shrink-0 flex items-center space-x-1.5 bg-green-50 border border-green-300 rounded-md px-2.5 py-1.5 text-xs"
      >
        <span class="text-green-700">{{ fileIcon(f.filename) }} {{ f.filename }}</span>
        <button @click="removeFile(idx)" class="text-red-400 hover:text-red-600">✕</button>
      </div>
    </div>

    <div v-if="isUploading || (uploadProgress > 0 && uploadProgress < 100)" class="space-y-1">
      <div class="flex items-center space-x-2">
        <svg class="animate-spin h-3 w-3 text-primary-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span class="text-[10px] text-primary-500 font-medium">上传中 {{ uploadProgress > 0 ? uploadProgress + '%' : '...' }}</span>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-1.5">
        <div class="bg-primary-500 h-1.5 rounded-full transition-all duration-300" :style="{ width: (uploadProgress > 0 ? uploadProgress : 5) + '%' }"></div>
      </div>
    </div>

    <div class="flex items-center space-x-4 mb-2">
      <label class="flex items-center space-x-1.5 cursor-pointer">
        <input type="checkbox" v-model="skipThinking" class="w-3.5 h-3.5 rounded border-gray-300 text-primary-500 focus:ring-primary-300" />
        <span class="text-[10px] text-gray-500">⚡ 跳过思考过程，直接输出</span>
      </label>
    </div>

    <div class="flex space-x-2">
      <textarea
        v-model="query"
        class="flex-1 border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-300 resize-y min-h-[60px] max-h-[200px]"
        rows="3"
        :placeholder="uploadedFiles.length > 0 ? '查询问题（留空则生成摘要）（Shift+Enter换行）' : '拖拽文件到页面任意位置，或点击下方按钮选择（Shift+Enter换行）'"
        @keydown.enter.exact.prevent="generateSummary"
      ></textarea>
      <div class="flex flex-col space-y-1">
        <input ref="fileInput" type="file" accept=".pdf,.md,.docx,.doc,.txt,.xlsx,.xls,.pptx,.ppt,.py,.js,.ts,.java,.c,.cpp,.go,.rs" class="hidden" multiple @change="handleFileSelect" />
        <button
          @click="($refs.fileInput as any)?.click()"
          class="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-xs hover:bg-gray-200"
        >
          📁 选择文件
        </button>
        <button
          @click="generateSummary"
          :disabled="store.isProcessing || uploadedFiles.length === 0"
          class="px-4 py-2 bg-primary-500 text-white rounded-lg text-xs font-medium disabled:opacity-50"
        >
          {{ store.isProcessing ? '处理中...' : '📝 摘要' }}
        </button>
      </div>
    </div>
    <div v-if="docId" class="flex space-x-2">
      <input
        v-model="followUpQuestion"
        class="flex-1 border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-300"
        placeholder="对文档追问..."
        @keydown.enter.exact.prevent="askFollowUp"
      />
      <button
        @click="askFollowUp"
        :disabled="!followUpQuestion"
        class="px-3 py-2 bg-blue-500 text-white rounded-lg text-xs disabled:opacity-50"
      >
        提问
      </button>
    </div>
    <div v-if="generatedFiles.length > 0" class="border-t pt-2">
      <div class="text-[10px] text-gray-400 font-medium mb-1.5">📎 生成文件</div>
      <div class="flex flex-wrap gap-2">
        <a
          v-for="gf in generatedFiles"
          :key="gf.filename"
          :href="getFileDownloadUrl(gf)"
          :download="gf.filename"
          class="inline-flex items-center space-x-1.5 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-xs text-blue-700 hover:bg-blue-100 hover:border-blue-300 transition-colors"
        >
          <span class="text-sm">{{ formatIcon(gf.file_format) }}</span>
          <span class="font-medium">{{ gf.file_name || gf.filename }}</span>
          <span class="text-blue-400">⬇</span>
        </a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { useAppStore } from '../stores/app';
import { streamPost, apiClient, validateUploadFile } from '../utils/api';
import type { GeneratedFile } from '../utils/api';

const store = useAppStore();
const query = ref('请生成这篇文献的详细摘要');
const docId = ref('');
const followUpQuestion = ref('');
const uploadProgress = ref(0);
const isUploading = ref(false);
const skipThinking = ref(false);
const generatedFileInfo = ref<any>(null);

const generatedFiles = computed(() => {
  if (!store.currentConvId) return [];
  return store.generatedFiles.filter(f => f.conv_id === store.currentConvId);
});

interface FileInfo {
  filename: string;
  file_path: string;
  stored_filename: string;
  relative_path?: string;
}
const uploadedFiles = ref<FileInfo[]>([]);

function fileIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase();
  const icons: Record<string, string> = { pdf: '📄', md: '📝', docx: '📃', doc: '📃', xlsx: '📊', xls: '📊', pptx: '📊', ppt: '📊', txt: '📄', py: '🐍', js: '📜', ts: '📜', java: '☕', c: '⚙️', cpp: '⚙️', go: '🔵', rs: '🦀' };
  return icons[ext || ''] || '📄';
}

function formatIcon(fmt: string): string {
  const icons: Record<string, string> = { md: '📝', html: '🌐', txt: '📄', pdf: '📄' };
  return icons[fmt] || '📄';
}

function getFileDownloadUrl(file: GeneratedFile): string {
  if (file.relative_path) {
    return `/api/files/download/${file.relative_path}`;
  }
  const storedName = file.stored_filename || file.filename;
  return `/api/chat/download/${storedName}?mode=literature&conv_id=${store.currentConvId || ''}`;
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files;
  if (files) {
    for (let i = 0; i < files.length; i++) {
      await uploadFile(files[i]);
    }
  }
  input.value = '';
}

async function uploadFile(file: File) {
  const validationError = validateUploadFile(file);
  if (validationError) {
    alert(validationError);
    return;
  }

  isUploading.value = true;
  uploadProgress.value = 5;
  try {
    const convId = store.currentConvId || undefined;
    const res = await apiClient.uploadLiteratureFile(file, 'literature', convId, (progress) => {
      uploadProgress.value = Math.round(progress);
    });
    uploadedFiles.value.push({
      filename: res.data.filename,
      file_path: res.data.file_path,
      stored_filename: res.data.stored_filename || res.data.file_path.split(/[/\\]/).pop() || res.data.filename,
      relative_path: res.data.relative_path,
    });
    uploadProgress.value = 100;
    setTimeout(() => { uploadProgress.value = 0; isUploading.value = false; }, 1000);
  } catch (e) {
    console.error('Upload failed:', e);
    uploadProgress.value = 0;
    isUploading.value = false;
  }
}

function removeFile(idx: number) {
  uploadedFiles.value.splice(idx, 1);
}

function getPrimaryFilePath(): string {
  return uploadedFiles.value.length > 0 ? uploadedFiles.value[0].file_path : '';
}

async function generateSummary() {
  const filePath = getPrimaryFilePath();
  if (!filePath) return;

  if (store.offlineMode) {
    await store.loadOfflineDemo('literature_summary');
    return;
  }

  store.currentRefFiles = uploadedFiles.value.map(f => ({ filename: f.filename, file_path: f.file_path, stored_filename: f.stored_filename, relative_path: f.relative_path, download_url: f.relative_path ? `/api/files/download/${f.relative_path}` : `/api/files/download/${f.stored_filename}` }));
  store.lastUserMessage = query.value;

  let convId = store.currentConvId;
  if (!convId || store.currentConvType !== 'literature') {
    convId = await store.startNewConversation('literature', query.value) || undefined;
  } else {
    await store.saveMessage('user', query.value);
  }

  if (!convId) {
    console.error('Failed to create conversation');
    return;
  }

  store.clearWorkflow();
  store.addWorkflowStep('提取文档文本');
  store.addWorkflowStep('文本切分与向量化');
  store.addWorkflowStep('检索相关内容');
  store.addWorkflowStep('Actor 生成摘要');
  store.addWorkflowStep('Critic 审查（防幻觉）');
  store.addWorkflowStep('修正与输出');

  store.isProcessing = true;

  try {
    const myConvId = store.currentConvId;
    const ctrl = store.createStreamController();
    generatedFileInfo.value = null;
    let _reactIter = 1;
    for await (const event of streamPost('/literature/summarize/stream', {
      file_path: filePath,
      query: query.value,
      skip_thinking: skipThinking.value,
      conv_id: convId,
    }, ctrl.signal)) {
      if (store.currentConvId !== myConvId) break;
      if (event.type === 'title_generated') {
        if (event.conv_id && event.title) store.loadConversations();
        continue;
      }
      if (event.type === 'actor_done') {
        if (event.title) store.loadConversations();
        continue;
      }
      if (event.type === 'step') {
        const stepIndex = store.workflowSteps.findIndex((s) => s.status === 'pending');
        if (stepIndex >= 0) {
          for (let i = 0; i < stepIndex; i++) {
            if (store.workflowSteps[i].status !== 'completed') {
              store.updateWorkflowStep(i, 'completed');
            }
          }
          store.updateWorkflowStep(stepIndex, 'active');
        }
      } else if (event.type === 'react_start') {
        _reactIter = (event as any).iteration || 1;
        store.appendThinkingRound('react', _reactIter, '');
      } else if (event.type === 'react_thought') {
        store.appendThinkingRound('react', _reactIter, `🤔 思考: ${(event as any).thought || ''}\n`);
      } else if (event.type === 'tool_call') {
        const args = (event as any).arguments || {};
        const argsStr = Object.entries(args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ');
        store.appendThinkingRound('react', _reactIter, `🔧 调用工具: ${(event as any).name}(${argsStr})\n`);
      } else if (event.type === 'tool_result') {
        const result = ((event as any).result || '').substring(0, 500);
        store.appendThinkingRound('react', _reactIter, `📋 工具结果: ${result}${((event as any).result || '').length > 500 ? '...' : ''}\n`);
      } else if (event.type === 'react_done') {
        if ((event as any).steps > 0) {
          store.appendThinkingRound('react', _reactIter, `✅ ReAct 完成: ${(event as any).steps} 步工具调用\n`);
        }
      } else if (event.type === 'stream' && event.role === 'actor') {
        store.actorText += event.content || '';
        store.appendThinkingRound('actor', event.iteration || 1, event.content || '');
        const actorIdx = store.workflowSteps.findIndex(s => s.name.includes('Actor'));
        if (actorIdx >= 0 && store.workflowSteps[actorIdx].status !== 'active') {
          for (let i = 0; i < actorIdx; i++) store.updateWorkflowStep(i, 'completed');
          store.updateWorkflowStep(actorIdx, 'active');
        }
      } else if (event.type === 'stream' && event.role === 'critic') {
        store.criticText += event.content || '';
        store.appendThinkingRound('critic', event.iteration || 1, event.content || '');
        const criticIdx = store.workflowSteps.findIndex(s => s.name.includes('Critic'));
        if (criticIdx >= 0 && store.workflowSteps[criticIdx].status !== 'active') {
          const actorIdx = store.workflowSteps.findIndex(s => s.name.includes('Actor'));
          if (actorIdx >= 0) store.updateWorkflowStep(actorIdx, 'completed');
          store.updateWorkflowStep(criticIdx, 'active');
        }
      } else if (event.type === 'file_generated' && event.file) {
        const file = event.file;
        const downloadUrl = file.relative_path
          ? `/api/files/download/${String(file.relative_path).replace(/\\/g, '/')}`
          : `/api/literature/download/${file.stored_filename || file.filename}`;
        generatedFileInfo.value = {
          filename: file.filename,
          file_path: file.file_path || '',
          stored_filename: file.stored_filename || '',
          relative_path: file.relative_path || '',
          file_format: file.file_format || 'md',
          download_url: downloadUrl,
        };
      } else if (event.type === 'complete') {
        store.workflowSteps.forEach((_: any, i: number) => {
          store.updateWorkflowStep(i, 'completed');
        });
        const finalText = event.output || store.actorText;
        store.actorText = finalText;
        store.isProcessing = false;
        store.finalOutput = finalText;
        docId.value = event.doc_id || '';

        if (generatedFileInfo.value) {
          store.addGeneratedFile({
            filename: generatedFileInfo.value.filename,
            file_name: generatedFileInfo.value.filename,
            file_path: generatedFileInfo.value.file_path,
            stored_filename: generatedFileInfo.value.stored_filename,
            relative_path: generatedFileInfo.value.relative_path,
            file_format: generatedFileInfo.value.file_format || 'md',
            file_size: generatedFileInfo.value.file_size || 0,
            download_url: generatedFileInfo.value.download_url,
            conv_id: convId || store.currentConvId || '',
          });
        }

        store.saveMessage('actor', finalText).then(() => {
          store.saveMessage('critic', store.criticText);
        }).then(() => {
          if (store.currentRefFiles.length > 0) {
            store.saveFilesMessage(store.currentRefFiles);
          }
        }).then(() => {
          store.loadConversations();
        }).catch((e: any) => console.error('Save failed:', e));
      } else if (event.type === 'error') {
        store.workflowSteps.forEach((_: any, i: number) => {
          store.updateWorkflowStep(i, 'completed');
        });
        store.isProcessing = false;
        store.finalOutput = event.message || '摘要生成过程中发生错误';
        store.saveMessage('actor', store.finalOutput).then(() => {
          store.loadConversations();
        }).catch((e: any) => console.error('Save error failed:', e));
      }
    }
  } catch (e) {
    console.error('Generate summary failed:', e);
    const errMsg = e instanceof Error ? e.message : '摘要生成失败';
    store.finalOutput = errMsg;
    store.saveMessage('actor', errMsg).then(() => {
      store.loadConversations();
    }).catch(() => {});
  } finally {
    store.isProcessing = false;
    query.value = '请生成这篇文献的详细摘要';
    uploadedFiles.value = [];
  }
}

async function askFollowUp() {
  if (!docId.value || !followUpQuestion.value) return;
  try {
    const res = await apiClient.askAboutDocument(docId.value, followUpQuestion.value);
    store.actorText = res.data.answer || '无法回答该问题';
  } catch (e) {
    store.actorText = '提问失败，请重试';
  }
}

watch(() => store.droppedFileInfo, (info) => {
  if (info) {
    uploadedFiles.value.push({
      filename: info.filename,
      file_path: info.file_path,
      stored_filename: info.stored_filename || info.file_path.split(/[/\\]/).pop() || info.filename,
      relative_path: info.relative_path,
    });
    store.droppedFileInfo = null;
  }
});
</script>
