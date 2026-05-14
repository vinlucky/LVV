<template>
  <div class="relative space-y-3">
    <div class="flex space-x-2">
      <input
        v-model="topic"
        class="flex-1 border rounded px-3 py-1.5 text-sm focus:ring-2 focus:ring-primary-300"
        placeholder="PPT 主题（可选，有内容或文件时可不填）"
        @keydown.enter.exact.prevent="topic && generatePPT()"
      />
    </div>
    <div class="flex items-center space-x-2">
      <div class="flex items-center space-x-1">
        <span class="text-[10px] text-gray-400">风格：</span>
        <select v-model="style" class="border rounded px-2 py-1.5 text-xs">
          <option value="academic">学术</option>
          <option value="business">商务</option>
          <option value="creative">创意</option>
        </select>
      </div>
    </div>

    <div class="flex items-center space-x-4">
      <label class="flex items-center space-x-1.5 cursor-pointer">
        <input type="checkbox" v-model="skipThinking" class="w-3.5 h-3.5 rounded border-gray-300 text-primary-500 focus:ring-primary-300" />
        <span class="text-[10px] text-gray-500">⚡ 跳过思考过程，直接输出</span>
      </label>
    </div>

    <div v-if="uploadedRefFiles.length > 0" class="flex items-center space-x-2 overflow-x-auto pb-1">
      <div
        v-for="(f, idx) in uploadedRefFiles"
        :key="idx"
        class="flex-shrink-0 flex items-center space-x-1.5 bg-green-50 border border-green-300 rounded-md px-2.5 py-1.5 text-xs"
      >
        <span class="text-green-700">{{ fileIcon(f.filename) }} {{ f.filename }}</span>
        <a
          v-if="f.relative_path"
          :href="`/api/files/download/${f.relative_path}`"
          :download="f.filename"
          class="text-[10px] text-primary-500 hover:text-primary-600"
        >📥</a>
        <button @click="removeRefFile(idx)" class="text-red-400 hover:text-red-600">✕</button>
      </div>
    </div>
    <div v-if="isUploading || (refUploadProgress > 0 && refUploadProgress < 100)" class="space-y-1">
      <div class="flex items-center space-x-2">
        <svg class="animate-spin h-3 w-3 text-primary-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span class="text-[10px] text-primary-500 font-medium">上传中 {{ refUploadProgress > 0 ? refUploadProgress + '%' : '...' }}</span>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-1.5">
        <div class="bg-primary-500 h-1.5 rounded-full transition-all duration-300" :style="{ width: (refUploadProgress > 0 ? refUploadProgress : 5) + '%' }"></div>
      </div>
    </div>

    <div class="flex space-x-2">
      <textarea
        v-model="content"
        class="flex-1 border rounded px-3 py-2 text-sm min-h-[40px] max-h-[200px] focus:ring-2 focus:ring-primary-300 resize-y"
        placeholder="参考内容（可选）..."
      ></textarea>
      <div class="flex flex-col space-y-1">
        <input ref="refFileInput" type="file" accept=".md,.pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.txt,.py,.js,.ts,.java,.c,.cpp,.go,.rs" class="hidden" multiple @change="handleRefFileSelect" />
        <button
          @click="($refs.refFileInput as any)?.click()"
          class="px-3 py-1.5 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
        >
          📁 上传参考
        </button>
        <button
          @click="generatePPT"
          :disabled="store.isProcessing || (!topic && !content && uploadedRefFiles.length === 0)"
          class="px-4 py-1.5 bg-primary-500 text-white rounded text-xs font-medium disabled:opacity-50"
        >
          {{ store.isProcessing ? '生成中...' : '生成大纲' }}
        </button>
      </div>
    </div>

    <div v-if="errorMessage" class="bg-red-50 border border-red-200 rounded-lg p-3">
      <div class="flex items-start">
        <span class="text-sm font-medium text-red-700">❌ {{ errorMessage }}</span>
      </div>
      <button @click="errorMessage = ''" class="mt-2 px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200">关闭</button>
    </div>

    <div v-if="generatedMarkdown" class="border rounded-lg overflow-hidden">
      <div
        class="flex items-center justify-between bg-blue-50 border-b border-blue-200 px-3 py-2 cursor-pointer hover:bg-blue-100"
        @click="resultExpanded = !resultExpanded"
      >
        <span class="text-xs font-medium text-blue-700">✅ PPT已生成</span>
        <div class="flex items-center space-x-2" @click.stop>
          <button
            v-if="generatedFileInfo"
            @click="downloadPptx"
            class="px-2 py-0.5 bg-purple-500 text-white rounded text-[10px] font-medium hover:bg-purple-600"
          >
            📥 PPT
          </button>
          <button
            @click="downloadMarkdown"
            class="px-2 py-0.5 bg-green-500 text-white rounded text-[10px] font-medium hover:bg-green-600"
          >
            💾 大纲
          </button>
          <button
            @click="copyMarkdown"
            class="px-2 py-0.5 bg-blue-500 text-white rounded text-[10px] font-medium hover:bg-blue-600"
          >
            📋 复制
          </button>
          <button
            @click="resetResult"
            class="px-2 py-0.5 bg-orange-500 text-white rounded text-[10px] font-medium hover:bg-orange-600"
          >
            🔄 重新生成
          </button>
          <span class="text-blue-400 text-xs">{{ resultExpanded ? '▼' : '▶' }}</span>
        </div>
      </div>
      <div v-if="resultExpanded" class="bg-white p-3">
        <div v-if="generatedFileInfo" class="bg-purple-50 border border-purple-200 rounded p-2 mb-2 text-xs text-purple-700">
          🎉 PPT文件已自动生成，点击上方"📥 PPT"按钮获取
        </div>
        <div class="bg-gray-50 rounded border p-2 max-h-48 overflow-y-auto text-xs whitespace-pre-wrap">{{ generatedMarkdown }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useAppStore } from '../stores/app';
import { streamPost, apiClient, validateUploadFile } from '../utils/api';

const store = useAppStore();
const topic = ref('');
const content = ref('');
const style = ref('academic');
const errorMessage = ref('');
const refUploadProgress = ref(0);
const isUploading = ref(false);
const skipThinking = ref(false);
const generatedMarkdown = ref('');
const generatedFileInfo = ref<any>(null);
const outlineFileInfo = ref<any>(null);
const resultExpanded = ref(false);

interface RefFileInfo {
  filename: string;
  file_path: string;
  stored_filename?: string;
  relative_path?: string;
}
const uploadedRefFiles = ref<RefFileInfo[]>([]);

onMounted(() => {
  restoreFromStore();
});

watch(() => store.currentConvId, () => {
  generatedMarkdown.value = '';
  generatedFileInfo.value = null;
  outlineFileInfo.value = null;
  resultExpanded.value = false;
  restoreFromStore();
});

watch(() => store.conversationRounds.length, () => {
  if (store.currentConvType === 'ppt') {
    restoreFromStore();
  }
});

function restoreFromStore() {
  generatedMarkdown.value = '';
  generatedFileInfo.value = null;
  outlineFileInfo.value = null;
  resultExpanded.value = false;

  if (store.currentConvType !== 'ppt' || store.conversationRounds.length === 0) {
    return;
  }
  const lastRound = store.conversationRounds[store.conversationRounds.length - 1];
    if (lastRound?.actorText) {
      generatedMarkdown.value = lastRound.actorText;
      resultExpanded.value = false;
    }
    if (lastRound?.generatedFiles && lastRound.generatedFiles.length > 0) {
      const pptxFile = lastRound.generatedFiles.find((f: any) => f.file_format === 'pptx' || (f.filename && f.filename.endsWith('.pptx')));
      if (pptxFile) {
        generatedFileInfo.value = {
          filename: pptxFile.filename,
          file_path: pptxFile.file_path || '',
          stored_filename: pptxFile.stored_filename || '',
          relative_path: pptxFile.relative_path || '',
          file_format: pptxFile.file_format || 'pptx',
          file_size: pptxFile.file_size || 0,
          download_url: pptxFile.download_url || (pptxFile.relative_path ? `/api/files/download/${pptxFile.relative_path}` : ''),
        };
      }
      const mdFile = lastRound.generatedFiles.find((f: any) => f.file_format === 'md' || (f.filename && f.filename.endsWith('.md')));
      if (mdFile) {
        outlineFileInfo.value = {
          filename: mdFile.filename,
          file_path: mdFile.file_path || '',
          stored_filename: mdFile.stored_filename || '',
          relative_path: mdFile.relative_path || '',
          file_format: mdFile.file_format || 'md',
          file_size: mdFile.file_size || 0,
          download_url: mdFile.download_url || (mdFile.relative_path ? `/api/files/download/${mdFile.relative_path}` : ''),
        };
      }
    }
}

function fileIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase();
  const icons: Record<string, string> = { pdf: '📄', md: '📝', docx: '📃', doc: '📃', xlsx: '📊', xls: '📊', pptx: '📊', ppt: '📊', txt: '📄', py: '🐍', js: '📜', ts: '📜', java: '☕', c: '⚙️', cpp: '⚙️', go: '🔵', rs: '🦀' };
  return icons[ext || ''] || '📄';
}

async function handleRefFileSelect(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files;
  if (files) {
    for (let i = 0; i < files.length; i++) {
      await uploadRefFile(files[i]);
    }
  }
  input.value = '';
}

function removeRefFile(idx: number) {
  uploadedRefFiles.value.splice(idx, 1);
}

async function uploadRefFile(file: File) {
  const validationError = validateUploadFile(file);
  if (validationError) {
    alert(validationError);
    return;
  }

  isUploading.value = true;
  refUploadProgress.value = 5;
  try {
    const convId = store.currentConvId || undefined;
    const res = await apiClient.uploadFile(file, 'ppt', convId, undefined, (progress) => {
      refUploadProgress.value = Math.round(progress);
    });
    uploadedRefFiles.value.push({
      filename: res.data.filename,
      file_path: res.data.file_path,
      stored_filename: res.data.stored_filename || res.data.file_path.split(/[/\\]/).pop() || res.data.filename,
      relative_path: res.data.relative_path,
    });
    refUploadProgress.value = 100;
    setTimeout(() => { refUploadProgress.value = 0; isUploading.value = false; }, 1000);
  } catch (e) {
    console.error('Upload ref file failed:', e);
    refUploadProgress.value = 0;
    isUploading.value = false;
  }
}

function copyMarkdown() {
  if (!generatedMarkdown.value) return;
  navigator.clipboard.writeText(generatedMarkdown.value).then(() => {
    alert('大纲已复制到剪贴板');
  }).catch(() => {
    const textarea = document.createElement('textarea');
    textarea.value = generatedMarkdown.value;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    alert('大纲已复制到剪贴板');
  });
}

function downloadPptx() {
  if (!generatedFileInfo.value) return;
  const file = generatedFileInfo.value;
  const url = file.download_url || (file.relative_path
    ? `/api/files/download/${file.relative_path}`
    : `/api/ppt/download/${file.stored_filename || file.filename}`);
  const a = document.createElement('a');
  a.href = url;
  a.download = file.filename || 'presentation.pptx';
  a.click();
}

async function downloadMarkdown() {
  if (outlineFileInfo.value) {
    const file = outlineFileInfo.value;
    const url = file.download_url || (file.relative_path
      ? `/api/files/download/${file.relative_path}`
      : `/api/chat/download/${file.stored_filename || file.filename}?mode=ppt&conv_id=${store.currentConvId || ''}`);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.filename || 'PPT大纲.md';
    a.click();
    return;
  }
  if (!generatedMarkdown.value) return;
  const convId = store.currentConvId || undefined;
  try {
    const res = await apiClient.generateFile(generatedMarkdown.value, 'md', topic.value || 'PPT大纲', convId, 'ppt');
    const file = res.data;
    const url = file.relative_path
      ? `/api/files/download/${file.relative_path}`
      : `/api/chat/download/${file.stored_filename || file.filename}?mode=ppt&conv_id=${convId || ''}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = file.filename || 'PPT大纲.md';
    a.click();
  } catch (e) {
    console.error('Download markdown failed:', e);
  }
}

function resetResult() {
  generatedMarkdown.value = '';
  generatedFileInfo.value = null;
  outlineFileInfo.value = null;
  resultExpanded.value = false;
}

async function generatePPT() {
  if (!topic.value && !content.value && uploadedRefFiles.value.length === 0) return;

  if (store.actorText || store.criticText || store.finalOutput) {
    store.commitStreamState();
  }

  if (store.offlineMode) {
    await store.loadOfflineDemo('ppt_generation');
    return;
  }

  errorMessage.value = '';
  generatedMarkdown.value = '';
  generatedFileInfo.value = null;
  outlineFileInfo.value = null;

  const refFileContext = uploadedRefFiles.value.length > 0
    ? '\n\n[参考文件]\n' + uploadedRefFiles.value.map(f => `文件: ${f.filename} (路径: ${f.file_path})`).join('\n')
    : '';

  const topicPart = topic.value ? `PPT主题: ${topic.value}` : '';
  const contentPart = content.value ? `\nPPT内容要点: ${content.value}` : '';
  const refPart = uploadedRefFiles.value.length > 0 ? ` [附带${uploadedRefFiles.value.length}个参考文件]` : '';
  const userMsg = topicPart + contentPart + refPart || '请根据参考文件生成PPT大纲';
  store.lastUserMessage = userMsg;
  store.currentRefFiles = uploadedRefFiles.value.map(f => ({ filename: f.filename, file_path: f.file_path, stored_filename: f.stored_filename, relative_path: f.relative_path, download_url: f.relative_path ? `/api/files/download/${f.relative_path}` : undefined }));

  if (!store.currentConvId || store.currentConvType !== 'ppt') {
    await store.startNewConversation('ppt', userMsg);
  } else {
    await store.saveMessage('user', userMsg);
  }
  store.lastUserMessage = userMsg;

  store.isProcessing = true;
  store.clearWorkflow();
  store.addWorkflowStep('生成PPT大纲');
  store.addWorkflowStep('Actor 创建内容');
  store.addWorkflowStep('Critic 审查');
  store.addWorkflowStep('输出Markdown大纲');

  try {
    store.updateWorkflowStep(0, 'active');
    const pptConvId = store.currentConvId;
    const ctrl = store.createStreamController();
    const convId = store.currentConvId || undefined;
    let _reactIter = 1;

    for await (const event of streamPost('/ppt/generate/stream', {
      topic: topic.value,
      content: content.value,
      style: style.value,
      template: 'default',
      skip_thinking: skipThinking.value,
      conv_id: convId,
      ref_files: uploadedRefFiles.value.map(f => ({ filename: f.filename, file_path: f.file_path })),
    }, ctrl.signal)) {
      if (store.currentConvId !== pptConvId) break;
      if (event.type === 'title_generated') {
        if (event.conv_id && event.title) store.loadConversations();
        continue;
      }
      if (event.type === 'actor_done') {
        if (event.title) store.loadConversations();
        continue;
      }
      if (event.type === 'react_start') {
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
        store.updateWorkflowStep(0, 'completed');
        store.updateWorkflowStep(1, 'active');
      } else if (event.type === 'stream' && event.role === 'critic') {
        store.criticText += event.content || '';
        store.appendThinkingRound('critic', event.iteration || 1, event.content || '');
        store.updateWorkflowStep(1, 'completed');
        store.updateWorkflowStep(2, 'active');
      } else if (event.type === 'file_generated' && event.file) {
        const file = event.file;
        const downloadUrl = file.relative_path
          ? `/api/files/download/${file.relative_path}`
          : `/api/ppt/download/${file.stored_filename || file.filename}`;
        const fileInfo = {
          filename: file.filename,
          file_path: file.file_path || '',
          stored_filename: file.stored_filename || '',
          relative_path: file.relative_path || '',
          file_format: file.file_format || 'md',
          file_size: file.file_size || 0,
          download_url: downloadUrl,
        };
        if (file.file_format === 'pptx') {
          generatedFileInfo.value = fileInfo;
        } else {
          outlineFileInfo.value = fileInfo;
        }
      } else if (event.type === 'complete') {
        store.updateWorkflowStep(2, 'completed');
        store.updateWorkflowStep(3, 'completed');
        store.isProcessing = false;
        store.finalOutput = event.output || store.actorText;
        generatedMarkdown.value = store.finalOutput;

        if (generatedFileInfo.value) {
          store.addGeneratedFile({
            filename: generatedFileInfo.value.filename,
            file_name: generatedFileInfo.value.filename,
            file_path: generatedFileInfo.value.file_path,
            stored_filename: generatedFileInfo.value.stored_filename,
            relative_path: generatedFileInfo.value.relative_path,
            file_format: generatedFileInfo.value.file_format || 'pptx',
            file_size: generatedFileInfo.value.file_size || 0,
            download_url: generatedFileInfo.value.download_url,
            conv_id: convId || store.currentConvId || '',
          }, false);
        }
        if (outlineFileInfo.value) {
          store.addGeneratedFile({
            filename: outlineFileInfo.value.filename,
            file_name: outlineFileInfo.value.filename,
            file_path: outlineFileInfo.value.file_path,
            stored_filename: outlineFileInfo.value.stored_filename,
            relative_path: outlineFileInfo.value.relative_path,
            file_format: outlineFileInfo.value.file_format || 'md',
            file_size: outlineFileInfo.value.file_size || 0,
            download_url: outlineFileInfo.value.download_url,
            conv_id: convId || store.currentConvId || '',
          }, false);
        }

        try {
          await store.saveMessage('actor', store.finalOutput);
          await store.saveMessage('critic', store.criticText);
          if (store.currentRefFiles.length > 0) {
            await store.saveFilesMessage(store.currentRefFiles);
          }
          await store.loadConversations();
        } catch (e: any) {
          console.error('Save failed:', e);
        }
      } else if (event.type === 'error') {
        const errMsg = event.message || 'PPT大纲生成过程中发生错误';
        errorMessage.value = errMsg;
        store.finalOutput = errMsg;
        store.saveMessage('actor', errMsg).then(() => {
          store.loadConversations();
        }).catch((e: any) => console.error('Save error failed:', e));
      }
    }

    if (!generatedMarkdown.value && !errorMessage.value) {
      errorMessage.value = 'PPT大纲生成失败，未获取到有效数据';
    }
  } catch (e: any) {
    console.error('PPT generation failed:', e);
    errorMessage.value = 'PPT大纲生成失败';
    const errMsg = e?.message || 'PPT大纲生成失败';
    store.finalOutput = errMsg;
    store.saveMessage('actor', errMsg).then(() => {
      store.loadConversations();
    }).catch(() => {});
  } finally {
    store.isProcessing = false;
    topic.value = '';
    content.value = '';
    uploadedRefFiles.value = [];
    store.loadConversations().catch(() => {});
  }
}

watch(() => store.droppedFileInfo, (info) => {
  if (info) {
    uploadedRefFiles.value.push({
      filename: info.filename,
      file_path: info.file_path,
      stored_filename: info.file_path.split(/[/\\]/).pop() || info.filename,
      relative_path: info.relative_path,
    });
    store.droppedFileInfo = null;
  }
});
</script>
