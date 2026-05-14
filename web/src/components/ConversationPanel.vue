<template>
  <div class="flex flex-col h-full">
    <div class="p-2 border-b">
      <button
        @click="newConversation"
        class="w-full py-1.5 bg-primary-500 text-white rounded text-xs font-medium hover:bg-primary-600 flex items-center justify-center space-x-1"
      >
        <span>＋</span>
        <span>新对话</span>
      </button>
    </div>

    <div class="p-2 border-b">
      <input
        v-model="searchKeyword"
        class="w-full border rounded px-2 py-1 text-xs focus:ring-1 focus:ring-primary-300"
        placeholder="搜索对话..."
        @input="onSearch"
      />
    </div>

    <div class="p-2 border-b">
      <select
        v-model="filterType"
        class="w-full border rounded px-2 py-1 text-xs focus:ring-1 focus:ring-primary-300"
      >
        <option value="">全部类型</option>
        <option value="chat">💬 通用对话</option>
        <option value="general">🤖 通用模式</option>
        <option value="meeting">📝 会议纪要</option>
        <option value="literature">📚 文献摘要</option>
        <option value="polish">✨ 多语言润色</option>
        <option value="ppt">📊 PPT生成</option>
      </select>
    </div>

    <div class="flex-1 overflow-y-auto">
      <div v-if="filteredConversations.length === 0" class="text-center text-gray-300 text-xs py-6">
        暂无对话记录
      </div>
      <div
        v-for="conv in filteredConversations"
        :key="conv.conv_id"
        class="group px-2 py-2 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors"
        :class="{ 'bg-primary-50 border-l-2 border-l-primary-500': store.currentConvId === conv.conv_id }"
        @click="selectConversation(conv.conv_id)"
      >
        <div class="flex items-center justify-between">
          <div class="flex-1 min-w-0">
            <div class="flex items-center space-x-1">
              <span class="text-xs">{{ taskTypeIcon(conv.task_type) }}</span>
              <span class="text-xs font-medium text-gray-700 truncate">{{ conv.title || taskTypeLabel(conv.task_type) }}</span>
              <span v-if="store.isConvProcessing(conv.conv_id)" class="text-[9px] text-primary-500 animate-pulse">●</span>
            </div>
            <div class="flex items-center space-x-1 mt-0.5">
              <span class="text-[9px] px-1 py-0.5 rounded-full" :class="taskTypeBadgeClass(conv.task_type)">{{ taskTypeLabel(conv.task_type) }}</span>
              <span class="text-[10px] text-gray-400 truncate">
                {{ formatTime(conv.updated_at || conv.created_at) }}
              </span>
            </div>
          </div>
          <button
            @click.stop="confirmDelete(conv.conv_id)"
            class="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-400 text-xs transition-opacity p-1"
            title="删除对话"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAppStore } from '../stores/app';
import type { Conversation } from '../stores/app';

const store = useAppStore();
const router = useRouter();
const searchKeyword = ref('');
const filterType = ref('');
const searchResults = ref<any[] | null>(null);

const taskTypeIcons: Record<string, string> = {
  chat: '💬',
  meeting: '📝',
  literature: '📚',
  polish: '✨',
  ppt: '📊',
  general: '🤖',
};

const taskTypeLabels: Record<string, string> = {
  chat: '通用对话',
  meeting: '会议纪要',
  literature: '文献摘要',
  polish: '多语言润色',
  ppt: 'PPT生成',
  general: '通用模式',
};

const taskTypeBadgeClasses: Record<string, string> = {
  chat: 'bg-blue-100 text-blue-600',
  meeting: 'bg-green-100 text-green-600',
  literature: 'bg-purple-100 text-purple-600',
  polish: 'bg-yellow-100 text-yellow-600',
  ppt: 'bg-red-100 text-red-600',
  general: 'bg-indigo-100 text-indigo-600',
};

function taskTypeIcon(type: string) {
  return taskTypeIcons[type] || '💬';
}

function taskTypeLabel(type: string) {
  return taskTypeLabels[type] || type;
}

function taskTypeBadgeClass(type: string) {
  return taskTypeBadgeClasses[type] || 'bg-gray-100 text-gray-600';
}

const filteredConversations = computed(() => {
  let result = searchResults.value ?? store.conversations;
  if (filterType.value) {
    result = result.filter((c) => c.task_type === filterType.value);
  }
  return result;
});

function formatTime(isoStr: string) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins}分钟前`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}小时前`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}天前`;
    return d.toLocaleDateString('zh-CN');
  } catch {
    return '';
  }
}

async function newConversation() {
  const currentRoute = window.location.pathname;
  let taskType = 'chat';
  if (currentRoute.includes('meeting')) taskType = 'meeting';
  else if (currentRoute.includes('literature')) taskType = 'literature';
  else if (currentRoute.includes('polish')) taskType = 'polish';
  else if (currentRoute.includes('ppt')) taskType = 'ppt';

  await store.startNewConversation(taskType);
}

async function selectConversation(convId: string) {
  const taskType = await store.switchConversation(convId);
  if (taskType) {
    const routeMap: Record<string, string> = {
      chat: '/chat',
      general: '/chat',
      meeting: '/meeting',
      literature: '/literature',
      polish: '/polish',
      ppt: '/ppt',
    };
    const targetRoute = routeMap[taskType] || '/chat';
    if (router.currentRoute.value.path !== targetRoute) {
      router.push(targetRoute);
    }
  }
}

async function confirmDelete(convId: string) {
  if (confirm('确定删除此对话？')) {
    await store.deleteConversation(convId);
  }
}

let searchTimer: any = null;
function onSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    if (searchKeyword.value) {
      try {
        const { apiClient } = await import('../utils/api');
        const res = await apiClient.searchConversations(searchKeyword.value);
        searchResults.value = res.data.conversations || [];
      } catch (e) {
        searchResults.value = null;
      }
    } else {
      searchResults.value = null;
      await store.loadConversations();
    }
  }, 300);
}

onMounted(() => {
  store.loadConversations();
});
</script>
