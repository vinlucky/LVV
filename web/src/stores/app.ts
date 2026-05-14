import { defineStore } from 'pinia';
import { ref } from 'vue';
import { apiClient } from '../utils/api';
import type { GeneratedFile, MaterialTemplate } from '../utils/api';

export interface Conversation {
  conv_id: string;
  task_type: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: any[];
}

export interface ConversationMessage {
  role: string;
  content: string;
  timestamp?: string;
}

export interface ConversationRound {
  userMessage: string;
  actorText: string;
  criticText: string;
  finalOutput: string;
  timestamp: string;
  refFiles?: { filename: string; file_path: string; stored_filename?: string; download_url?: string; relative_path?: string }[];
  generatedFiles?: GeneratedFile[];
  transcriptText?: string;
  thinkingRounds?: ThinkingRound[];
}

export interface ThinkingRound {
  iteration: number;
  reactText: string;
  actorText: string;
  criticText: string;
}

export interface ThinkingHistoryEntry {
  conv_id: string;
  actorText: string;
  criticText: string;
  timestamp: string;
  thinkingRounds: ThinkingRound[];
}

export interface ConversationStreamState {
  convId: string;
  actorText: string;
  criticText: string;
  finalOutput: string;
  lastUserMessage: string;
  isProcessing: boolean;
  workflowSteps: { name: string; status: 'pending' | 'active' | 'completed' | 'failed' }[];
  conversationRounds: ConversationRound[];
  thinkingHistory: ThinkingHistoryEntry[];
  thinkingRounds: ThinkingRound[];
}

export const useAppStore = defineStore('app', () => {
  const currentProvider = ref('qwen');
  const offlineMode = ref(false);

  const initialized = ref<boolean | null>(null);
  const backendOnline = ref(true);

  const conversations = ref<Conversation[]>([]);
  const currentConvId = ref<string | null>(null);
  const currentConvType = ref<string>('chat');

  const streamStates = ref<Map<string, ConversationStreamState>>(new Map());

  const generatedFiles = ref<GeneratedFile[]>([]);
  const materialTemplates = ref<MaterialTemplate[]>([]);
  const droppedFileInfo = ref<{ filename: string; file_path: string; stored_filename?: string; download_url?: string; relative_path?: string } | null>(null);
  const currentRefFiles = ref<{ filename: string; file_path: string; stored_filename?: string; download_url?: string; relative_path?: string }[]>([]);
  const currentStreamController = ref<AbortController | null>(null);

  const progress = ref(0);

  function cancelCurrentStream() {
    if (currentStreamController.value) {
      currentStreamController.value.abort();
      currentStreamController.value = null;
    }
  }

  function createStreamController(): AbortController {
    cancelCurrentStream();
    currentStreamController.value = new AbortController();
    return currentStreamController.value;
  }

  function getStreamState(convId: string): ConversationStreamState {
    if (!streamStates.value.has(convId)) {
      streamStates.value.set(convId, {
        convId,
        actorText: '',
        criticText: '',
        finalOutput: '',
        lastUserMessage: '',
        isProcessing: false,
        workflowSteps: [],
        conversationRounds: [],
        thinkingHistory: [],
        thinkingRounds: [],
      });
    }
    return streamStates.value.get(convId)!;
  }

  const actorText = ref('');
  const criticText = ref('');
  const finalOutput = ref('');
  const lastUserMessage = ref('');
  const transcriptText = ref('');
  const reactText = ref('');
  const isProcessing = ref(false);
  const workflowSteps = ref<{ name: string; status: 'pending' | 'active' | 'completed' | 'failed' }[]>([]);
  const thinkingHistory = ref<ThinkingHistoryEntry[]>([]);
  const conversationRounds = ref<ConversationRound[]>([]);
  const thinkingRounds = ref<ThinkingRound[]>([]);

  function _syncFromStreamState(convId: string) {
    const state = getStreamState(convId);
    actorText.value = state.actorText;
    criticText.value = state.criticText;
    finalOutput.value = state.finalOutput;
    lastUserMessage.value = state.lastUserMessage;
    isProcessing.value = state.isProcessing;
    workflowSteps.value = [...state.workflowSteps];
    conversationRounds.value = [...state.conversationRounds];
    thinkingHistory.value = [...state.thinkingHistory];
    thinkingRounds.value = [...state.thinkingRounds];
  }

  function _syncToStreamState(convId: string) {
    if (!convId) return;
    const state = getStreamState(convId);
    state.actorText = actorText.value;
    state.criticText = criticText.value;
    state.finalOutput = finalOutput.value;
    state.lastUserMessage = lastUserMessage.value;
    state.isProcessing = isProcessing.value;
    state.workflowSteps = [...workflowSteps.value];
    state.conversationRounds = [...conversationRounds.value];
    state.thinkingHistory = [...thinkingHistory.value];
    state.thinkingRounds = [...thinkingRounds.value];
  }

  function commitStreamState() {
    if (currentConvId.value && (actorText.value || criticText.value || finalOutput.value)) {
      if (transcriptText.value) {
        saveMessage('transcript', transcriptText.value);
      }
      if (thinkingRounds.value.length > 0) {
        saveMessage('thinking_rounds', JSON.stringify(thinkingRounds.value));
      }
      thinkingHistory.value.push({
        conv_id: currentConvId.value,
        actorText: actorText.value,
        criticText: criticText.value,
        timestamp: new Date().toISOString(),
        thinkingRounds: [...thinkingRounds.value],
      });
      if (lastUserMessage.value || finalOutput.value) {
        const roundFiles = generatedFiles.value.filter(f => f.conv_id === currentConvId.value);
        conversationRounds.value.push({
          userMessage: lastUserMessage.value,
          actorText: actorText.value,
          criticText: criticText.value,
          finalOutput: finalOutput.value || actorText.value,
          timestamp: new Date().toISOString(),
          refFiles: currentRefFiles.value.length > 0 ? [...currentRefFiles.value] : undefined,
          generatedFiles: roundFiles.length > 0 ? [...roundFiles] : undefined,
          transcriptText: transcriptText.value || undefined,
          thinkingRounds: thinkingRounds.value.length > 0 ? [...thinkingRounds.value] : undefined,
        });
      }
      _syncToStreamState(currentConvId.value);
    }
    actorText.value = '';
    criticText.value = '';
    finalOutput.value = '';
    lastUserMessage.value = '';
    currentRefFiles.value = [];
    thinkingRounds.value = [];
    transcriptText.value = '';
    reactText.value = '';
  }

  function resetStream() {
    cancelCurrentStream();
    commitStreamState();
  }

  function appendThinkingRound(role: 'actor' | 'critic' | 'react', iteration: number, content: string) {
    const idx = thinkingRounds.value.findIndex(r => r.iteration === iteration);
    if (idx >= 0) {
      if (role === 'react') {
        thinkingRounds.value[idx].reactText += content;
        reactText.value += content;
      } else if (role === 'actor') {
        thinkingRounds.value[idx].actorText += content;
      } else {
        thinkingRounds.value[idx].criticText += content;
      }
    } else {
      const round: ThinkingRound = {
        iteration,
        reactText: role === 'react' ? content : '',
        actorText: role === 'actor' ? content : '',
        criticText: role === 'critic' ? content : '',
      };
      thinkingRounds.value.push(round);
      if (role === 'react') {
        reactText.value += content;
      }
    }
    if (currentConvId.value) _syncToStreamState(currentConvId.value);
  }

  function addWorkflowStep(name: string) {
    workflowSteps.value.push({ name, status: 'pending' });
    if (currentConvId.value) _syncToStreamState(currentConvId.value);
  }

  function updateWorkflowStep(index: number, status: 'pending' | 'active' | 'completed' | 'failed') {
    if (workflowSteps.value[index]) {
      workflowSteps.value[index].status = status;
      if (currentConvId.value) _syncToStreamState(currentConvId.value);
    }
  }

  function clearWorkflow() {
    workflowSteps.value = [];
    if (currentConvId.value) _syncToStreamState(currentConvId.value);
  }

  function getThinkingHistory(convId: string): ThinkingHistoryEntry[] {
    const state = streamStates.value.get(convId);
    if (state) return state.thinkingHistory;
    return thinkingHistory.value.filter((e) => e.conv_id === convId);
  }

  function isConvProcessing(convId: string): boolean {
    const state = streamStates.value.get(convId);
    return state?.isProcessing || false;
  }

  async function loadConversations(taskType?: string) {
    if (offlineMode.value) return;
    try {
      const res = await apiClient.listConversations(50, 0, taskType);
      conversations.value = res.data.conversations || [];
    } catch (e) {
      // ignore
    }
  }

  async function startNewConversation(taskType: string, initialMessage?: string) {
    const prevConvId = currentConvId.value;
    const prevActorText = actorText.value;
    const prevCriticText = criticText.value;
    const prevFinalOutput = finalOutput.value;
    const prevLastUserMessage = lastUserMessage.value;
    const prevThinkingRounds = [...thinkingRounds.value];
    const prevTranscriptText = transcriptText.value;

    if (offlineMode.value) {
      currentConvId.value = `offline_${Date.now()}`;
      currentConvType.value = taskType;
      resetStream();
      clearWorkflow();
      conversationRounds.value = [];
      thinkingHistory.value = [];
      return currentConvId.value;
    }
    try {
      const res = await apiClient.createConversation(taskType, initialMessage);
      currentConvId.value = res.data.conv_id;
      currentConvType.value = taskType;

      if (prevConvId && (prevActorText || prevCriticText)) {
        if (prevTranscriptText) {
          saveMessage('transcript', prevTranscriptText);
        }
        if (prevThinkingRounds.length > 0) {
          saveMessage('thinking_rounds', JSON.stringify(prevThinkingRounds));
        }
        thinkingHistory.value.push({
          conv_id: prevConvId,
          actorText: prevActorText,
          criticText: prevCriticText,
          timestamp: new Date().toISOString(),
          thinkingRounds: prevThinkingRounds,
        });
        if (prevLastUserMessage || prevFinalOutput) {
          conversationRounds.value.push({
            userMessage: prevLastUserMessage,
            actorText: prevActorText,
            criticText: prevCriticText,
            finalOutput: prevFinalOutput || prevActorText,
            timestamp: new Date().toISOString(),
            transcriptText: prevTranscriptText || undefined,
            thinkingRounds: prevThinkingRounds.length > 0 ? prevThinkingRounds : undefined,
          });
        }
        _syncToStreamState(prevConvId);
      }

      resetStream();
      clearWorkflow();
      conversationRounds.value = [];
      thinkingHistory.value = [];
      thinkingRounds.value = [];
      if (currentConvId.value) _syncToStreamState(currentConvId.value);
      await loadConversations();
      return res.data.conv_id;
    } catch (e) {
      console.error('Failed to create conversation:', e);
      return null;
    }
  }

  async function switchConversation(convId: string): Promise<string | null> {
    if (offlineMode.value) return null;

    if (currentConvId.value) {
      _syncToStreamState(currentConvId.value);
    }

    try {
      const res = await apiClient.getConversation(convId);
      const conv = res.data;
      currentConvId.value = conv.conv_id;
      currentConvType.value = conv.task_type;
      const messages = conv.messages || [];
      const rounds: ConversationRound[] = [];
      let pendingUser = '';
      let pendingActor = '';
      let pendingCritic = '';
      let pendingFiles: { filename: string; file_path: string; stored_filename?: string; download_url?: string; relative_path?: string }[] | undefined;
      let pendingGeneratedFiles: GeneratedFile[] | undefined;
      let pendingTranscript = '';
      let pendingThinkingRounds: ThinkingRound[] = [];
      for (const msg of messages) {
        if (msg.role === 'user') {
          if (pendingUser && (pendingActor || pendingCritic)) {
            rounds.push({
              userMessage: pendingUser,
              actorText: pendingActor,
              criticText: pendingCritic,
              finalOutput: pendingActor,
              timestamp: msg.timestamp || new Date().toISOString(),
              refFiles: pendingFiles,
              generatedFiles: pendingGeneratedFiles,
              transcriptText: pendingTranscript || undefined,
              thinkingRounds: pendingThinkingRounds.length > 0 ? pendingThinkingRounds : undefined,
            });
          }
          pendingUser = msg.content;
          pendingActor = '';
          pendingCritic = '';
          pendingFiles = undefined;
          pendingGeneratedFiles = undefined;
          pendingTranscript = '';
          pendingThinkingRounds = [];
        } else if (msg.role === 'actor') {
          pendingActor = msg.content;
        } else if (msg.role === 'critic') {
          pendingCritic = msg.content;
        } else if (msg.role === 'files') {
          try {
            pendingFiles = JSON.parse(msg.content);
          } catch {
            pendingFiles = undefined;
          }
        } else if (msg.role === 'generated_files') {
          try {
            const parsed = JSON.parse(msg.content);
            if (Array.isArray(parsed)) {
              if (!pendingGeneratedFiles) {
                pendingGeneratedFiles = parsed;
              } else {
                for (const f of parsed) {
                  const existingIdx = pendingGeneratedFiles.findIndex((ef: any) => ef.filename === f.filename);
                  if (existingIdx < 0) {
                    pendingGeneratedFiles.push(f);
                  } else if (f.relative_path && !pendingGeneratedFiles[existingIdx].relative_path) {
                    pendingGeneratedFiles[existingIdx] = f;
                  }
                }
              }
            }
          } catch {
            pendingGeneratedFiles = undefined;
          }
        } else if (msg.role === 'transcript') {
          pendingTranscript = msg.content;
        } else if (msg.role === 'thinking_rounds') {
          try {
            pendingThinkingRounds = JSON.parse(msg.content);
            if (!Array.isArray(pendingThinkingRounds)) pendingThinkingRounds = [];
          } catch {
            pendingThinkingRounds = [];
          }
        }
      }
      if (pendingUser && (pendingActor || pendingCritic)) {
        rounds.push({
          userMessage: pendingUser,
          actorText: pendingActor,
          criticText: pendingCritic,
          finalOutput: pendingActor,
          timestamp: new Date().toISOString(),
          refFiles: pendingFiles,
          generatedFiles: pendingGeneratedFiles,
          transcriptText: pendingTranscript || undefined,
          thinkingRounds: pendingThinkingRounds.length > 0 ? pendingThinkingRounds : undefined,
        });
      }

      const existingState = streamStates.value.get(convId);
      if (existingState) {
        conversationRounds.value = [...existingState.conversationRounds];
        thinkingHistory.value = [...existingState.thinkingHistory];
        thinkingRounds.value = [...existingState.thinkingRounds];
        actorText.value = existingState.actorText;
        criticText.value = existingState.criticText;
        finalOutput.value = existingState.finalOutput;
        lastUserMessage.value = existingState.lastUserMessage;
        isProcessing.value = existingState.isProcessing;
        workflowSteps.value = [...existingState.workflowSteps];
      } else {
        conversationRounds.value = rounds;
        thinkingHistory.value = rounds.map((r, i) => ({
          conv_id: convId,
          actorText: r.actorText,
          criticText: r.criticText,
          timestamp: r.timestamp,
          thinkingRounds: r.thinkingRounds || [],
        }));
        thinkingRounds.value = [];
        actorText.value = '';
        criticText.value = '';
        finalOutput.value = '';
        lastUserMessage.value = '';
        isProcessing.value = false;
        workflowSteps.value = [];
      }

      const allRoundFiles: GeneratedFile[] = [];
      for (const round of rounds) {
        if (round.generatedFiles) {
          for (const gf of round.generatedFiles) {
            if (!gf.conv_id) gf.conv_id = convId;
            allRoundFiles.push(gf);
          }
        }
      }
      generatedFiles.value = allRoundFiles;

      clearWorkflow();
      return conv.task_type;
    } catch (e) {
      console.error('Failed to switch conversation:', e);
      return null;
    }
  }

  async function deleteConversation(convId: string) {
    if (offlineMode.value) return;
    try {
      await apiClient.deleteConversation(convId);
      streamStates.value.delete(convId);
      if (currentConvId.value === convId) {
        currentConvId.value = null;
        resetStream();
        clearWorkflow();
      }
      thinkingHistory.value = thinkingHistory.value.filter((e) => e.conv_id !== convId);
      await loadConversations();
    } catch (e) {
      console.error('Failed to delete conversation:', e);
    }
  }

  async function saveMessage(role: string, content: string) {
    if (offlineMode.value || !currentConvId.value) return;
    try {
      await apiClient.addMessage(currentConvId.value, role, content);
    } catch (e) {
      // ignore
    }
  }

  async function saveFilesMessage(files: { filename: string; file_path: string; stored_filename?: string; download_url?: string }[]) {
    if (offlineMode.value || !currentConvId.value || files.length === 0) return;
    try {
      const updatedRes = await apiClient.updateFilesConvId(files, currentConvId.value);
      const updatedFiles = updatedRes.data.files || files;
      await apiClient.addMessage(currentConvId.value, 'files', JSON.stringify(updatedFiles));
    } catch (e) {
      try {
        await apiClient.addMessage(currentConvId.value, 'files', JSON.stringify(files));
      } catch (e2) {
        // ignore
      }
    }
  }

  async function rollbackConversation(messageIndex?: number) {
    if (!currentConvId.value) return;
    try {
      const res = await apiClient.getConversation(currentConvId.value);
      const conv = res.data;
      let messages = conv.messages || [];

      if (messageIndex !== undefined) {
        messages = messages.slice(0, messageIndex);
      } else {
        while (messages.length > 0 && messages[messages.length - 1].role !== 'user') {
          messages.pop();
        }
        if (messages.length > 0) {
          messages.pop();
        }
      }

      const newConv = await apiClient.createConversation(conv.task_type);
      const newConvId = newConv.data.conv_id;

      for (const msg of messages) {
        await apiClient.addMessage(newConvId, msg.role, msg.content);
      }

      await apiClient.deleteConversation(currentConvId.value);

      streamStates.value.delete(currentConvId.value);
      currentConvId.value = newConvId;
      currentConvType.value = conv.task_type;

      const rounds: ConversationRound[] = [];
      let pendingUser = '';
      let pendingActor = '';
      let pendingCritic = '';
      let pendingTranscript = '';
      let pendingThinkingRounds: ThinkingRound[] = [];
      for (const msg of messages) {
        if (msg.role === 'user') {
          if (pendingUser && (pendingActor || pendingCritic)) {
            rounds.push({
              userMessage: pendingUser,
              actorText: pendingActor,
              criticText: pendingCritic,
              finalOutput: pendingActor,
              timestamp: new Date().toISOString(),
              transcriptText: pendingTranscript || undefined,
              thinkingRounds: pendingThinkingRounds.length > 0 ? pendingThinkingRounds : undefined,
            });
          }
          pendingUser = msg.content;
          pendingActor = '';
          pendingCritic = '';
          pendingTranscript = '';
          pendingThinkingRounds = [];
        } else if (msg.role === 'actor') {
          pendingActor = msg.content;
        } else if (msg.role === 'critic') {
          pendingCritic = msg.content;
        } else if (msg.role === 'transcript') {
          pendingTranscript = msg.content;
        } else if (msg.role === 'thinking_rounds') {
          try {
            pendingThinkingRounds = JSON.parse(msg.content);
            if (!Array.isArray(pendingThinkingRounds)) pendingThinkingRounds = [];
          } catch {
            pendingThinkingRounds = [];
          }
        }
      }
      if (pendingUser && (pendingActor || pendingCritic)) {
        rounds.push({
          userMessage: pendingUser,
          actorText: pendingActor,
          criticText: pendingCritic,
          finalOutput: pendingActor,
          timestamp: new Date().toISOString(),
          transcriptText: pendingTranscript || undefined,
          thinkingRounds: pendingThinkingRounds.length > 0 ? pendingThinkingRounds : undefined,
        });
      }

      conversationRounds.value = rounds;
      const lastActor = messages.filter((m: any) => m.role === 'actor').pop();
      const lastCritic = messages.filter((m: any) => m.role === 'critic').pop();
      actorText.value = lastActor?.content || '';
      criticText.value = lastCritic?.content || '';
      finalOutput.value = lastActor?.content || '';
      lastUserMessage.value = '';
      isProcessing.value = false;
      clearWorkflow();
      _syncToStreamState(newConvId);
      await loadConversations();
    } catch (e) {
      console.error('Failed to rollback conversation:', e);
    }
  }

  async function regenerateLastResponse() {
    if (!currentConvId.value) return;
    try {
      const res = await apiClient.getConversation(currentConvId.value);
      const conv = res.data;
      const messages = conv.messages || [];

      let lastUserMessage = '';
      let lastUserIndex = -1;
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === 'user') {
          lastUserMessage = messages[i].content;
          lastUserIndex = i;
          break;
        }
      }

      if (!lastUserMessage) return;

      const preservedMessages = messages.slice(0, lastUserIndex);

      const newConv = await apiClient.createConversation(conv.task_type);
      const newConvId = newConv.data.conv_id;

      for (const msg of preservedMessages) {
        await apiClient.addMessage(newConvId, msg.role, msg.content);
      }

      await apiClient.addMessage(newConvId, 'user', lastUserMessage);

      await apiClient.deleteConversation(currentConvId.value);

      streamStates.value.delete(currentConvId.value);
      currentConvId.value = newConvId;
      currentConvType.value = conv.task_type;

      return lastUserMessage;
    } catch (e) {
      console.error('Failed to regenerate:', e);
      return null;
    }
  }

  let _healthPollInterval: number | null = null;
  let _lastBackendOnline = true;
  let _consecutiveFailures = 0;

  function startHealthPolling() {
    stopHealthPolling();
    _healthPollInterval = window.setInterval(async () => {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);
        const healthRes = await fetch('/api/health', { signal: controller.signal });
        clearTimeout(timeoutId);
        const health = await healthRes.json();
        _consecutiveFailures = 0;
        const wasOnline = backendOnline.value;
        backendOnline.value = true;

        if (health && health.all_offline) {
          initialized.value = false;
        } else if (!wasOnline) {
          initialized.value = true;
          console.log('✅ 后端服务已恢复！');
        } else {
          try {
            const res = await apiClient.getProviders();
            const providers: string[] = res.data.providers || [];
            const realProviders = providers.filter((p) => p !== 'mock');
            initialized.value = realProviders.length > 0;
          } catch (e) {
            initialized.value = true;
          }
        }
      } catch (e) {
        _consecutiveFailures++;
        if (_consecutiveFailures >= 3) {
          const wasOnline = backendOnline.value;
          backendOnline.value = false;
          if (wasOnline) {
            console.warn('⚠️ 后端服务已断开，系统将在恢复后自动重连...');
          }
          _lastBackendOnline = false;
        }
      }
    }, 20000);
  }

  function stopHealthPolling() {
    if (_healthPollInterval !== null) {
      clearInterval(_healthPollInterval);
      _healthPollInterval = null;
    }
  }

  async function checkInitStatus() {
    try {
      const healthRes = await apiClient.health();
      const health = healthRes.data;
      backendOnline.value = true;
      
      if (health && health.all_offline) {
        initialized.value = false;
        return;
      }
      
      try {
        const res = await apiClient.getProviders();
        const providers: string[] = res.data.providers || [];
        const realProviders = providers.filter((p) => p !== 'mock');
        initialized.value = realProviders.length > 0;
      } catch (e) {
        initialized.value = true;
      }
    } catch (e) {
      backendOnline.value = false;
      initialized.value = false;
    }
  }

  async function loadOfflineDemo(taskType: string) {
    if (!offlineMode.value) return false;

    isProcessing.value = true;
    resetStream();
    clearWorkflow();

    addWorkflowStep('加载离线演示数据');
    updateWorkflowStep(0, 'active');

    try {
      const res = await apiClient.getOfflineDemo(taskType);
      const data = res.data;

      updateWorkflowStep(0, 'completed');

      const output = data.output || '';
      const feedbacks = data.critic_feedbacks || [];

      for (let i = 0; i < output.length; i += 5) {
        actorText.value += output.slice(i, i + 5);
        await new Promise(r => setTimeout(r, 20));
      }

      if (feedbacks.length > 0 && feedbacks[0] !== '通过') {
        criticText.value = feedbacks.join('\n');
      }

      isProcessing.value = false;
      return true;
    } catch (e) {
      console.error('Failed to load offline demo:', e);
      isProcessing.value = false;
      return false;
    }
  }

  function addGeneratedFile(file: GeneratedFile, persist: boolean = true) {
    const existing = generatedFiles.value.findIndex(f => f.filename === file.filename && f.conv_id === file.conv_id);
    if (existing >= 0) {
      generatedFiles.value[existing] = file;
    } else {
      generatedFiles.value.unshift(file);
    }
    if (persist && currentConvId.value && !offlineMode.value) {
      const convFiles = generatedFiles.value.filter(f => f.conv_id === currentConvId.value);
      apiClient.addMessage(currentConvId.value, 'generated_files', JSON.stringify(convFiles)).catch(() => {});
    }
  }

  function clearGeneratedFiles() {
    generatedFiles.value = [];
  }

  async function loadMaterialTemplates() {
    try {
      const res = await apiClient.getMaterialTemplates();
      materialTemplates.value = res.data.templates || [];
    } catch (e) {
      console.error('Failed to load material templates:', e);
    }
  }

  async function loadGeneratedFiles() {
    try {
      const res = await apiClient.getChatFiles();
      generatedFiles.value = res.data.files || [];
    } catch (e) {
      console.error('Failed to load generated files:', e);
    }
  }

  async function generateFileFromContent(content: string, format: string = 'md', fileName: string = '内容', mode?: string) {
    try {
      const res = await apiClient.generateFile(content, format, fileName, currentConvId.value || undefined, mode || currentConvType.value || 'chat');
      const fileInfo = res.data;
      addGeneratedFile(fileInfo);
      return fileInfo;
    } catch (e) {
      console.error('Failed to generate file:', e);
      return null;
    }
  }

  return {
    currentProvider,
    actorText,
    criticText,
    finalOutput,
    lastUserMessage,
    transcriptText,
    reactText,
    workflowSteps,
    isProcessing,
    progress,
    offlineMode,
    initialized,
    backendOnline,
    conversations,
    currentConvId,
    currentConvType,
    thinkingHistory,
    conversationRounds,
    thinkingRounds,
    generatedFiles,
    materialTemplates,
    droppedFileInfo,
    currentRefFiles,
    streamStates,
    resetStream,
    commitStreamState,
    addWorkflowStep,
    updateWorkflowStep,
    clearWorkflow,
    getThinkingHistory,
    isConvProcessing,
    appendThinkingRound,
    loadConversations,
    startNewConversation,
    switchConversation,
    deleteConversation,
    saveMessage,
    saveFilesMessage,
    cancelCurrentStream,
    createStreamController,
    rollbackConversation,
    regenerateLastResponse,
    checkInitStatus,
    startHealthPolling,
    stopHealthPolling,
    loadOfflineDemo,
    addGeneratedFile,
    clearGeneratedFiles,
    loadMaterialTemplates,
    loadGeneratedFiles,
    generateFileFromContent,
  };
});
