<template>
  <div class="relative space-y-3">
    <div v-if="uploadedFiles.length > 0" class="flex items-center space-x-2 overflow-x-auto pb-1 mb-2">
      <div
        v-for="(f, idx) in uploadedFiles"
        :key="idx"
        class="flex-shrink-0 flex items-center space-x-1.5 bg-green-50 border border-green-300 rounded-md px-2.5 py-1.5 text-xs"
      >
        <span class="text-green-700">{{ fileIcon(f.filename) }} {{ f.filename }}</span>
        <button @click="removeFile(idx)" class="text-red-400 hover:text-red-600">✕</button>
      </div>
    </div>
    <div v-if="isUploading || (uploadProgress > 0 && uploadProgress < 100)" class="space-y-1 mb-2">
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

    <textarea
      v-model="inputText"
      class="w-full border rounded-lg px-4 py-3 text-sm min-h-[120px] max-h-[300px] focus:ring-2 focus:ring-primary-300 resize-y"
      :placeholder="uploadedFiles.length > 0 ? '文件已添加，可在此补充说明...（Shift+Enter换行）' : '输入需要润色的文本，或拖拽文件到页面任意位置...（Shift+Enter换行）'"
      @keydown.enter.exact.prevent="inputText && startPolish()"
    ></textarea>
    <p class="text-[10px] text-gray-400 -mt-1">💡 选择非文件使用的语言可以自动翻译，上传文件后可补充说明</p>

    <div class="flex items-center space-x-4 mb-2">
      <label class="flex items-center space-x-1.5 cursor-pointer">
        <input type="checkbox" v-model="skipThinking" class="w-3.5 h-3.5 rounded border-gray-300 text-primary-500 focus:ring-primary-300" />
        <span class="text-[10px] text-gray-500">⚡ 跳过思考过程，直接输出</span>
      </label>
    </div>

    <div class="flex items-center space-x-2 flex-wrap gap-y-1">
      <select v-model="targetLanguage" class="border rounded px-2 py-1.5 text-xs">
        <option value="auto">🔍 自动识别</option>
              <option value="en">🇬🇧 英文</option>
              <option value="zh">🇨🇳 中文</option>
              <option value="ja">🇯🇵 日文</option>
              <option value="ko">🇰🇷 韩文</option>
              <option value="fr">🇫🇷 法文</option>
              <option value="de">🇩🇪 德文</option>
              <option value="es">🇪🇸 西班牙文</option>
              <option value="ru">🇷🇺 俄文</option>
              <option value="pt">🇵🇹 葡萄牙文</option>
              <option value="it">🇮🇹 意大利文</option>
              <option value="ar">🇸🇦 阿拉伯文</option>
      </select>
      <select v-model="style" class="border rounded px-2 py-1.5 text-xs">
        <option value="academic">学术写作</option>
        <option value="business">商业计划书</option>
        <option value="formal">正式公文</option>
        <option value="email_professor">教授邮件</option>
        <option value="casual">日常交流</option>
      </select>
      <button
        @click="startPolish"
        :disabled="store.isProcessing || (!inputText && uploadedFiles.length === 0)"
        class="px-4 py-1.5 bg-primary-500 text-white rounded text-xs font-medium disabled:opacity-50"
      >
        {{ store.isProcessing ? '润色中...' : '开始润色' }}
      </button>
      <label v-if="uploadedFiles.length > 0" class="flex items-center space-x-1 text-xs text-gray-500">
        <input type="checkbox" v-model="inplace" class="rounded" />
        <span>原地生成（同目录）</span>
      </label>
    </div>

    <div v-if="langMismatch" class="bg-yellow-50 border border-yellow-300 rounded p-3 text-sm space-y-2">
      <p class="text-yellow-700">⚠️ {{ langMismatch.message }}</p>
      <div class="flex space-x-2">
        <button
          @click="confirmLangMismatch(true)"
          class="px-3 py-1 bg-yellow-500 text-white rounded text-xs"
        >
          确认，翻译为{{ langMismatch.target_language_name }}
        </button>
        <button
          @click="confirmLangMismatch(false)"
          class="px-3 py-1 bg-gray-200 text-gray-700 rounded text-xs"
        >
          使用原文语言（{{ langMismatch.source_language_name }}）
        </button>
      </div>
    </div>

    <div v-if="generatedFile" class="bg-green-50 border border-green-300 rounded p-3 text-sm flex items-center justify-between">
      <span class="text-green-700">📄 润色文件已生成：{{ generatedFile.filename }}</span>
      <a
        :href="generatedFile.download_url"
        class="px-3 py-1 bg-green-500 text-white rounded text-xs hover:bg-green-600"
        download
      >
        下载
      </a>
    </div>

    
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useAppStore } from '../stores/app';
import { streamPost, apiClient, validateUploadFile } from '../utils/api';

const store = useAppStore();
const inputText = ref('');
const targetLanguage = ref('auto');
const style = ref('academic');
const inplace = ref(false);
const generatedFile = ref<any>(null);
const langMismatch = ref<any>(null);
const uploadProgress = ref(0);
const isUploading = ref(false);
const skipThinking = ref(false);

const langNameMap: Record<string, string> = {
  auto: '自动识别', en: '英文', zh: '中文', ja: '日文', ko: '韩文',
  fr: '法文', de: '德文', es: '西班牙文', ru: '俄文', pt: '葡萄牙文', it: '意大利文', ar: '阿拉伯文',
};

const styleNameMap: Record<string, string> = {
  academic: '学术写作', business: '商业计划书', formal: '正式公文', email_professor: '教授邮件', casual: '日常交流',
};

interface UploadedFileInfo {
  filename: string;
  file_path: string;
  stored_filename?: string;
  relative_path?: string;
  detected_language?: string;
  detected_language_name?: string;
}
const uploadedFiles = ref<UploadedFileInfo[]>([]);

function fileIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase();
  const icons: Record<string, string> = {
    pdf: '📄', md: '📝', docx: '📃', doc: '📃',
    xlsx: '📊', xls: '📊', pptx: '📊', ppt: '📊',
    txt: '📄', py: '🐍', js: '📜', ts: '📜',
    java: '☕', c: '⚙️', cpp: '⚙️', go: '🔵', rs: '🦀'
  };
  return icons[ext || ''] || '📄';
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
    const res = await apiClient.uploadPolishFile(file, 'polish', convId, (progress) => {
      uploadProgress.value = Math.round(progress);
    });
    uploadedFiles.value.push({
      filename: res.data.filename,
      file_path: res.data.file_path,
      stored_filename: res.data.stored_filename || res.data.file_path.split(/[/\\]/).pop() || res.data.filename,
      relative_path: res.data.relative_path,
      detected_language: res.data.detected_language?.lang || 'auto',
      detected_language_name: res.data.detected_language?.name || '自动识别',
    });
    inputText.value = '';
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

async function startPolish() {
  langMismatch.value = null;
  generatedFile.value = null;

  const isFile = uploadedFiles.value.length > 0;
  const textToDetect = isFile ? '' : inputText.value;
  if (!textToDetect && !isFile) return;

  try {
    let detectedLang = 'auto';
    let detectedLangName = '自动识别';

    if (textToDetect) {
      const res = await apiClient.detectPolishLanguage(textToDetect);
      detectedLang = res.data.lang || 'auto';
      detectedLangName = res.data.name || langNameMap[detectedLang] || detectedLang;
    } else if (isFile && uploadedFiles.value[0]?.detected_language) {
      detectedLang = uploadedFiles.value[0].detected_language || 'auto';
      detectedLangName = uploadedFiles.value[0].detected_language_name || langNameMap[detectedLang] || detectedLang;
    }

    const resolvedTarget = targetLanguage.value === 'auto' ? detectedLang : targetLanguage.value;
    const resolvedTargetName = langNameMap[resolvedTarget] || resolvedTarget;
    const isTranslation = detectedLang !== 'auto' && resolvedTarget !== 'auto' && detectedLang !== resolvedTarget;

    if (isFile) {
      await polishFromFile();
    } else {
      await polishFromText();
    }
  } catch (e) {
    console.error('Language detection failed, proceeding directly:', e);
    if (isFile) {
      await polishFromFile();
    } else {
      await polishFromText();
    }
  }
}

async function polishFromText() {
  if (!inputText.value) return;

  if (store.offlineMode) {
    await store.loadOfflineDemo('multilingual_polish');
    return;
  }

  const userMsg = inputText.value + (uploadedFiles.value.length > 0 ? ` [附带${uploadedFiles.value.length}个文件]` : '');
  store.lastUserMessage = userMsg;
  store.currentRefFiles = uploadedFiles.value.map(f => ({ filename: f.filename, file_path: f.file_path, stored_filename: f.stored_filename, relative_path: f.relative_path, download_url: f.relative_path ? `/api/files/download/${f.relative_path}` : undefined }));

  if (!store.currentConvId || store.currentConvType !== 'polish') {
    await store.startNewConversation('polish', userMsg);
  } else {
    await store.saveMessage('user', userMsg);
  }
  store.lastUserMessage = userMsg;

  const myConvId = store.currentConvId;

  store.isProcessing = true;
  store.clearWorkflow();
  store.addWorkflowStep('文本分析');
  store.addWorkflowStep('Actor 润色');
  store.addWorkflowStep('Critic 审查（语体校验）');
  store.addWorkflowStep('修正与输出');

  try {
    store.updateWorkflowStep(0, 'active');
    const ctrl = store.createStreamController();

    for await (const event of streamPost('/polish/stream', {
      text: inputText.value,
      target_language: targetLanguage.value,
      style: style.value,
      ref_files: uploadedFiles.value.map(f => ({
        filename: f.filename, file_path: f.file_path,
        stored_filename: f.stored_filename, relative_path: f.relative_path,
      })),
      conv_id: myConvId || undefined,
      skip_thinking: skipThinking.value,
      detect_source_lang: true,
    }, ctrl.signal)) {
      if (store.currentConvId !== myConvId) break;
      if (event.type === 'lang_mismatch') {
        langMismatch.value = event;
        store.isProcessing = false;
        return;
      }
      await handleStreamEvent(event);
    }
  } catch (e) {
    console.error('Polish failed:', e);
  } finally {
    store.isProcessing = false;
    if (!langMismatch.value) {
      inputText.value = '';
      uploadedFiles.value = [];
    }
  }
}

async function polishFromFile() {
  const filePath = getPrimaryFilePath();
  if (!filePath) return;

  if (store.offlineMode) {
    await store.loadOfflineDemo('multilingual_polish');
    return;
  }

  const fileNames = uploadedFiles.value.map(f => f.filename).join(', ');
  const userMsg = inputText.value
    ? `润色文件: ${fileNames}\n${inputText.value}`
    : `润色文件: ${fileNames}`;
  store.lastUserMessage = userMsg;
  store.currentRefFiles = uploadedFiles.value.map(f => ({ filename: f.filename, file_path: f.file_path, stored_filename: f.stored_filename, relative_path: f.relative_path, download_url: f.relative_path ? `/api/files/download/${f.relative_path}` : undefined }));

  if (!store.currentConvId || store.currentConvType !== 'polish') {
    await store.startNewConversation('polish', userMsg);
  } else {
    await store.saveMessage('user', userMsg);
  }
  store.lastUserMessage = userMsg;

  store.isProcessing = true;
  store.clearWorkflow();
  store.addWorkflowStep('读取文件');
  store.addWorkflowStep('Actor 润色');
  store.addWorkflowStep('Critic 审查（语体校验）');
  store.addWorkflowStep('修正与输出');

  try {
    store.updateWorkflowStep(0, 'active');
    const ctrl = store.createStreamController();

    const convId = store.currentConvId || undefined;
    for await (const event of streamPost('/polish/file/stream', {
      file_path: filePath,
      target_language: targetLanguage.value,
      style: style.value,
      user_instruction: inputText.value || '',
      inplace: inplace.value,
      confirm_lang: false,
      skip_thinking: skipThinking.value,
      conv_id: convId,
    }, ctrl.signal)) {
      if (event.type === 'lang_mismatch') {
        langMismatch.value = event;
        store.isProcessing = false;
        return;
      }
      if (event.type === 'file_generated' && event.file) {
        const file = event.file;
        const downloadUrl = file.relative_path
          ? `/api/files/download/${file.relative_path}`
          : (file.file_path
            ? `/api/polish/download/${file.filename}?file_path=${encodeURIComponent(file.file_path)}&mode=polish&conv_id=${convId || ''}`
            : `/api/polish/download/${file.filename}?mode=polish&conv_id=${convId || ''}`);
        generatedFile.value = { ...file, download_url: downloadUrl };
      }
      await handleStreamEvent(event);
    }
  } catch (e) {
    console.error('Polish file failed:', e);
  } finally {
    store.isProcessing = false;
    if (!langMismatch.value) {
      inputText.value = '';
      uploadedFiles.value = [];
    }
  }
}

async function confirmLangMismatch(useTarget: boolean) {
  if (!langMismatch.value) return;

  const resolvedLang = useTarget ? langMismatch.value.target_language : langMismatch.value.source_language;
  langMismatch.value = null;

  store.isProcessing = true;

  try {
    const filePath = getPrimaryFilePath();
    const convId = store.currentConvId || undefined;
    if (filePath) {
      const ctrl = store.createStreamController();
      for await (const event of streamPost('/polish/file/stream', {
        file_path: filePath,
        target_language: resolvedLang,
        style: style.value,
        user_instruction: '',
        inplace: inplace.value,
        confirm_lang: true,
        skip_thinking: skipThinking.value,
        conv_id: convId,
      }, ctrl.signal)) {
        if (event.type === 'file_generated' && event.file) {
          const file = event.file;
          const downloadUrl = file.relative_path
            ? `/api/files/download/${file.relative_path}`
            : (file.file_path
              ? `/api/polish/download/${file.filename}?file_path=${encodeURIComponent(file.file_path)}&mode=polish&conv_id=${convId || ''}`
              : `/api/polish/download/${file.filename}?mode=polish&conv_id=${convId || ''}`);
          generatedFile.value = { ...file, download_url: downloadUrl };
        }
        await handleStreamEvent(event);
      }
    } else {
      const ctrl = store.createStreamController();
      for await (const event of streamPost('/polish/stream', {
        text: inputText.value,
        target_language: resolvedLang,
        style: style.value,
        confirm_lang: true,
        skip_thinking: skipThinking.value,
        conv_id: convId,
      }, ctrl.signal)) {
        await handleStreamEvent(event);
      }
    }
  } catch (e) {
    console.error('Polish failed:', e);
  } finally {
    store.isProcessing = false;
    inputText.value = '';
    uploadedFiles.value = [];
  }
}

let _reactIter = 1;

async function handleStreamEvent(event: any) {
  if (event.type === 'title_generated') {
    if (event.conv_id && event.title) store.loadConversations();
    return;
  }
  if (event.type === 'actor_done') {
    if (event.title) store.loadConversations();
    return;
  }
  if (event.type === 'step' && event.message) {
    const stepIndex = store.workflowSteps.findIndex((s: any) => s.status === 'pending');
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
    store.updateWorkflowStep(0, 'completed');
    store.updateWorkflowStep(1, 'active');
  } else if (event.type === 'stream' && event.role === 'critic') {
    store.criticText += event.content || '';
    store.appendThinkingRound('critic', event.iteration || 1, event.content || '');
    store.updateWorkflowStep(1, 'completed');
    store.updateWorkflowStep(2, 'active');
  } else if (event.type === 'error') {
    store.workflowSteps.forEach((_: any, i: number) => {
      store.updateWorkflowStep(i, 'completed');
    });
    store.isProcessing = false;
    store.finalOutput = event.message || '处理过程中发生错误';
    store.saveMessage('actor', store.finalOutput).then(() => {
      store.loadConversations();
    }).catch((e: any) => console.error('Save failed:', e));
  } else if (event.type === 'complete') {
    if (event.file && !generatedFile.value) {
      const file = event.file;
      generatedFile.value = {
        ...file,
        download_url: file.relative_path
          ? `/api/files/download/${file.relative_path}`
          : (file.file_path
            ? `/api/polish/download/${file.filename}?file_path=${encodeURIComponent(file.file_path)}&mode=polish&conv_id=${store.currentConvId || ''}`
            : `/api/polish/download/${file.filename}?mode=polish&conv_id=${store.currentConvId || ''}`),
      };
    }
    store.workflowSteps.forEach((_: any, i: number) => {
      store.updateWorkflowStep(i, 'completed');
    });
    store.isProcessing = false;
    store.finalOutput = event.output || store.actorText;
    store.saveMessage('actor', store.finalOutput).then(() => {
      store.saveMessage('critic', store.criticText);
    }).then(() => {
      if (generatedFile.value) {
        const fileInfo = {
          filename: generatedFile.value.filename,
          file_path: generatedFile.value.file_path || '',
          stored_filename: generatedFile.value.stored_filename || (generatedFile.value.file_path ? generatedFile.value.file_path.split(/[/\\]/).pop() || '' : ''),
          download_url: generatedFile.value.download_url || '',
          relative_path: generatedFile.value.relative_path || '',
        };
        store.addGeneratedFile({
          filename: fileInfo.filename,
          file_name: fileInfo.filename,
          file_path: fileInfo.file_path,
          stored_filename: fileInfo.stored_filename,
          relative_path: fileInfo.relative_path,
          file_format: generatedFile.value.file_format || 'txt',
          file_size: generatedFile.value.file_size || 0,
          download_url: fileInfo.download_url,
          conv_id: store.currentConvId || '',
        });
      }
      if (store.currentRefFiles.length > 0) {
        store.saveFilesMessage(store.currentRefFiles);
      }
    }).then(() => {
      store.loadConversations();
    }).catch((e: any) => console.error('Save failed:', e));
  }
}

watch(() => store.droppedFileInfo, (info) => {
  if (info) {
    uploadedFiles.value.push({
      filename: info.filename,
      file_path: info.file_path,
      stored_filename: info.file_path.split(/[/\\]/).pop() || info.filename,
    });
    store.droppedFileInfo = null;
  }
});
</script>
