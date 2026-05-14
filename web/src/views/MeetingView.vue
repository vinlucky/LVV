<template>
  <div class="relative space-y-3">
    <div class="flex items-center space-x-3">
      <div class="flex space-x-1">
        <button
          @click="mode = 'realtime'"
          :class="mode === 'realtime' ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-600'"
          class="px-3 py-1 rounded text-xs font-medium"
        >
          实时监听
        </button>
        <button
          @click="mode = 'upload'"
          :class="mode === 'upload' ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-600'"
          class="px-3 py-1 rounded text-xs font-medium"
        >
          上传文件
        </button>
        <button
          @click="mode = 'text'"
          :class="mode === 'text' ? 'bg-green-500 text-white' : 'bg-gray-100 text-gray-600'"
          class="px-3 py-1 rounded text-xs font-medium"
        >
          文本输入
        </button>
      </div>
      <select v-model="language" class="border rounded px-2 py-1 text-xs">
        <option value="auto">🔍 自动识别</option>
        <option value="zh">中文</option>
        <option value="en">英文</option>
        <option value="ja">日文</option>
        <option value="bilingual">双语对照</option>
      </select>
      <label class="flex items-center space-x-1.5 cursor-pointer ml-4">
        <input type="checkbox" v-model="skipThinking" class="w-3.5 h-3.5 rounded border-gray-300 text-primary-500 focus:ring-primary-300" />
        <span class="text-[10px] text-gray-500">⚡ 跳过思考</span>
      </label>
      <label class="flex items-center space-x-1 cursor-pointer ml-4">
        <span class="text-[10px] text-gray-500">📄</span>
        <select v-model="outputFormat" class="border rounded px-1.5 py-0.5 text-[10px]">
          <option value="md">Markdown</option>
          <option value="docx">Word</option>
          <option value="xlsx">Excel</option>
        </select>
      </label>
    </div>

    <div v-if="mode === 'realtime'" class="flex items-center space-x-2">
      <button
        @click="startRealtime"
        :disabled="isRecording"
        class="px-3 py-1.5 bg-green-500 text-white rounded text-xs disabled:opacity-50"
      >
        {{ isRecording ? '录音中...' : '开始会议' }}
      </button>
      <button
        @click="stopRealtime"
        :disabled="!isRecording"
        class="px-3 py-1.5 bg-red-500 text-white rounded text-xs disabled:opacity-50"
      >
        结束会议
      </button>
      <label class="flex items-center space-x-1 cursor-pointer" :class="{ 'opacity-50': isRecording }">
        <span class="text-[10px] text-gray-500">🎤</span>
        <select v-model="audioSourceMode" class="border rounded px-1.5 py-0.5 text-[10px]" :disabled="isRecording">
          <option value="mic">仅麦克风</option>
          <option value="system">仅系统声音</option>
          <option value="both">麦克风+系统声音</option>
        </select>
      </label>
      <span v-if="isRecording" class="text-xs text-red-500 animate-pulse">● REC</span>
      <span v-if="isRecording" class="text-xs text-gray-600 font-mono">{{ formattedDuration }}</span>
      <span v-if="isRecording && vadState === 'silence'" class="text-xs text-gray-400">静音中...</span>
      <span v-if="isRecording && vadState === 'speech'" class="text-xs text-green-500">检测到人声</span>
      <span v-if="recordingFilePath" class="text-xs text-blue-500">💾 录音已保存</span>
    </div>

    <div v-if="uploadedAudioFiles.length > 0 || uploadedRefFiles.length > 0" class="flex items-center space-x-2 overflow-x-auto pb-1 mb-2">
        <div
          v-for="(f, idx) in uploadedAudioFiles"
          :key="'audio-'+idx"
          class="flex-shrink-0 flex items-center space-x-1.5 bg-green-50 border border-green-300 rounded-md px-2.5 py-1.5 text-xs"
        >
          <span class="text-green-700">🎵 {{ f.filename }}</span>
          <a
            v-if="f.relative_path"
            :href="`/api/files/download/${f.relative_path}`"
            :download="f.filename"
            class="text-[10px] text-primary-500 hover:text-primary-600"
          >📥</a>
          <button @click="removeAudioFile(idx)" class="text-red-400 hover:text-red-600">✕</button>
        </div>
        <div
          v-for="(f, idx) in uploadedRefFiles"
          :key="'ref-'+idx"
          class="flex-shrink-0 flex items-center space-x-1.5 bg-blue-50 border border-blue-300 rounded-md px-2.5 py-1.5 text-xs"
        >
          <span class="text-blue-700">{{ fileIcon(f.filename) }} {{ f.filename }}</span>
          <a
            v-if="f.relative_path"
            :href="`/api/files/download/${f.relative_path}`"
            :download="f.filename"
            class="text-[10px] text-primary-500 hover:text-primary-600"
          >📥</a>
          <button @click="removeRefFile(idx)" class="text-red-400 hover:text-red-600">✕</button>
        </div>
      </div>

    <div v-if="mode === 'upload'">
      <p v-if="uploadedAudioFiles.length === 0 && uploadedRefFiles.length === 0" class="text-[10px] text-gray-400 mb-1">拖拽文件到页面任意位置，或点击下方按钮选择</p>
      <div class="flex space-x-2">
        <input ref="audioInput" type="file" accept="audio/*,video/*" class="hidden" @change="handleAudioSelect" />
        <input ref="fileInput" type="file" accept=".pdf,.md,.docx,.doc,.txt,.xlsx,.xls,.pptx,.ppt,.py,.js,.ts,.java,.c,.cpp,.go,.rs" class="hidden" multiple @change="handleFileSelect" />
        <button @click="($refs.audioInput as any)?.click()" class="px-3 py-1.5 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200">🎵 选择录音/视频</button>
        <button @click="($refs.fileInput as any)?.click()" class="px-3 py-1.5 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200">📁 选择文档</button>
      </div>
      <div v-if="fileUploadProgress > 0 && fileUploadProgress < 100" class="mt-2 w-full bg-gray-200 rounded-full h-1.5">
        <div class="bg-primary-500 h-1.5 rounded-full transition-all duration-300" :style="{ width: fileUploadProgress + '%' }"></div>
      </div>
      <div v-if="fileUploadProgress > 0 && fileUploadProgress < 100" class="text-[10px] text-primary-500 mt-1">上传中 {{ fileUploadProgress }}%</div>
      <div v-if="uploadTaskId" class="mt-2 text-xs text-blue-600">
        任务: {{ uploadTaskId.slice(0,8) }}...
        <div class="w-full bg-gray-200 rounded-full h-1 mt-1">
          <div class="bg-primary-500 h-1 rounded-full progress-bar" :style="{ width: uploadProgress + '%' }"></div>
        </div>
      </div>
    </div>

    <div v-if="mode === 'text'" class="flex space-x-2">
      <textarea
        v-model="transcript"
        class="flex-1 border rounded px-3 py-2 text-sm min-h-[60px] max-h-[200px] focus:ring-2 focus:ring-primary-300 resize-y"
        placeholder="粘贴会议记录文本，或拖拽录音文件到此处...（Shift+Enter换行）"
        @keydown.enter.exact.prevent="generateMinutes"
      ></textarea>
    </div>

    <button
      @click="generateMinutes"
      :disabled="store.isProcessing || !canGenerate"
      class="px-4 py-1.5 bg-primary-500 text-white rounded text-xs font-medium disabled:opacity-50 hover:bg-primary-600"
    >
      {{ store.isProcessing ? '处理中...' : '生成会议纪要' }}
    </button>

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
              <div class="text-[10px] text-gray-400">{{ (file.file_format || '').toUpperCase() }} · {{ formatSize(file.file_size || 0) }}</div>
            </div>
          </div>
          <a
            :href="genFileDownloadUrl(file)"
            :download="file.filename"
            class="text-[10px] bg-primary-500 text-white px-2 py-0.5 rounded hover:bg-primary-600 shrink-0"
          >
            下载
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onBeforeUnmount, watch, computed } from 'vue';
import { useAppStore } from '../stores/app';
import { streamPost, streamUpload, apiClient, validateUploadFile } from '../utils/api';

const store = useAppStore();
const mode = ref<'realtime' | 'upload' | 'text'>('text');
const language = ref('auto');
const transcript = ref('');
const isRecording = ref(false);
const uploadTaskId = ref('');
const uploadProgress = ref(0);
const vadState = ref<'silence' | 'speech'>('silence');
const recordingFilePath = ref('');
const fileUploadProgress = ref(0);
const recordingDuration = ref(0);
const recordingSeconds = ref(0);
const skipThinking = ref(false);
const audioSourceMode = ref<'mic' | 'system' | 'both'>('both');
const outputFormat = ref<'md' | 'docx' | 'xlsx'>('docx');

let mediaRecorder: MediaRecorder | null = null;
let currentStream: MediaStream | null = null;
let audioContext: AudioContext | null = null;
let mixAudioCtx: AudioContext | null = null;
let analyser: AnalyserNode | null = null;
let vadInterval: number | null = null;
let durationInterval: number | null = null;
let recordedChunks: Blob[] = [];
let isSilent = true;
const SILENCE_THRESHOLD = 0.01;

interface AudioFileInfo {
  filename: string;
  task_id: string;
  stored_filename?: string;
  transcript?: string;
  file_path?: string;
  relative_path?: string;
}
const uploadedAudioFiles = ref<AudioFileInfo[]>([]);

interface RefFileInfo {
  filename: string;
  file_path: string;
  stored_filename?: string;
  relative_path?: string;
}
const uploadedRefFiles = ref<RefFileInfo[]>([]);

const canGenerate = computed(() => {
  return !!transcript.value || (store.actorText && store.actorText.length > 10) || uploadedAudioFiles.value.length > 0 || uploadedRefFiles.value.length > 0;
});

const currentConvFiles = computed(() => {
  if (!store.currentConvId) return [];
  return store.generatedFiles.filter(f => f.conv_id === store.currentConvId);
});

const formattedDuration = computed(() => {
  const mins = Math.floor(recordingDuration.value / 60);
  const secs = recordingDuration.value % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
});

onBeforeUnmount(() => {
  if (isRecording.value) {
    stopRealtime();
  }
  if (vadInterval) {
    clearInterval(vadInterval);
    vadInterval = null;
  }
  if (durationInterval) {
    clearInterval(durationInterval);
    durationInterval = null;
  }
});

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function downloadText(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  downloadBlob(blob, filename);
}

async function saveMeetingMinutesToHistory(content: string) {
  const convId = store.currentConvId || undefined;
  try {
    const res = await apiClient.saveMeetingMinutes(content, convId, 'meeting');
    if (res.data.stored_filename) {
      store.addGeneratedFile({
        filename: res.data.filename,
        file_name: res.data.filename,
        file_path: res.data.file_path || '',
        stored_filename: res.data.stored_filename,
        relative_path: res.data.relative_path || '',
        file_format: 'md',
        file_size: 0,
        download_url: `/api/files/download/${res.data.relative_path}`,
        conv_id: convId || '',
      });
    }
  } catch (e) {
    console.error('Failed to save meeting minutes:', e);
  }
}

async function startRealtime() {
  try {
    isRecording.value = true;
    recordedChunks = [];
    recordingFilePath.value = '';
    recordingDuration.value = 0;

    store.isProcessing = true;
    store.lastUserMessage = '实时会议录音';

    if (!store.currentConvId) {
      await store.startNewConversation('meeting', '实时会议录音');
    }

    store.clearWorkflow();
    store.addWorkflowStep('启动麦克风');
    store.addWorkflowStep('录音中');
    store.addWorkflowStep('转写与生成纪要');

    store.updateWorkflowStep(0, 'active');

    let stream: MediaStream;
    if (audioSourceMode.value === 'system') {
      try {
        const displayStream = await navigator.mediaDevices.getDisplayMedia({
          video: true,
          audio: true,
        });
        displayStream.getVideoTracks().forEach(t => t.stop());

        if (displayStream.getAudioTracks().length === 0) {
          isRecording.value = false;
          store.isProcessing = false;
          store.actorText = '未检测到系统音频，请确保共享时勾选了"分享音频"选项。';
          return;
        }

        stream = new MediaStream(displayStream.getAudioTracks());

        displayStream.getAudioTracks().forEach(t => {
          t.addEventListener('ended', () => {
            if (isRecording.value) {
              store.transcriptText += '\n共享音频流已结束\n';
            }
          });
        });
      } catch (e: any) {
        if (e.name === 'NotAllowedError') {
          isRecording.value = false;
          store.isProcessing = false;
          store.actorText = '用户取消了屏幕共享，无法捕获系统声音。请重试或切换为"仅麦克风"模式。';
          return;
        }
        throw e;
      }
    } else if (audioSourceMode.value === 'both') {
      try {
        const displayStream = await navigator.mediaDevices.getDisplayMedia({
          video: true,
          audio: true,
        });
        displayStream.getVideoTracks().forEach(t => t.stop());

        const micStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            sampleRate: 44100,
          },
        });

        const mixCtx = new AudioContext({ sampleRate: 44100 });
        mixAudioCtx = mixCtx;
        const dest = mixCtx.createMediaStreamDestination();

        if (displayStream.getAudioTracks().length > 0) {
          const displaySrc = mixCtx.createMediaStreamSource(displayStream);
          const displayGain = mixCtx.createGain();
          displayGain.gain.value = 1.0;
          displaySrc.connect(displayGain);
          displayGain.connect(dest);
        }

        const micSrc = mixCtx.createMediaStreamSource(micStream);
        const micGain = mixCtx.createGain();
        micGain.gain.value = 1.0;
        micSrc.connect(micGain);
        micGain.connect(dest);

        stream = dest.stream;

        displayStream.getAudioTracks().forEach(t => {
          t.addEventListener('ended', () => {
            if (isRecording.value) {
              store.transcriptText += '\n共享音频流已结束\n';
            }
          });
        });
      } catch (e: any) {
        if (e.name === 'NotAllowedError') {
          isRecording.value = false;
          store.isProcessing = false;
          store.actorText = '用户取消了屏幕共享，无法捕获系统声音。请重试或切换为"仅麦克风"模式。';
          return;
        }
        throw e;
      }
    } else {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
      });
    }
    currentStream = stream;
    store.updateWorkflowStep(0, 'completed');
    store.updateWorkflowStep(1, 'active');

    audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(stream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);

    mediaRecorder = new MediaRecorder(stream, {
      mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm',
    });

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    };

    mediaRecorder.start(1000);

    durationInterval = window.setInterval(() => {
      recordingDuration.value++;
    }, 1000);

    vadInterval = window.setInterval(() => {
      detectVAD();
    }, 500);

  } catch (e) {
    console.error('Failed to start recording:', e);
    isRecording.value = false;
    store.isProcessing = false;
  }
}

function detectVAD() {
  if (!analyser) return;

  const dataArray = new Float32Array(analyser.fftSize);
  analyser.getFloatTimeDomainData(dataArray);

  let sumSquares = 0;
  for (let i = 0; i < dataArray.length; i++) {
    sumSquares += dataArray[i] * dataArray[i];
  }
  const rms = Math.sqrt(sumSquares / dataArray.length);

  if (rms > SILENCE_THRESHOLD) {
    isSilent = false;
    vadState.value = 'speech';
  } else {
    isSilent = true;
    vadState.value = 'silence';
  }
}

async function stopRealtime() {
  if (!isRecording.value) return;
  isRecording.value = false;

  if (vadInterval) {
    clearInterval(vadInterval);
    vadInterval = null;
  }

  if (durationInterval) {
    clearInterval(durationInterval);
    durationInterval = null;
  }

  store.updateWorkflowStep(1, 'completed');
  store.updateWorkflowStep(2, 'active');

  const stopPromise = new Promise<void>((resolve) => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.onstop = () => {
        resolve();
      };
      mediaRecorder.stop();
    } else {
      resolve();
    }
  });

  await stopPromise;

  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }

  if (mixAudioCtx) {
    mixAudioCtx.close();
    mixAudioCtx = null;
  }

  if (currentStream) {
    currentStream.getTracks().forEach(track => track.stop());
    currentStream = null;
  }

  analyser = null;

  if (recordedChunks.length === 0) {
    store.actorText = '未录制到音频，请重试';
    store.updateWorkflowStep(2, 'completed');
    store.isProcessing = false;
    return;
  }

  const audioBlob = new Blob(recordedChunks, { type: 'audio/webm' });
  const recordingFilename = `meeting_recording_${new Date().toISOString().replace(/[:.]/g, '-')}.webm`;

  downloadBlob(audioBlob, recordingFilename);
  store.transcriptText += `\n录音已保存: ${recordingFilename}\n`;
  recordingFilePath.value = recordingFilename;

  try {
    store.transcriptText += '正在上传录音至服务器...\n';
    const file = new File([audioBlob], recordingFilename, { type: 'audio/webm' });
    const convId = store.currentConvId || undefined;

    let uploadedFilePath = '';
    let uploadedRelativePath = '';
    try {
      const uploadRes = await apiClient.uploadFile(file, 'meeting', convId, undefined, (progress) => {});
      uploadedFilePath = uploadRes.data.file_path;
      uploadedRelativePath = uploadRes.data.relative_path || '';
      store.transcriptText += '录音上传成功，正在处理音频...\n';
    } catch (uploadErr) {
      console.error('Upload recording failed:', uploadErr);
      store.actorText = '录音上传失败，请检查网络连接后重试';
      store.updateWorkflowStep(2, 'completed');
      store.isProcessing = false;
      await store.saveMessage('actor', store.actorText);
      return;
    }

    const formData = new FormData();
    formData.append('file_path', uploadedFilePath);
    formData.append('language', language.value === 'bilingual' ? 'zh' : (language.value === 'auto' ? 'zh' : language.value));
    if (store.currentConvId) formData.append('conv_id', store.currentConvId);
    formData.append('skip_thinking', String(skipThinking.value));
    formData.append('output_format', outputFormat.value);

    const myConvId = store.currentConvId;
    const ctrl = store.createStreamController();
    let generatedFileInfo: any = null;
    let transcriptText = '';
    let _reactIter = 1;

    for await (const event of streamUpload('/meeting/audio/stream', formData, ctrl.signal)) {
      if (store.currentConvId !== myConvId) break;
      if (event.type === 'step' && event.message) {
        store.transcriptText += `${event.message}\n`;
      } else if (event.type === 'stream' && event.role === 'transcript') {
        transcriptText += event.content || '';
        store.transcriptText += event.content || '';
      } else if (event.type === 'transcript_done') {
        transcriptText = event.transcript || transcriptText;
        const method = event.method === 'whisper' ? 'Whisper' : '全模态模型';
        store.transcriptText += `\n--- ${method}转写完成 ---\n`;
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
      } else if (event.type === 'stream' && event.role === 'critic') {
        store.criticText += event.content || '';
        store.appendThinkingRound('critic', event.iteration || 1, event.content || '');
      } else if (event.type === 'actor_done' && event.title) {
        store.loadConversations();
      } else if (event.type === 'file_generated' && event.file) {
        const f = event.file;
        generatedFileInfo = {
          filename: f.filename,
          file_path: f.file_path || '',
          stored_filename: f.stored_filename || '',
          relative_path: f.relative_path || '',
          file_format: f.file_format || 'md',
          download_url: f.relative_path ? `/api/files/download/${f.relative_path}` : '',
        };
      } else if (event.type === 'complete') {
        store.finalOutput = event.output || store.actorText;
        store.updateWorkflowStep(2, 'completed');
        await store.saveMessage('actor', store.finalOutput);
        await store.saveMessage('critic', store.criticText);

        if (generatedFileInfo) {
          store.addGeneratedFile({
            filename: generatedFileInfo.filename,
            file_name: generatedFileInfo.filename,
            file_path: generatedFileInfo.file_path || '',
            stored_filename: generatedFileInfo.stored_filename || '',
            relative_path: generatedFileInfo.relative_path || '',
            file_format: generatedFileInfo.file_format || 'md',
            file_size: generatedFileInfo.file_size || 0,
            download_url: generatedFileInfo.download_url || '',
            conv_id: store.currentConvId || '',
          });
        }
        const refFilesToSave: any[] = [];
        if (uploadedFilePath) {
          refFilesToSave.push({
            filename: recordingFilename,
            file_path: uploadedFilePath,
            stored_filename: recordingFilename,
            relative_path: uploadedRelativePath,
            download_url: uploadedRelativePath ? `/api/files/download/${uploadedRelativePath}` : '',
            conv_id: store.currentConvId || '',
          });
        }
        if (refFilesToSave.length > 0) {
          await store.saveFilesMessage(refFilesToSave);
        }
        await store.loadConversations();
      } else if (event.type === 'error') {
        store.updateWorkflowStep(2, 'completed');
        store.finalOutput = event.message || '纪要生成失败';
        await store.saveMessage('actor', store.finalOutput);
        await store.loadConversations();
      }
    }
  } catch (e) {
    console.error('Transcription/minutes generation failed:', e);
    store.transcriptText += '\n全模态转写或纪要生成失败\n';

    const fallbackText = transcript.value || (store.actorText && store.actorText.length > 10 ? store.actorText : '');
    if (fallbackText.trim()) {
      try {
        store.transcriptText += '尝试使用输入文本直接生成纪要...\n';
        const fallbackConvId = store.currentConvId;
        const ctrl = store.createStreamController();
        let _reactIter2 = 1;
        for await (const event of streamPost('/meeting/minutes/stream', {
          transcript: fallbackText,
          language: language.value,
          skip_thinking: skipThinking.value,
          conv_id: store.currentConvId,
          output_format: outputFormat.value,
        }, ctrl.signal)) {
          if (store.currentConvId !== fallbackConvId) break;
          if (event.type === 'react_start') {
            _reactIter2 = (event as any).iteration || 1;
            store.appendThinkingRound('react', _reactIter2, '');
          } else if (event.type === 'react_thought') {
            store.appendThinkingRound('react', _reactIter2, `🤔 思考: ${(event as any).thought || ''}\n`);
          } else if (event.type === 'tool_call') {
            const args = (event as any).arguments || {};
            const argsStr = Object.entries(args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ');
            store.appendThinkingRound('react', _reactIter2, `🔧 调用工具: ${(event as any).name}(${argsStr})\n`);
          } else if (event.type === 'tool_result') {
            const result = ((event as any).result || '').substring(0, 500);
            store.appendThinkingRound('react', _reactIter2, `📋 工具结果: ${result}${((event as any).result || '').length > 500 ? '...' : ''}\n`);
          } else if (event.type === 'react_done') {
            if ((event as any).steps > 0) {
              store.appendThinkingRound('react', _reactIter2, `✅ ReAct 完成: ${(event as any).steps} 步工具调用\n`);
            }
          } else if (event.type === 'stream' && event.role === 'actor') {
            store.actorText += event.content || '';
            store.appendThinkingRound('actor', event.iteration || 1, event.content || '');
          } else if (event.type === 'file_generated' && event.file) {
            const f = event.file;
            const gfInfo = {
              filename: f.filename,
              file_path: f.file_path || '',
              stored_filename: f.stored_filename || '',
              relative_path: f.relative_path || '',
              file_format: f.file_format || 'md',
              download_url: f.relative_path ? `/api/files/download/${f.relative_path}` : '',
            };
            store.addGeneratedFile({
              filename: gfInfo.filename,
              file_name: gfInfo.filename,
              file_path: gfInfo.file_path,
              stored_filename: gfInfo.stored_filename,
              relative_path: gfInfo.relative_path,
              file_format: gfInfo.file_format,
              file_size: 0,
              download_url: gfInfo.download_url,
              conv_id: store.currentConvId || '',
            });
          } else if (event.type === 'complete') {
            store.finalOutput = event.output || store.actorText;
            store.updateWorkflowStep(2, 'completed');
            await store.saveMessage('actor', store.finalOutput);
            await store.saveMessage('critic', store.criticText);
            await store.loadConversations();
          }
        }
      } catch (e2) {
        console.error('All fallback failed:', e2);
        store.actorText = '纪要生成失败，录音已保存到本地';
        store.updateWorkflowStep(2, 'completed');
      }
    } else {
      store.actorText = '处理失败，录音已保存到本地';
      store.updateWorkflowStep(2, 'completed');
    }
  }

  store.isProcessing = false;
}

function removeAudioFile(idx: number) {
  uploadedAudioFiles.value.splice(idx, 1);
}

function removeRefFile(idx: number) {
  uploadedRefFiles.value.splice(idx, 1);
}

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

function genFileDownloadUrl(file: any): string {
  if (file.relative_path) {
    return `/api/files/download/${String(file.relative_path).replace(/\\/g, '/')}`;
  }
  if (file.download_url) {
    return file.download_url.startsWith('/') ? `/api${file.download_url}` : file.download_url;
  }
  return `/api/meeting/download/${file.stored_filename || file.filename}?conv_id=${store.currentConvId || ''}`;
}

function formatIcon(fmt: string): string {
  const icons: Record<string, string> = { md: '📝', docx: '📃', xlsx: '📊', html: '🌐', txt: '📄' };
  return icons[fmt] || '📄';
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function extractAudioFromVideo(file: File): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    video.src = URL.createObjectURL(file);
    video.muted = true;
    video.crossOrigin = 'anonymous';

    video.onloadedmetadata = () => {
      const audioContext = new AudioContext();
      const source = audioContext.createMediaElementSource(video);
      const destination = audioContext.createMediaStreamDestination();
      source.connect(destination);
      source.connect(audioContext.destination);
      video.play();

      const mediaRecorder = new MediaRecorder(destination.stream, {
        mimeType: 'audio/webm'
      });
      const chunks: Blob[] = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunks.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        URL.revokeObjectURL(video.src);
        audioContext.close();
        const blob = new Blob(chunks, { type: 'audio/webm' });
        resolve(blob);
      };

      mediaRecorder.onerror = (e) => {
        URL.revokeObjectURL(video.src);
        audioContext.close();
        reject(e);
      };

      video.onended = () => {
        if (mediaRecorder.state !== 'inactive') {
          mediaRecorder.stop();
        }
      };

      setTimeout(() => {
        if (mediaRecorder.state !== 'inactive') {
          mediaRecorder.stop();
        }
      }, video.duration * 1000 + 1000);
    };

    video.onerror = () => {
      reject(new Error('Failed to load video file'));
    };
  });
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files;
  if (files) {
    for (let i = 0; i < files.length; i++) {
      await uploadRefFile(files[i]);
    }
  }
  input.value = '';
}

async function uploadRefFile(file: File) {
  const validationError = validateUploadFile(file);
  if (validationError) {
    alert(validationError);
    return;
  }

  fileUploadProgress.value = 5;
  try {
    const convId = store.currentConvId || undefined;
    const res = await apiClient.uploadFile(file, 'meeting', convId, undefined, (progress) => {
      fileUploadProgress.value = Math.round(progress);
    });
    uploadedRefFiles.value.push({
      filename: res.data.filename,
      file_path: res.data.file_path,
      stored_filename: res.data.stored_filename || res.data.file_path.split(/[/\\]/).pop() || res.data.filename,
      relative_path: res.data.relative_path,
    });
    fileUploadProgress.value = 100;
    setTimeout(() => { fileUploadProgress.value = 0; }, 1000);
  } catch (e) {
    console.error('Upload ref file failed:', e);
    fileUploadProgress.value = 0;
  }
}

async function handleAudioSelect(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) await uploadAudioFile(file);
}

async function uploadAudioFile(file: File) {
  fileUploadProgress.value = 5;
  try {
    const isVideo = file.type.startsWith('video/');
    if (isVideo) {
      store.transcriptText += `检测到视频文件: ${file.name}，后端将自动提取音频...\n`;
    }

    const asrLanguage = language.value === 'bilingual' ? 'zh' : (language.value === 'auto' ? 'zh' : language.value);
    const convId = store.currentConvId || undefined;

    store.clearWorkflow();
    store.addWorkflowStep('上传录音');
    store.addWorkflowStep('ASR 转写');
    store.addWorkflowStep('生成纪要');
    store.updateWorkflowStep(0, 'active');

    try {
      fileUploadProgress.value = 40;
      const asrRes = await apiClient.transcribeAudioSync(file, asrLanguage, 'meeting', convId);
      fileUploadProgress.value = 80;
      const asrData = asrRes.data;
      store.updateWorkflowStep(0, 'completed');
      store.updateWorkflowStep(1, 'completed');

      const audioInfo: AudioFileInfo = {
        filename: asrData.filename || file.name,
        task_id: '',
        stored_filename: asrData.stored_filename || '',
        transcript: asrData.transcript || '',
        file_path: asrData.file_path || '',
        relative_path: asrData.relative_path || '',
      };
      uploadedAudioFiles.value.push(audioInfo);
      fileUploadProgress.value = 100;

      if (asrData.transcript) {
        transcript.value = asrData.transcript;
        store.transcriptText += `转写完成\n`;
      } else {
        store.transcriptText += `未识别到语音内容\n`;
      }
      setTimeout(() => { fileUploadProgress.value = 0; }, 1000);
      return;
    } catch (asrError) {
      console.error('Sync transcription failed, trying upload-audio:', asrError);
    }

    const res = await apiClient.uploadAudio(file, asrLanguage, 'meeting', convId, (progress) => {
      fileUploadProgress.value = Math.round(progress);
    });
    uploadTaskId.value = res.data.task_id;
    uploadedAudioFiles.value.push({
      filename: res.data.filename || file.name,
      task_id: res.data.task_id,
      stored_filename: res.data.stored_filename || '',
      transcript: res.data.transcript || '',
      file_path: res.data.file_path || '',
      relative_path: res.data.relative_path || '',
    });
    uploadProgress.value = 5;
    store.updateWorkflowStep(0, 'completed');

    if (res.data.transcript) {
      transcript.value = res.data.transcript;
      store.transcriptText += '转写完成，点击"生成会议纪要"继续\n';
      fileUploadProgress.value = 100;
      setTimeout(() => { fileUploadProgress.value = 0; }, 1000);
      return;
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    const taskWs = new WebSocket(`${wsProtocol}//${wsHost}/ws/tasks/${uploadTaskId.value}`);

    taskWs.onmessage = (event) => {
      try {
        const task = JSON.parse(event.data);
        if (task.status === 'completed') {
          taskWs.close();
          uploadProgress.value = 100;
          store.updateWorkflowStep(1, 'completed');
          store.updateWorkflowStep(2, 'completed');
          if (task.result) {
            try {
              const result = JSON.parse(task.result);
              store.actorText = result.output || task.result;
              if (result.critic_feedbacks) {
                store.criticText = result.critic_feedbacks.join('\n');
              }
            } catch {
              store.actorText = task.result;
            }
            if (store.actorText && store.actorText.length > 10 && mode.value === 'upload') {
              setTimeout(() => generateMinutes(), 500);
            }
          }
        } else if (task.status === 'failed') {
          taskWs.close();
          uploadProgress.value = 0;
          store.actorText = '处理失败，请重试';
        } else if (task.status === 'processing') {
          uploadProgress.value = Math.max(uploadProgress.value, 50);
          store.updateWorkflowStep(1, 'active');
          if (task.progress) {
            uploadProgress.value = 50 + (task.progress / 100) * 50;
          }
        } else {
          uploadProgress.value = Math.max(uploadProgress.value, 10);
        }
      } catch (e) {
        // ignore parse errors
      }
    };

    taskWs.onerror = () => {
      taskWs.close();
      pollTaskProgress(uploadTaskId.value);
    };

    taskWs.onclose = () => {
      // WebSocket closed
    };

  } catch (e) {
    console.error('Upload failed:', e);
    uploadProgress.value = 0;
    store.actorText = '上传失败，请检查网络连接';
  }
}

function pollTaskProgress(taskId: string) {
  let attempts = 0;
  const maxAttempts = 200;
  const pollInterval = setInterval(async () => {
    attempts++;
    if (attempts > maxAttempts) {
      clearInterval(pollInterval);
      store.actorText = '处理超时，请稍后在任务中心查看结果';
      return;
    }
    try {
      const task = await apiClient.getTask(taskId);
      if (task.data.status === 'completed') {
        clearInterval(pollInterval);
        uploadProgress.value = 100;
        store.updateWorkflowStep(1, 'completed');
        store.updateWorkflowStep(2, 'completed');
        if (task.data.result) {
          try {
            const result = JSON.parse(task.data.result);
            store.actorText = result.output || task.data.result;
          } catch {
            store.actorText = task.data.result;
          }
        }
      } else if (task.data.status === 'failed') {
        clearInterval(pollInterval);
        uploadProgress.value = 0;
        store.actorText = '处理失败，请重试';
      } else if (task.data.status === 'processing') {
        uploadProgress.value = Math.min(90, uploadProgress.value + 5);
        store.updateWorkflowStep(1, 'active');
      }
    } catch (e) {
      clearInterval(pollInterval);
    }
  }, 3000);
}

async function generateMinutes() {
  if (!transcript.value && mode.value === 'text' && uploadedRefFiles.value.length === 0 && uploadedAudioFiles.value.length === 0) return;

  if (store.offlineMode) {
    await store.loadOfflineDemo('meeting_minutes');
    return;
  }

  const audioExts = ['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'wma', 'opus', 'webm', 'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv'];
  const refAudioFiles = uploadedRefFiles.value.filter(f => audioExts.includes(f.filename.split('.').pop()?.toLowerCase() || ''));
  const refDocFiles = uploadedRefFiles.value.filter(f => !audioExts.includes(f.filename.split('.').pop()?.toLowerCase() || ''));
  if (refAudioFiles.length > 0) {
    for (const f of refAudioFiles) {
      uploadedAudioFiles.value.push({
        filename: f.filename,
        task_id: '',
        stored_filename: f.stored_filename,
        file_path: f.file_path,
        relative_path: f.relative_path,
      });
    }
    uploadedRefFiles.value = refDocFiles;
  }

  let audioTranscripts = '';
  if (uploadedAudioFiles.value.length > 0) {
    const parts = uploadedAudioFiles.value
      .filter(f => f.transcript)
      .map(f => f.transcript!);
    if (parts.length > 0) {
      audioTranscripts = parts.join('\n\n');
    }
  }

  const effectiveTranscript = transcript.value || audioTranscripts || '';

  store.currentRefFiles = [
    ...uploadedRefFiles.value.map(f => ({ filename: f.filename, file_path: f.file_path, stored_filename: f.stored_filename, relative_path: f.relative_path, download_url: f.relative_path ? `/api/files/download/${f.relative_path}` : undefined })),
  ];

  const baseMsg = effectiveTranscript || (store.actorText && store.actorText.length > 10 ? store.actorText : '');
  const audioFileNames = uploadedAudioFiles.value.map(f => f.filename).join(', ');
  const refFileNames = uploadedRefFiles.value.map(f => f.filename).join(', ');
  let userMsg = '';
  if (audioFileNames) {
    userMsg = `请根据以下音频文件生成会议纪要：${audioFileNames}`;
  } else if (refFileNames) {
    userMsg = `请根据以下文件生成会议纪要：${refFileNames}`;
  } else if (baseMsg) {
    userMsg = baseMsg;
  } else {
    userMsg = '会议纪要生成';
  }
  store.lastUserMessage = userMsg;

  if (!store.currentConvId || store.currentConvType !== 'meeting') {
    await store.startNewConversation('meeting', userMsg);
  } else {
    await store.saveMessage('user', userMsg);
  }

  store.isProcessing = true;
  store.clearWorkflow();
  store.addWorkflowStep('文本预处理');
  store.addWorkflowStep('Actor 生成纪要');
  store.addWorkflowStep('Critic 审查');
  store.addWorkflowStep('修正与输出');

  const finalTranscript = effectiveTranscript.trim()
    ? effectiveTranscript
    : `请根据以下上传的文件生成会议纪要：\n${uploadedRefFiles.value.map(f => f.filename).join('\n')}`;
  const hasRefFiles = uploadedRefFiles.value.length > 0;
  if (!finalTranscript.trim() && !hasRefFiles && uploadedAudioFiles.value.length === 0) {
    store.actorText = '未检测到会议内容，请先输入文本或上传录音文件进行转写。';
    store.isProcessing = false;
    return;
  }

  if (finalTranscript.trim() && (
    finalTranscript.startsWith('[离线摘要模式]') ||
    finalTranscript.startsWith('[ASR') ||
    finalTranscript.startsWith('语音转写失败') ||
    finalTranscript.startsWith('转写已提交异步任务'))
  ) {
    store.actorText = finalTranscript;
    store.isProcessing = false;
    return;
  }

  try {
    store.updateWorkflowStep(0, 'active');
    const genConvId = store.currentConvId;
    const ctrl = store.createStreamController();
    let generatedFileInfo: any = null;

    if (uploadedAudioFiles.value.length > 0 && !audioTranscripts.trim()) {
      const audioFile = uploadedAudioFiles.value[0];
      if (audioFile.file_path) {
        store.updateWorkflowStep(0, 'completed');
        store.addWorkflowStep('全模态转写');
        store.updateWorkflowStep(store.workflowSteps.length - 1, 'active');

        const formData = new FormData();
        formData.append('file_path', audioFile.file_path);
        formData.append('language', language.value === 'bilingual' ? 'zh' : (language.value === 'auto' ? 'zh' : language.value));
        if (store.currentConvId) formData.append('conv_id', store.currentConvId);
        formData.append('skip_thinking', String(skipThinking.value));
        formData.append('output_format', outputFormat.value);

        let transcriptText = '';
        let _reactIter3 = 1;
        for await (const event of streamUpload('/meeting/audio/stream', formData, ctrl.signal)) {
          if (store.currentConvId !== genConvId) break;
          if (event.type === 'step' && event.message) {
            store.transcriptText += `${event.message}\n`;
          } else if (event.type === 'stream' && event.role === 'transcript') {
            transcriptText += event.content || '';
            store.transcriptText += event.content || '';
          } else if (event.type === 'transcript_done') {
            transcriptText = event.transcript || transcriptText;
            const method = event.method === 'whisper' ? 'Whisper' : '全模态模型';
            store.transcriptText += `\n--- ${method}转写完成 ---\n`;
            store.updateWorkflowStep(store.workflowSteps.length - 1, 'completed');
          } else if (event.type === 'react_start') {
            _reactIter3 = (event as any).iteration || 1;
            store.appendThinkingRound('react', _reactIter3, '');
          } else if (event.type === 'react_thought') {
            store.appendThinkingRound('react', _reactIter3, `🤔 思考: ${(event as any).thought || ''}\n`);
          } else if (event.type === 'tool_call') {
            const args = (event as any).arguments || {};
            const argsStr = Object.entries(args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ');
            store.appendThinkingRound('react', _reactIter3, `🔧 调用工具: ${(event as any).name}(${argsStr})\n`);
          } else if (event.type === 'tool_result') {
            const result = ((event as any).result || '').substring(0, 500);
            store.appendThinkingRound('react', _reactIter3, `📋 工具结果: ${result}${((event as any).result || '').length > 500 ? '...' : ''}\n`);
          } else if (event.type === 'react_done') {
            if ((event as any).steps > 0) {
              store.appendThinkingRound('react', _reactIter3, `✅ ReAct 完成: ${(event as any).steps} 步工具调用\n`);
            }
          } else if (event.type === 'stream' && event.role === 'actor') {
            store.actorText += event.content || '';
            store.appendThinkingRound('actor', event.iteration || 1, event.content || '');
            store.updateWorkflowStep(1, 'completed');
            store.updateWorkflowStep(2, 'active');
          } else if (event.type === 'stream' && event.role === 'critic') {
            store.criticText += event.content || '';
            store.appendThinkingRound('critic', event.iteration || 1, event.content || '');
            if (store.workflowSteps[2]?.status !== 'completed') {
              store.updateWorkflowStep(1, 'completed');
              store.updateWorkflowStep(2, 'active');
            }
          } else if (event.type === 'actor_done' && event.title) {
            store.loadConversations();
          } else if (event.type === 'file_generated' && event.file) {
            const file = event.file;
            generatedFileInfo = {
              filename: file.filename,
              file_path: file.file_path || '',
              stored_filename: file.stored_filename || '',
              relative_path: file.relative_path || '',
              file_format: file.file_format || 'md',
              download_url: file.relative_path ? `/api/files/download/${file.relative_path}` : '',
            };
          } else if (event.type === 'complete') {
            store.updateWorkflowStep(2, 'completed');
            store.updateWorkflowStep(3, 'completed');
            store.isProcessing = false;
            store.finalOutput = event.output || store.actorText;

            const refFilesToSave: any[] = [];
            if (generatedFileInfo) {
              store.addGeneratedFile({
                filename: generatedFileInfo.filename,
                file_name: generatedFileInfo.filename,
                file_path: generatedFileInfo.file_path || '',
                stored_filename: generatedFileInfo.stored_filename || '',
                relative_path: generatedFileInfo.relative_path || '',
                file_format: generatedFileInfo.file_format || 'md',
                file_size: generatedFileInfo.file_size || 0,
                download_url: generatedFileInfo.download_url || '',
                conv_id: store.currentConvId || '',
              });
            }
            for (const af of uploadedAudioFiles.value) {
              refFilesToSave.push({
                filename: af.filename,
                file_path: af.file_path || af.filename,
                stored_filename: af.stored_filename || af.filename,
                relative_path: af.relative_path || '',
                download_url: af.relative_path ? `/api/files/download/${af.relative_path}` : '',
                conv_id: store.currentConvId || '',
              });
            }
            if (store.currentRefFiles.length > 0) {
              refFilesToSave.push(...store.currentRefFiles);
            }

            store.saveMessage('actor', store.finalOutput).then(() => {
              store.saveMessage('critic', store.criticText);
            }).then(() => {
              if (refFilesToSave.length > 0) {
                store.saveFilesMessage(refFilesToSave);
              }
            }).then(() => {
              store.loadConversations();
            }).catch((e: any) => console.error('Save failed:', e));
          } else if (event.type === 'error') {
            store.workflowSteps.forEach((_: any, i: number) => {
              store.updateWorkflowStep(i, 'completed');
            });
            store.isProcessing = false;
            store.finalOutput = event.message || '会议纪要生成过程中发生错误';
            await store.saveMessage('actor', store.finalOutput);
            await store.loadConversations();
          }
        }

        store.isProcessing = false;
        transcript.value = '';
        uploadedRefFiles.value = [];
        uploadedAudioFiles.value = [];
        return;
      }
    }

    let _reactIter4 = 1;
    for await (const event of streamPost('/meeting/minutes/stream', {
      transcript: finalTranscript + (uploadedRefFiles.value.length > 0 ? '\n\n[参考文件]\n' + uploadedRefFiles.value.map(f => `文件: ${f.filename} (路径: ${f.file_path})`).join('\n') : ''),
      language: language.value,
      ref_files: uploadedRefFiles.value.map(f => ({ filename: f.filename, file_path: f.file_path })),
      skip_thinking: skipThinking.value,
      conv_id: store.currentConvId,
      output_format: outputFormat.value,
    }, ctrl.signal)) {
      if (store.currentConvId !== genConvId) break;
      if (event.type === 'step' && event.message) {
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
        _reactIter4 = (event as any).iteration || 1;
        store.appendThinkingRound('react', _reactIter4, '');
      } else if (event.type === 'react_thought') {
        store.appendThinkingRound('react', _reactIter4, `🤔 思考: ${(event as any).thought || ''}\n`);
      } else if (event.type === 'tool_call') {
        const args = (event as any).arguments || {};
        const argsStr = Object.entries(args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ');
        store.appendThinkingRound('react', _reactIter4, `🔧 调用工具: ${(event as any).name}(${argsStr})\n`);
      } else if (event.type === 'tool_result') {
        const result = ((event as any).result || '').substring(0, 500);
        store.appendThinkingRound('react', _reactIter4, `📋 工具结果: ${result}${((event as any).result || '').length > 500 ? '...' : ''}\n`);
      } else if (event.type === 'react_done') {
        if ((event as any).steps > 0) {
          store.appendThinkingRound('react', _reactIter4, `✅ ReAct 完成: ${(event as any).steps} 步工具调用\n`);
        }
      } else if (event.type === 'stream' && event.role === 'actor') {
        store.actorText += event.content || '';
        store.appendThinkingRound('actor', event.iteration || 1, event.content || '');
        store.updateWorkflowStep(0, 'completed');
        store.updateWorkflowStep(1, 'active');
      } else if (event.type === 'stream' && event.role === 'critic') {
        store.criticText += event.content || '';
        store.appendThinkingRound('critic', event.iteration || 1, event.content || '');
        if (store.workflowSteps[2]?.status !== 'completed') {
          store.updateWorkflowStep(1, 'completed');
          store.updateWorkflowStep(2, 'active');
        }
      } else if (event.type === 'actor_done' && event.title) {
        store.loadConversations();
      } else if (event.type === 'file_generated' && event.file) {
        const file = event.file;
        const downloadUrl = file.relative_path
          ? `/api/files/download/${file.relative_path}`
          : `/api/meeting/download/${file.stored_filename || file.filename}`;
        generatedFileInfo = {
          filename: file.filename,
          file_path: file.file_path || '',
          stored_filename: file.stored_filename || '',
          relative_path: file.relative_path || '',
          file_format: file.file_format || 'md',
          download_url: downloadUrl,
        };
      } else if (event.type === 'complete') {
        store.updateWorkflowStep(2, 'completed');
        store.updateWorkflowStep(3, 'completed');
        store.isProcessing = false;
        store.finalOutput = event.output || store.actorText;

        const refFilesToSave: any[] = [];
        if (generatedFileInfo) {
          store.addGeneratedFile({
            filename: generatedFileInfo.filename,
            file_name: generatedFileInfo.filename,
            file_path: generatedFileInfo.file_path || '',
            stored_filename: generatedFileInfo.stored_filename || '',
            relative_path: generatedFileInfo.relative_path || '',
            file_format: generatedFileInfo.file_format || 'md',
            file_size: generatedFileInfo.file_size || 0,
            download_url: generatedFileInfo.download_url || '',
            conv_id: store.currentConvId || '',
          });
        }
        if (store.currentRefFiles.length > 0) {
          refFilesToSave.push(...store.currentRefFiles);
        }
        for (const af of uploadedAudioFiles.value) {
          refFilesToSave.push({
            filename: af.filename,
            file_path: af.file_path || af.filename,
            stored_filename: af.stored_filename || af.filename,
            relative_path: af.relative_path || '',
            download_url: af.relative_path ? `/api/files/download/${af.relative_path}` : '',
            conv_id: store.currentConvId || '',
          });
        }

        store.saveMessage('actor', store.finalOutput).then(() => {
          store.saveMessage('critic', store.criticText);
        }).then(() => {
          if (refFilesToSave.length > 0) {
            store.saveFilesMessage(refFilesToSave);
          }
        }).then(() => {
          store.loadConversations();
        }).catch((e: any) => console.error('Save failed:', e));
      } else if (event.type === 'error') {
        store.workflowSteps.forEach((_: any, i: number) => {
          store.updateWorkflowStep(i, 'completed');
        });
        store.isProcessing = false;
        store.finalOutput = event.message || '会议纪要生成过程中发生错误';
        await store.saveMessage('actor', store.finalOutput);
        await store.loadConversations();
      }
    }
  } catch (e) {
    console.error('Generate minutes failed:', e);
    const errMsg = e instanceof Error ? e.message : '会议纪要生成失败';
    store.finalOutput = errMsg;
    await store.saveMessage('actor', errMsg);
    await store.loadConversations();
  } finally {
    store.isProcessing = false;
    transcript.value = '';
    uploadedRefFiles.value = [];
    uploadedAudioFiles.value = [];
  }
}

watch(() => store.droppedFileInfo, (info) => {
  if (info) {
    const audioExts = ['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'wma', 'opus', 'webm', 'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv'];
    const ext = info.filename.split('.').pop()?.toLowerCase() || '';
    if (audioExts.includes(ext)) {
      uploadedAudioFiles.value.push({
        filename: info.filename,
        task_id: '',
        stored_filename: info.file_path.split(/[/\\]/).pop() || info.filename,
        file_path: info.file_path,
        relative_path: info.relative_path,
      });
    } else {
      uploadedRefFiles.value.push({
        filename: info.filename,
        file_path: info.file_path,
        stored_filename: info.file_path.split(/[/\\]/).pop() || info.filename,
        relative_path: info.relative_path,
      });
    }
    store.droppedFileInfo = null;
  }
});
</script>
