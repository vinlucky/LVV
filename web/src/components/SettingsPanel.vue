<template>
  <div v-if="visible" class="fixed inset-0 bg-black/30 z-50 flex items-center justify-center" @click.self="$emit('close')">
    <div class="bg-white rounded-xl shadow-2xl w-[560px] max-h-[85vh] overflow-y-auto">
      <div class="p-4 border-b flex items-center justify-between">
        <h3 class="text-sm font-semibold text-gray-700">⚙️ 高级设置</h3>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
      </div>

      <div class="p-4 space-y-4">
        <div v-if="healthStatus?.all_offline" class="p-3 bg-red-50 rounded-lg border border-red-200">
          <div class="text-xs font-semibold text-red-700 mb-1">⚠️ 所有AI模型均不可用</div>
          <div class="text-[10px] text-red-600 space-y-1">
            <div>没有配置任何API Key，所有AI功能无法使用。</div>
            <div class="font-medium mt-1">可选方案：</div>
            <div>1. 配置 API Key（推荐）：在上方选择提供方并输入 Key</div>
            <div>2. 使用本地备用库（无需 API Key，功能有限，已随依赖安装）</div>
          </div>
        </div>

        <div v-if="discoveryResult?.missing_categories?.length" class="p-2 bg-amber-50 rounded-lg border border-amber-200">
          <div class="text-xs font-semibold text-amber-700 mb-1">⚠️ 部分模型分类不可用</div>
          <div v-for="s in discoveryResult.category_suggestions" :key="s.category" class="text-[10px] text-amber-600 space-y-1 mb-1">
            <div class="font-medium">{{ s.icon }} {{ s.category_name }}：不可用</div>
            <div>影响功能：{{ s.skills_affected }}</div>
            <div v-if="s.official_url">
              👉 前往官网获取：<a :href="s.official_url" target="_blank" class="text-blue-500 underline">{{ s.official_url }}</a>
            </div>
            <div v-if="s.local_alternative">
              🔧 本地替代：{{ s.local_alternative }}
            </div>
            <div v-if="s.local_libraries">
              <div v-for="(lib, lkey) in s.local_libraries" :key="lkey" class="ml-2">
                • {{ lib.name }}: <code class="bg-amber-100 px-1 rounded">{{ lib.install }}</code>
              </div>
            </div>
          </div>
        </div>

        <div v-if="discoveryResult?.has_llm_only" class="p-2 bg-blue-50 rounded-lg border border-blue-200">
          <div class="text-xs font-semibold text-blue-700 mb-1">ℹ️ 仅有大语言模型</div>
          <div class="text-[10px] text-blue-600 space-y-1">
            <div>当前提供商只有大语言模型，缺少多模态和向量模型。</div>
            <div class="font-medium mt-1">本地备用库已随依赖安装，API不可用时自动启用：</div>
            <div>• 语音转文字 → whisper</div>
            <div>• OCR文字识别 → PaddleOCR</div>
            <div>• 图片预处理 → OpenCV + Pillow</div>
            <div>• 语义检索 → sentence-transformers</div>
          </div>
        </div>

        <div>
          <label class="text-xs font-medium text-gray-600 block mb-1">AI 提供方</label>
          <select v-model="provider" @change="onProviderChange" class="w-full border rounded px-3 py-1.5 text-sm">
            <option v-for="p in availableProviders" :key="p.id" :value="p.id">{{ p.name }}</option>
            <option value="__custom__">➕ 其他 API 提供商...</option>
            <option value="mock">Mock (离线演示)</option>
          </select>
        </div>

        <div v-if="provider === '__custom__'" class="space-y-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
          <h4 class="text-xs font-semibold text-blue-700">🔗 添加新的 API 提供商</h4>
          <p class="text-[10px] text-blue-600">输入 API Base URL 和 API Key，系统将自动发现可用模型并智能分类</p>

          <div>
            <label class="text-xs font-medium text-gray-600 block mb-1">API Base URL</label>
            <input
              v-model="customBaseUrl"
              class="w-full border rounded px-3 py-1.5 text-sm"
              placeholder="https://api.example.com/v1"
            />
          </div>

          <div>
            <label class="text-xs font-medium text-gray-600 block mb-1">API Key</label>
            <div class="flex space-x-2">
              <input
                v-model="customApiKey"
                :type="showCustomKey ? 'text' : 'password'"
                class="flex-1 border rounded px-3 py-1.5 text-sm"
                placeholder="sk-xxx"
              />
              <button @click="showCustomKey = !showCustomKey" class="px-2 text-xs text-gray-400 hover:text-gray-600">
                {{ showCustomKey ? '隐藏' : '显示' }}
              </button>
            </div>
          </div>

          <div>
            <label class="text-xs font-medium text-gray-600 block mb-1">提供商名称（可选，留空自动检测）</label>
            <input
              v-model="customProviderName"
              class="w-full border rounded px-3 py-1.5 text-sm"
              placeholder="自动从 URL 检测"
            />
          </div>

          <div class="flex items-center space-x-2">
            <input type="checkbox" v-model="customAutoTest" id="auto-test" class="rounded" />
            <label for="auto-test" class="text-xs text-gray-600">自动测试模型并生成降级链</label>
          </div>

          <button
            @click="discoverAndAddProvider"
            :disabled="discovering || !customBaseUrl || !customApiKey"
            class="w-full px-4 py-2 bg-blue-500 text-white rounded text-sm font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ discovering ? '🔍 正在发现模型...' : '🔍 发现并添加模型' }}
          </button>

          <div v-if="discoveryResult" class="space-y-2">
            <div v-if="discoveryResult.success" class="p-2 bg-green-50 rounded text-xs">
              <div class="font-semibold text-green-700 mb-1">
                ✅ {{ discoveryResult.provider_name }} ({{ discoveryResult.provider_id }})
              </div>
              <div class="text-green-600 space-y-0.5">
                <div>📝 大语言模型: {{ discoveryResult.summary?.llm || 0 }} 个</div>
                <div>🖼️ 多模态模型: {{ discoveryResult.summary?.omni || 0 }} 个</div>
                <div>📊 向量/排序模型: {{ (discoveryResult.summary?.embedding || 0) + (discoveryResult.summary?.rerank || 0) }} 个</div>
                <div v-if="discoveryResult.auto_test_result?.working_models?.length" class="mt-1">
                  ✅ 可用模型: {{ discoveryResult.auto_test_result.working_models.join(', ') }}
                </div>
              </div>
            </div>
            <div v-else class="p-2 bg-red-50 rounded text-xs text-red-600">
              ❌ {{ discoveryResult.error }}
            </div>

            <div v-if="discoveryResult.success && discoveryResult.task_model_map" class="p-2 bg-blue-50 rounded text-xs">
              <div class="font-semibold text-blue-700 mb-1">📋 自动生成的任务-模型映射</div>
              <div class="space-y-1 max-h-40 overflow-y-auto">
                <div v-for="(slots, task) in discoveryResult.task_model_map" :key="task" class="flex flex-wrap gap-x-2">
                  <span class="text-blue-600 font-medium">{{ taskLabels[task] || task }}:</span>
                  <span v-for="(model, slot) in slots" :key="slot" class="text-blue-500">
                    {{ slot }}={{ model.split(':').pop() }}
                  </span>
                </div>
              </div>
            </div>

            <div v-if="discoveryResult.success && discoveryResult.critic_fallback_map" class="p-2 bg-purple-50 rounded text-xs">
              <div class="font-semibold text-purple-700 mb-1">🔍 自动生成的 Critic 降级映射</div>
              <div class="space-y-0.5">
                <div v-for="(chain, task) in discoveryResult.critic_fallback_map" :key="task" class="text-purple-500">
                  {{ taskLabels[task] || task }} → {{ chain }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="provider !== '__custom__' && provider !== 'mock'">
          <label class="text-xs font-medium text-gray-600 block mb-1">API Key</label>
          <div class="flex space-x-2">
            <input
              v-model="apiKey"
              :type="showApiKey ? 'text' : 'password'"
              class="flex-1 border rounded px-3 py-1.5 text-sm"
              :placeholder="currentMaskedKey ? `已配置 (${currentMaskedKey})` : '输入 API Key'"
            />
            <button @click="showApiKey = !showApiKey" class="px-2 text-xs text-gray-400 hover:text-gray-600">
              {{ showApiKey ? '隐藏' : '显示' }}
            </button>
          </div>
          <p v-if="currentMaskedKey && !apiKey" class="text-[10px] text-gray-400 mt-1">留空则保留已配置的 Key 不变</p>
        </div>

        <div v-if="provider !== '__custom__'">
          <label class="text-xs font-medium text-gray-600 block mb-1">模型覆盖（高级）</label>
          <select v-model="modelOverride" class="w-full border rounded px-3 py-1.5 text-sm">
            <option value="">默认（自动选择）</option>
            <optgroup v-if="models.llm?.length" label="大语言模型">
              <option v-for="m in models.llm" :key="m" :value="m">{{ m }}</option>
            </optgroup>
            <optgroup v-if="models.omni?.length" label="多模态模型">
              <option v-for="m in models.omni" :key="m" :value="m">{{ m }}</option>
            </optgroup>
            <optgroup v-if="models.embedding?.length" label="向量/排序模型">
              <option v-for="m in models.embedding" :key="m" :value="m">{{ m }}</option>
            </optgroup>
          </select>
          <p class="text-[10px] text-gray-400 mt-1">留空则根据任务类型自动选择最优模型</p>
        </div>

        <div>
          <label class="text-xs font-medium text-gray-600 block mb-1">已配置的提供商</label>
          <div class="bg-gray-50 rounded p-2 text-[10px] text-gray-500 space-y-1">
            <div v-for="(info, pid) in providersDetail" :key="pid" class="flex justify-between items-center">
              <span>{{ info.name }} ({{ pid }})</span>
              <span :class="info.has_api_key ? 'text-green-500' : 'text-red-400'">
                {{ info.has_api_key ? '✅ 已配置' : '❌ 未配置' }}
                <span v-if="info.masked_api_key" class="text-gray-400 ml-1">({{ info.masked_api_key }})</span>
                <span class="text-gray-400 ml-1">LLM:{{ info.model_counts?.llm || 0 }} 多模态:{{ info.model_counts?.omni || 0 }} 向量:{{ info.model_counts?.embedding || 0 }}</span>
              </span>
            </div>
            <div v-if="!Object.keys(providersDetail).length" class="text-gray-400 text-center">暂无提供商</div>
          </div>
        </div>

        <div>
          <label class="text-xs font-medium text-gray-600 block mb-1">任务-模型映射</label>
          <div class="bg-gray-50 rounded p-2 text-[10px] text-gray-500 space-y-1 max-h-32 overflow-y-auto">
            <div v-for="(config, task) in taskModelMap" :key="task" class="flex justify-between">
              <span>{{ taskLabels[task] || task }}</span>
              <span class="text-primary-500">{{ config.default }}</span>
            </div>
          </div>
        </div>

        <div class="flex space-x-2 pt-2">
          <button
            @click="saveSettings"
            class="flex-1 px-4 py-2 bg-primary-500 text-white rounded text-sm font-medium hover:bg-primary-600"
          >
            保存设置
          </button>
          <button
            @click="refreshModels"
            :disabled="refreshing"
            class="px-4 py-2 bg-green-500 text-white rounded text-sm font-medium hover:bg-green-600 disabled:opacity-50"
          >
            {{ refreshing ? '刷新中...' : '🔄 刷新模型' }}
          </button>
          <button
            @click="$emit('close')"
            class="px-4 py-2 bg-gray-100 text-gray-600 rounded text-sm hover:bg-gray-200"
          >
            取消
          </button>
        </div>

        <div v-if="saveMessage" class="text-xs text-center" :class="saveSuccess ? 'text-green-500' : 'text-red-500'">
          {{ saveMessage }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { apiClient } from '../utils/api';

defineProps<{ visible: boolean }>();
defineEmits(['close']);

const provider = ref('qwen');
const apiKey = ref('');
const showApiKey = ref(false);
const modelOverride = ref('');
const models = ref<any>({ llm: [], omni: [], embedding: [] });
const taskModelMap = ref<any>({});
const providersDetail = ref<any>({});
const saveMessage = ref('');
const saveSuccess = ref(false);

const customBaseUrl = ref('');
const customApiKey = ref('');
const customProviderName = ref('');
const customAutoTest = ref(true);
const showCustomKey = ref(false);
const discovering = ref(false);
const discoveryResult = ref<any>(null);
const refreshing = ref(false);
const healthStatus = ref<any>(null);

const taskLabels: Record<string, string> = {
  meeting_minutes: '会议纪要',
  literature_summary: '文献摘要',
  multilingual_polish: '多语言润色',
  ppt_generation: 'PPT生成',
  code_polish: '代码润色',
  math_reasoning: '数学推理',
  vision_analysis: '视觉分析',
  realtime_asr: '实时语音',
  general_chat: '通用对话',
  multimodal_understanding: '多模态理解',
  deep_reasoning: '深度推理',
};

const availableProviders = computed(() => {
  const list = [
    { id: 'qwen', name: '千问 (Qwen/DashScope)' },
    { id: 'tencent', name: '腾讯 (Hunyuan)' },
  ];
  for (const [pid, info] of Object.entries(providersDetail.value || {})) {
    if (pid !== 'qwen' && pid !== 'tencent') {
      list.push({ id: pid, name: (info as any).name || pid });
    }
  }
  return list;
});

const currentMaskedKey = computed(() => {
  const detail = providersDetail.value?.[provider.value];
  return detail?.masked_api_key || '';
});

onMounted(async () => {
  await loadSettings();
});

async function loadSettings() {
  try {
    const [providersRes, modelsRes, taskModelRes, detailRes, healthRes] = await Promise.allSettled([
      apiClient.getProviders(),
      apiClient.getModels(),
      apiClient.getTaskModelMap(),
      apiClient.getProvidersDetail(),
      apiClient.health(),
    ]);
    if (providersRes.status === 'fulfilled') {
      provider.value = providersRes.value.data.current || 'qwen';
    }
    if (modelsRes.status === 'fulfilled') {
      models.value = modelsRes.value.data;
    }
    if (taskModelRes.status === 'fulfilled') {
      taskModelMap.value = taskModelRes.value.data;
    }
    if (detailRes.status === 'fulfilled') {
      providersDetail.value = detailRes.value.data;
    }
    if (healthRes.status === 'fulfilled') {
      healthStatus.value = healthRes.value.data;
    }
  } catch (e) {
    // ignore
  }
}

async function onProviderChange() {
  apiKey.value = '';
  discoveryResult.value = null;
}

async function discoverAndAddProvider() {
  if (!customBaseUrl.value || !customApiKey.value) return;

  discovering.value = true;
  discoveryResult.value = null;

  try {
    const res = await apiClient.addProvider(
      customBaseUrl.value,
      customApiKey.value,
      undefined,
      customProviderName.value || undefined,
      customAutoTest.value,
      customAutoTest.value,
    );
    discoveryResult.value = res.data;

    if (res.data.success) {
      await loadSettings();
      provider.value = res.data.provider_id;
    }
  } catch (e: any) {
    discoveryResult.value = {
      success: false,
      error: e?.response?.data?.detail || e?.message || '连接失败',
    };
  } finally {
    discovering.value = false;
  }
}

async function refreshModels() {
  refreshing.value = true;
  try {
    await apiClient.discoverExistingModels();
    await loadSettings();
    saveMessage.value = '模型列表已刷新';
    saveSuccess.value = true;
  } catch (e) {
    saveMessage.value = '刷新失败';
    saveSuccess.value = false;
  } finally {
    refreshing.value = false;
    setTimeout(() => { saveMessage.value = ''; }, 2000);
  }
}

async function saveSettings() {
  try {
    const modelName = modelOverride.value || undefined;
    if (provider.value === '__custom__') {
      saveMessage.value = '请先点击"发现并添加模型"';
      saveSuccess.value = false;
      return;
    }
    if (apiKey.value.trim()) {
      await apiClient.switchProvider(provider.value, modelName, apiKey.value.trim());
    } else if (provider.value) {
      await apiClient.switchProvider(provider.value, modelName);
    }
    saveMessage.value = '设置已保存';
    saveSuccess.value = true;
    setTimeout(() => { saveMessage.value = ''; }, 2000);
  } catch (e) {
    saveMessage.value = '保存失败，请重试';
    saveSuccess.value = false;
  }
}
</script>
