<template>
  <div class="flex items-center justify-center h-full overflow-y-auto">
    <div class="max-w-3xl w-full p-4">
      <div class="mb-6 text-center">
        <h2 class="text-2xl font-bold text-gray-800 mb-2">LVV - Love Working</h2>
        <p class="text-sm text-gray-500">你的智能办公助手，选择一个任务开始吧</p>
      </div>

      <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="bg-white border rounded-lg p-3 text-center">
          <div class="text-xs text-gray-400">待处理任务</div>
          <div class="text-lg font-bold text-yellow-600 mt-1">{{ taskStats.pending }}</div>
        </div>
        <div class="bg-white border rounded-lg p-3 text-center">
          <div class="text-xs text-gray-400">已完成任务</div>
          <div class="text-lg font-bold text-green-600 mt-1">{{ taskStats.completed }}</div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4 mb-6">
        <div
          v-for="task in tasks"
          :key="task.path"
          @click="goTo(task.path)"
          class="bg-white border-2 border-gray-200 rounded-xl p-5 cursor-pointer hover:border-primary-400 hover:shadow-md transition-all group text-left"
          :class="{ 'border-primary-400 border-dashed bg-primary-50/30': task.highlight }"
        >
          <div class="text-3xl mb-3">{{ task.icon }}</div>
          <h3 class="text-sm font-semibold text-gray-800 group-hover:text-primary-600 mb-1">{{ task.title }}</h3>
          <p class="text-xs text-gray-400 leading-relaxed">{{ task.desc }}</p>
          <div class="mt-3 flex flex-wrap gap-1">
            <span
              v-for="tag in task.tags"
              :key="tag"
              class="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded"
            >{{ tag }}</span>
          </div>
        </div>
      </div>

      <div v-if="circuitBreakers && Object.keys(circuitBreakers).length > 0" class="bg-white border rounded-lg p-3 mb-4">
        <h4 class="text-xs font-semibold text-gray-500 mb-2">熔断器状态</h4>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="(info, key) in circuitBreakers"
            :key="key"
            class="text-[10px] px-2 py-0.5 rounded"
            :class="{
              'bg-green-100 text-green-600': info.circuit_state === 'closed',
              'bg-red-100 text-red-600': info.circuit_state === 'open',
              'bg-yellow-100 text-yellow-600': info.circuit_state === 'half_open',
            }"
          >
            {{ info.model }}: {{ info.circuit_state === 'closed' ? '正常' : info.circuit_state === 'open' ? '熔断' : '半开' }}
          </span>
        </div>
      </div>

      <div class="text-center text-xs text-gray-400">
        也可以使用左侧导航栏随时切换功能 · CLI 用户请运行 <code class="bg-gray-100 px-1 rounded">agent-cli interactive</code>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAppStore } from '../stores/app';
import { apiClient } from '../utils/api';

const router = useRouter();
const store = useAppStore();

const taskStats = ref<any>({ pending: 0, completed: 0, processing: 0 });
const circuitBreakers = ref<any>({});

const tasks = [
  {
    path: '/chat',
    icon: '🤖',
    title: '通用模式',
    desc: '对话 + 文件生成，写周报、方案书、报告等，一键下载',
    tags: ['对话', '生成文件', '材料模板', 'MD/HTML/TXT'],
    highlight: true,
  },
  {
    path: '/meeting',
    icon: '📝',
    title: '会议纪要',
    desc: '实时监听或上传录音，自动生成结构化纪要，支持多语言',
    tags: ['实时字幕', '录音上传', '双语对照'],
  },
  {
    path: '/literature',
    icon: '📚',
    title: '文献摘要',
    desc: '上传文件，AI自动提取摘要并溯源标注，防幻觉',
    tags: ['PDF/MD/DOCX', 'RAG检索', '溯源标注'],
  },
  {
    path: '/polish',
    icon: '✨',
    title: '多语言润色',
    desc: '学术/商务/邮件多风格润色，Critic审查语体',
    tags: ['英日韩法德', '学术风格', '防中式英语'],
  },
  {
    path: '/ppt',
    icon: '📊',
    title: 'PPT 生成',
    desc: '输入主题自动生成大纲，Critic校验排版，HTML预览+下载',
    tags: ['自动排版', '模板选择', 'HTML预览'],
  },
];

async function goTo(path: string) {
  const taskTypeMap: Record<string, string> = {
    '/chat': 'general',
    '/meeting': 'meeting',
    '/literature': 'literature',
    '/polish': 'polish',
    '/ppt': 'ppt',
  };
  await store.startNewConversation(taskTypeMap[path]);
  router.push(path);
}

onMounted(async () => {
  try {
    const [pendingRes, completedRes] = await Promise.allSettled([
      apiClient.getTasks('pending'),
      apiClient.getTasks('completed'),
    ]);

    if (pendingRes.status === 'fulfilled') {
      taskStats.value.pending = Array.isArray(pendingRes.value.data) ? pendingRes.value.data.length : 0;
    }
    if (completedRes.status === 'fulfilled') {
      taskStats.value.completed = Array.isArray(completedRes.value.data) ? completedRes.value.data.length : 0;
    }
  } catch (e) {
    // ignore
  }
});
</script>
