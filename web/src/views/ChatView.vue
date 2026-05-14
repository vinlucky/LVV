<template>
  <div class="relative space-y-3">
    <div class="flex space-x-2">
      <textarea
        v-model="userInput"
        class="flex-1 border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-300 resize-y min-h-[40px] max-h-[200px]"
        rows="1"
        placeholder="输入任何问题，或选择下方模板生成文件...（Shift+Enter换行）"
        @keydown.enter.exact.prevent="sendMessage"
      ></textarea>
      <button
        @click="sendMessage"
        :disabled="store.isProcessing || !userInput.trim()"
        class="px-4 py-2 bg-primary-500 text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-primary-600"
      >
        {{ store.isProcessing ? '思考中...' : '发送' }}
      </button>
    </div>

    <div v-if="uploadedRefFiles.length > 0" class="flex items-center space-x-2 overflow-x-auto pb-1">
      <div
        v-for="(f, idx) in uploadedRefFiles"
        :key="idx"
        class="flex-shrink-0 flex items-center space-x-1.5 bg-green-50 border border-green-300 rounded-md px-2.5 py-1.5 text-xs"
      >
        <span class="text-green-700">{{ fileIcon(f.filename) }} {{ f.filename }}</span>
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

    <div class="flex items-center space-x-4">
      <label class="flex items-center space-x-1.5 cursor-pointer">
        <input type="checkbox" v-model="skipThinking" class="w-3.5 h-3.5 rounded border-gray-300 text-primary-500 focus:ring-primary-300" />
        <span class="text-[10px] text-gray-500">⚡ 跳过思考过程，直接输出</span>
      </label>
    </div>

    <div class="flex items-center space-x-2 flex-wrap gap-y-1">
      <span class="text-[10px] text-gray-400">快捷指令：</span>
      <button
        v-for="shortcut in shortcuts"
        :key="shortcut.label"
        @click="userInput = shortcut.prompt"
        class="text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded hover:bg-primary-100 hover:text-primary-600"
      >
        {{ shortcut.label }}
      </button>
      <input ref="refFileInput" type="file" accept=".md,.pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.txt,.py,.js,.ts,.java,.c,.cpp,.go,.rs,.skill.zip" class="hidden" multiple @change="handleRefFileSelect" />
      <button
        @click="($refs.refFileInput as any)?.click()"
        class="text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded hover:bg-primary-100 hover:text-primary-600"
      >
        📁 上传参考
      </button>
    </div>

    <div v-if="modeSuggestion" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30" @click.self="dismissModeSuggestion">
      <div class="bg-white rounded-xl shadow-2xl p-6 max-w-sm mx-4 border border-primary-200">
        <div class="text-center mb-4">
          <div class="text-3xl mb-2">🔀</div>
          <h3 class="text-base font-semibold text-gray-800">建议切换模式</h3>
        </div>
        <p class="text-sm text-gray-600 mb-1">
          AI 检测到您的需求更适合
          <span class="font-semibold text-primary-600">{{ modeNameMap[modeSuggestion.mode] || modeSuggestion.mode }}</span>
          模式
        </p>
        <p class="text-xs text-gray-400 mb-4">{{ modeSuggestion.reason }}</p>

        <div v-if="modeSuggestion.mode === 'polish'" class="space-y-3 mb-5 border-t pt-4">
          <div>
            <label class="text-xs text-gray-500 block mb-1">目标语言</label>
            <select v-model="polishTargetLang" class="w-full border rounded px-2 py-1.5 text-xs">
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
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">写作风格</label>
            <select v-model="polishStyle" class="w-full border rounded px-2 py-1.5 text-xs">
              <option value="academic">学术写作</option>
              <option value="business">商业计划书</option>
              <option value="formal">正式公文</option>
              <option value="email_professor">教授邮件</option>
              <option value="casual">日常交流</option>
            </select>
          </div>
        </div>

        <div class="flex space-x-3">
          <button
            @click="dismissModeSuggestion"
            class="flex-1 px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50"
          >
            继续当前模式
          </button>
          <button
            @click="acceptModeSuggestion"
            class="flex-1 px-4 py-2 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600 font-medium"
          >
            {{ modeSuggestion.mode === 'polish' ? '开始润色' : '切换过去' }}
          </button>
        </div>
      </div>
    </div>

    <div class="border-t pt-2">
      <div class="flex items-center justify-between mb-1.5">
        <span class="text-[10px] text-gray-400 font-medium">材料模板：</span>
        <button
          @click="showTemplates = !showTemplates"
          class="text-[10px] text-primary-500 hover:text-primary-600"
        >
          {{ showTemplates ? '收起' : '展开' }}
        </button>
      </div>
      <div v-if="showTemplates" class="grid grid-cols-4 gap-1.5">
        <button
          v-for="tmpl in store.materialTemplates"
          :key="tmpl.key"
          @click="useTemplate(tmpl)"
          class="flex flex-col items-center p-2 bg-gray-50 rounded-lg hover:bg-primary-50 hover:border-primary-200 border border-transparent transition-colors"
        >
          <span class="text-lg">{{ tmpl.icon }}</span>
          <span class="text-[10px] text-gray-600 mt-0.5">{{ tmpl.name }}</span>
        </button>
      </div>
    </div>

    <div v-if="currentConvFiles.length > 0" class="border-t pt-2">
      <div class="flex items-center justify-between mb-1.5">
        <span class="text-[10px] text-gray-400 font-medium">已生成文件：</span>
        <button
          @click="store.clearGeneratedFiles()"
          class="text-[10px] text-gray-400 hover:text-red-400"
        >
          清空
        </button>
      </div>
      <div class="space-y-1">
        <div
          v-for="file in currentConvFiles.slice(0, 5)"
          :key="file.filename"
          class="flex items-center justify-between bg-green-50 border border-green-200 rounded-lg px-2.5 py-1.5"
        >
          <div class="flex items-center space-x-2 min-w-0">
            <span class="text-sm">{{ formatIcon(file.file_format) }}</span>
            <div class="min-w-0">
              <div class="text-xs font-medium text-gray-700 truncate">{{ file.file_name }}</div>
              <div class="text-[10px] text-gray-400">{{ file.file_format.toUpperCase() }} · {{ formatSize(file.file_size) }}</div>
            </div>
          </div>
          <a
            :href="downloadUrl(file)"
                       :download="file.filename"
            class="text-[10px] bg-primary-500 text-white px-2 py-0.5 rounded hover:bg-primary-600 shrink-0"
          >
            下载
          </a>
        </div>
      </div>
    </div>

    <div v-if="showFileSave" class="border-t pt-2">
      <div class="flex items-center space-x-2">
        <span class="text-[10px] text-gray-400">保存为文件：</span>
        <select
          v-model="saveFormat"
          class="text-[10px] border rounded px-1.5 py-0.5 focus:ring-1 focus:ring-primary-300"
        >
          <option value="md">Markdown (.md)</option>
          <option value="html">HTML (.html)</option>
          <option value="txt">纯文本 (.txt)</option>
        </select>
        <button
          @click="saveAsFile"
          :disabled="isSavingFile"
          class="text-[10px] bg-green-500 text-white px-2.5 py-0.5 rounded hover:bg-green-600 disabled:opacity-50"
        >
          {{ isSavingFile ? '保存中...' : '保存' }}
        </button>
        <button
          @click="showFileSave = false"
          class="text-[10px] text-gray-400 hover:text-gray-600"
        >
          取消
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import { useAppStore } from '../stores/app';
import { streamPost, apiClient, validateUploadFile } from '../utils/api';
import type { MaterialTemplate, GeneratedFile } from '../utils/api';
import { useRouter } from 'vue-router';

const store = useAppStore();
const router = useRouter();
const userInput = ref('');
const showTemplates = ref(true);
const showFileSave = ref(false);
const saveFormat = ref('md');
const refUploadProgress = ref(0);
const isUploading = ref(false);
const skipThinking = ref(false);

const modeSuggestion = ref<{ mode: string; reason: string } | null>(null);
const polishTargetLang = ref('auto');
const polishStyle = ref('academic');

const modeRouteMap: Record<string, string> = {
  literature: '/literature',
  meeting: '/meeting',
  polish: '/polish',
  ppt: '/ppt',
};

const modeNameMap: Record<string, string> = {
  literature: '📚 文献摘要',
  meeting: '🎙️ 会议纪要',
  polish: '✍️ 多语言润色',
  ppt: '📊 PPT生成',
  xlsx: '📊 Excel生成',
  docx: '📃 文档生成',
};

async function acceptModeSuggestion() {
  if (!modeSuggestion.value) return;

  if (modeSuggestion.value.mode === 'polish') {
    const pendingSuggestion = modeSuggestion.value;
    modeSuggestion.value = null;

    const text = userInput.value.trim() || store.lastUserMessage || '';
    if (!text) {
      router.push('/polish');
      return;
    }

    const userMsg = text;
    store.lastUserMessage = userMsg;

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
      store.updateWorkflowStep(1, 'active');
      const ctrl = store.createStreamController();

      for await (const event of streamPost('/polish/stream', {
        text: userMsg,
        target_language: polishTargetLang.value,
        style: polishStyle.value,
        conv_id: myConvId || undefined,
        skip_thinking: skipThinking.value,
        detect_source_lang: true,
      }, ctrl.signal)) {
        if (store.currentConvId !== myConvId) break;
        if (event.type === 'stream' && event.role === 'actor') {
          store.actorText += event.content || '';
          store.updateWorkflowStep(0, 'completed');
          store.updateWorkflowStep(1, 'active');
        } else if (event.type === 'stream' && event.role === 'critic') {
          store.criticText += event.content || '';
          store.updateWorkflowStep(1, 'completed');
          store.updateWorkflowStep(2, 'active');
        } else if (event.type === 'complete') {
          store.workflowSteps.forEach((_: any, i: number) => {
            store.updateWorkflowStep(i, 'completed');
          });
          store.isProcessing = false;
          store.finalOutput = event.output || store.actorText;
          store.saveMessage('actor', store.finalOutput).then(() => {
            store.saveMessage('critic', store.criticText);
          }).then(() => {
            store.loadConversations();
          }).catch((e: any) => console.error('Save failed:', e));
        } else if (event.type === 'lang_mismatch') {
          modeSuggestion.value = null;
          store.isProcessing = false;
          const doTranslate = confirm((event as any).message || '检测到语言不匹配，是否翻译为目标语言？');
          const resolvedLang = doTranslate
            ? (event as any).target_language || polishTargetLang.value
            : (event as any).source_language || 'auto';
          polishTargetLang.value = resolvedLang;
          store.isProcessing = true;
          store.clearWorkflow();
          store.addWorkflowStep('文本分析');
          store.addWorkflowStep('Actor 润色');
          store.addWorkflowStep('Critic 审查（语体校验）');
          store.addWorkflowStep('修正与输出');
          store.updateWorkflowStep(0, 'active');
          store.updateWorkflowStep(1, 'active');
          const ctrl2 = store.createStreamController();
          for await (const event2 of streamPost('/polish/stream', {
            text: userMsg,
            target_language: resolvedLang,
            style: polishStyle.value,
            conv_id: myConvId || undefined,
            skip_thinking: skipThinking.value,
            detect_source_lang: true,
            confirm_lang: true,
          }, ctrl2.signal)) {
            if (store.currentConvId !== myConvId) break;
            if (event2.type === 'stream' && event2.role === 'actor') {
              store.actorText += event2.content || '';
              store.updateWorkflowStep(0, 'completed');
              store.updateWorkflowStep(1, 'active');
            } else if (event2.type === 'stream' && event2.role === 'critic') {
              store.criticText += event2.content || '';
              store.updateWorkflowStep(1, 'completed');
              store.updateWorkflowStep(2, 'active');
            } else if (event2.type === 'complete') {
              store.workflowSteps.forEach((_: any, i: number) => store.updateWorkflowStep(i, 'completed'));
              store.isProcessing = false;
              store.finalOutput = event2.output || store.actorText;
              store.saveMessage('actor', store.finalOutput).then(() => {
                store.saveMessage('critic', store.criticText);
              }).then(() => {
                store.loadConversations();
              }).catch((e: any) => console.error('Save failed:', e));
            } else if (event2.type === 'error') {
              store.isProcessing = false;
              store.finalOutput = event2.message || '处理过程中发生错误';
            }
          }
          return;
        } else if (event.type === 'error') {
          store.isProcessing = false;
          store.finalOutput = event.message || '处理过程中发生错误';
        }
      }
    } catch (e) {
      console.error('Polish from chat failed:', e);
      store.isProcessing = false;
    } finally {
      userInput.value = '';
    }
    return;
  }

  if (modeSuggestion.value.mode === 'xlsx' || modeSuggestion.value.mode === 'docx') {
    modeSuggestion.value = null;
    return;
  }

  const targetMode = modeSuggestion.value.mode;
  const targetRoute = modeRouteMap[targetMode];
  modeSuggestion.value = null;

  if (targetRoute) {
    try {
      await store.startNewConversation(targetMode, userInput.value.trim() || '');
    } catch (e) {
      console.error('Failed to create conversation for mode switch:', e);
    }
    router.push(targetRoute);
  }
}

function dismissModeSuggestion() {
  modeSuggestion.value = null;
}

interface RefFileInfo {
  filename: string;
  file_path: string;
  stored_filename?: string;
  relative_path?: string;
}
const uploadedRefFiles = ref<RefFileInfo[]>([]);

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

  if (file.name.endsWith('.skill.zip')) {
    try {
      isUploading.value = true;
      refUploadProgress.value = 5;
      const res = await apiClient.importSkillFromZip(file, (progress) => {
        refUploadProgress.value = Math.round(progress);
      });
      refUploadProgress.value = 100;
      setTimeout(() => { refUploadProgress.value = 0; isUploading.value = false; }, 1000);
      userInput.value = `已导入 Skill: ${res.data.skill_name}`;
    } catch (e) {
      console.error('Import skill failed:', e);
      refUploadProgress.value = 0;
      isUploading.value = false;
    }
    return;
  }

  isUploading.value = true;
  refUploadProgress.value = 5;
  try {
    const convId = store.currentConvId || undefined;
    const res = await apiClient.uploadFile(file, 'chat', convId, undefined, (progress) => {
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
const isSavingFile = ref(false);

const currentConvFiles = computed(() => {
  if (!store.currentConvId) return [];
  return store.generatedFiles.filter(f => f.conv_id === store.currentConvId);
});

const shortcuts = [
  { label: '帮我写周报', prompt: '请帮我写一份本周工作周报，包括完成事项、进行中事项和下周计划', autoSend: true },
  { label: '翻译这段话', prompt: '请将以下内容翻译为英文：', autoSend: false },
  { label: '总结要点', prompt: '请帮我总结以下内容的要点：', autoSend: false },
  { label: '润色邮件', prompt: '请帮我润色一封写给教授的邮件：', autoSend: false },
  { label: '写报告', prompt: '请帮我撰写一份结构化的工作报告，包含背景、分析、结论和建议', autoSend: true },
  { label: '生成方案', prompt: '请帮我撰写一份项目方案书，包含目标、实施步骤、时间规划和预期成果', autoSend: true },
];

async function sendMessage() {
  if (!userInput.value.trim() || store.isProcessing) return;

  let _reactStreamStep = 0;
  let _reactIter = 1;
  const message = userInput.value.trim();
  userInput.value = '';

  const refFileContext = uploadedRefFiles.value.length > 0
    ? '\n\n[参考文件]\n' + uploadedRefFiles.value.map(f => `文件: ${f.filename} (路径: ${f.file_path})`).join('\n')
    : '';

  store.currentRefFiles = uploadedRefFiles.value.map(f => ({ filename: f.filename, file_path: f.file_path, stored_filename: f.stored_filename, relative_path: f.relative_path, download_url: f.relative_path ? `/api/files/download/${f.relative_path}` : undefined }));
  store.lastUserMessage = message + (uploadedRefFiles.value.length > 0 ? ` [附带${uploadedRefFiles.value.length}个参考文件]` : '');

  if (store.offlineMode) {
    await store.loadOfflineDemo('chat');
    return;
  }

  if (!store.currentConvId || store.currentConvType !== 'chat') {
    await store.startNewConversation('chat', store.lastUserMessage);
  } else {
    await store.saveMessage('user', store.lastUserMessage);
  }
  store.lastUserMessage = message + (uploadedRefFiles.value.length > 0 ? ` [附带${uploadedRefFiles.value.length}个参考文件]` : '');

  const myConvId = store.currentConvId;

  store.isProcessing = true;
  store.clearWorkflow();
  store.addWorkflowStep('理解意图');
  store.addWorkflowStep('Actor 生成回复');
  store.addWorkflowStep('Critic 审查');
  store.addWorkflowStep('修正与输出');

  try {
    store.updateWorkflowStep(0, 'completed');
    store.updateWorkflowStep(1, 'active');
    const ctrl = store.createStreamController();

    for await (const event of streamPost('/chat/stream', {
      message: message + refFileContext,
      conv_id: store.currentConvId || undefined,
      ref_files: uploadedRefFiles.value.map(f => ({ filename: f.filename, file_path: f.file_path })),
      skip_thinking: skipThinking.value,
      mode: 'chat',
    }, ctrl.signal)) {
      if (store.currentConvId !== myConvId) break;
      if (event.type === 'stream' && event.role === 'actor') {
        store.actorText += event.content || '';
        store.appendThinkingRound('actor', event.iteration || 1, event.content || '');
      } else if (event.type === 'stream' && event.role === 'critic') {
        store.criticText += event.content || '';
        store.appendThinkingRound('critic', event.iteration || 1, event.content || '');
        if (store.workflowSteps[2]?.status !== 'completed') {
          store.updateWorkflowStep(1, 'completed');
          store.updateWorkflowStep(2, 'active');
        }
      } else if (event.type === 'actor_done') {
        store.updateWorkflowStep(1, 'completed');
        store.updateWorkflowStep(2, 'active');
        if (event.title) {
          store.loadConversations();
        }
      } else if (event.type === 'critic_done') {
        store.updateWorkflowStep(2, 'completed');
        if (event.approved) {
          store.updateWorkflowStep(3, 'active');
        } else {
          store.updateWorkflowStep(1, 'active');
          store.updateWorkflowStep(3, 'active');
        }
      } else if (event.type === 'heartbeat') {
      } else if (event.type === 'react_start') {
        _reactIter = (event as any).iteration || 1;
        store.appendThinkingRound('react', _reactIter, '');
      } else if (event.type === 'react_thought') {
        if ((event as any).streaming) {
          if (_reactStreamStep !== (event as any).step) {
            _reactStreamStep = (event as any).step;
            store.appendThinkingRound('react', _reactIter, `🤔 思考: `);
          }
          store.appendThinkingRound('react', _reactIter, (event as any).thought || '');
        } else {
          if (_reactStreamStep === (event as any).step) {
            store.appendThinkingRound('react', _reactIter, '\n');
            _reactStreamStep = 0;
          } else {
            store.appendThinkingRound('react', _reactIter, `🤔 思考: ${(event as any).thought || ''}\n`);
          }
        }
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
      } else if (event.type === 'file_generated' && event.file) {
        store.addGeneratedFile(event.file as GeneratedFile);
      } else if (event.type === 'file_error') {
        console.error('File generation error:', event.error);
      } else if (event.type === 'skill_imported') {
        store.actorText += `\n\n✅ Skill "${event.skill_name}" 已成功导入！`;
      } else if (event.type === 'skill_import_error') {
        store.actorText += `\n\n❌ Skill 导入失败：${event.error}`;
      } else if (event.type === 'mode_suggestion') {
        modeSuggestion.value = { mode: event.suggested_mode || '', reason: event.reason || '' };
      } else if (event.type === 'title_generated') {
        if (event.conv_id && event.title) {
          store.loadConversations();
        }
      } else if (event.type === 'complete') {
        store.updateWorkflowStep(2, 'completed');
        store.updateWorkflowStep(3, 'completed');
        store.finalOutput = event.output || store.actorText;
        store.isProcessing = false;

        store.saveMessage('actor', store.finalOutput).then(() => {
          store.saveMessage('critic', store.criticText);
        }).then(() => {
          if (store.currentRefFiles.length > 0) {
            store.saveFilesMessage(store.currentRefFiles);
          }
        }).then(() => {
          store.loadConversations();
        }).catch((e: any) => {
          console.error('Save message failed:', e);
        });

        if (store.actorText.trim() && !store.generatedFiles.length) {
          showFileSave.value = true;
        }
      }
    }
  } catch (e) {
    console.error('Chat failed:', e);
    store.actorText = '抱歉，处理时出错了，请重试。';
  } finally {
    store.isProcessing = false;
    uploadedRefFiles.value = [];
  }
}

function useTemplate(tmpl: MaterialTemplate) {
  userInput.value = tmpl.prompt;
}

async function saveAsFile() {
  if (!store.actorText.trim()) return;
  isSavingFile.value = true;
  try {
    const fileInfo = await store.generateFileFromContent(
      store.actorText,
      saveFormat.value,
      '对话内容',
    );
    if (fileInfo) {
      showFileSave.value = false;
    }
  } finally {
    isSavingFile.value = false;
  }
}

function downloadUrl(file: GeneratedFile): string {
  if (file.relative_path) {
    return `/api/files/download/${file.relative_path}`;
  }
  if (file.download_url) {
    return file.download_url.startsWith('/') ? `/api${file.download_url}` : file.download_url;
  }
  const mode = store.currentConvType || 'chat';
  return `/api/chat/download/${file.stored_filename || file.filename}?mode=${mode}&conv_id=${store.currentConvId || ''}`;
}

function formatIcon(fmt: string): string {
  const icons: Record<string, string> = { md: '📝', html: '🌐', txt: '📄' };
  return icons[fmt] || '📄';
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

onMounted(() => {
  store.loadMaterialTemplates();
  store.loadGeneratedFiles();
});

watch(() => store.droppedFileInfo, (info) => {
  if (info) {
    uploadedRefFiles.value.push({
      filename: info.filename,
      file_path: info.file_path,
      stored_filename: info.file_path.split(/[/\\]/).pop() || info.filename,
    });
    store.droppedFileInfo = null;
  }
});
</script>
