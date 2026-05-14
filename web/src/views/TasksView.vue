<template>
  <div class="p-4 space-y-3">
    <div class="flex items-center space-x-2 flex-wrap gap-y-1">
      <button
        v-for="s in statusesWithCount"
        :key="s.value"
        @click="filterStatus = s.value"
        :class="filterStatus === s.value ? 'bg-primary-500 text-white' : 'bg-gray-100 text-gray-600'"
        class="px-2 py-1 rounded text-xs"
      >
        {{ s.label }} <span class="opacity-70">({{ s.count }})</span>
      </button>
      <button @click="loadTasks" class="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">刷新</button>
    </div>
    <div class="flex items-center space-x-3 text-xs text-gray-500 bg-gray-50 rounded px-3 py-1.5">
      <span>总计: <strong class="text-gray-700">{{ totalCount }}</strong></span>
      <span>已完成: <strong class="text-green-600">{{ completedCount }}</strong></span>
      <span>失败: <strong class="text-red-500">{{ failedCount }}</strong></span>
    </div>
    <div v-if="tasks.length === 0" class="text-center text-gray-400 text-xs py-4">暂无任务</div>
    <div v-else class="space-y-1 overflow-y-auto" style="max-height: calc(100vh - 200px)">
      <div
        v-for="task in tasks"
        :key="task.task_id"
        class="flex items-center justify-between text-xs border-b border-gray-100 py-1"
      >
        <span class="text-gray-600">{{ task.task_type }}</span>
        <span
          :class="{
            'text-yellow-600': task.status === 'pending',
            'text-blue-600': task.status === 'processing',
            'text-green-600': task.status === 'completed',
            'text-red-600': task.status === 'failed',
          }"
        >
          {{ statusLabels[task.status] || task.status }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue';
import { apiClient } from '../utils/api';

const tasks = ref<any[]>([]);
const allTasks = ref<any[]>([]);
const filterStatus = ref('');

const statuses = [
  { value: '', label: '全部' },
  { value: 'pending', label: '等待中' },
  { value: 'processing', label: '处理中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
];

const statusLabels: Record<string, string> = {
  pending: '等待中',
  processing: '处理中',
  completed: '已完成',
  failed: '失败',
};

const totalCount = computed(() => allTasks.value.length);
const completedCount = computed(() => allTasks.value.filter(t => t.status === 'completed').length);
const failedCount = computed(() => allTasks.value.filter(t => t.status === 'failed').length);

const statusesWithCount = computed(() => {
  return statuses.map(s => ({
    ...s,
    count: s.value ? allTasks.value.filter(t => t.status === s.value).length : allTasks.value.length,
  }));
});

async function loadAllTasks() {
  try {
    const res = await apiClient.getTasks(undefined);
    allTasks.value = Array.isArray(res.data) ? res.data : (res.data.tasks || []);
  } catch (e) {
    // ignore
  }
}

async function loadTasks() {
  await loadAllTasks();
  if (!filterStatus.value) {
    tasks.value = allTasks.value;
  } else {
    tasks.value = allTasks.value.filter(t => t.status === filterStatus.value);
  }
}

watch(filterStatus, () => {
  loadTasks();
});

let refreshInterval: number | null = null;

onMounted(() => {
  loadTasks();
  refreshInterval = window.setInterval(loadTasks, 5000);
});

onBeforeUnmount(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval);
    refreshInterval = null;
  }
});
</script>
