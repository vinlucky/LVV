<template>
  <div class="flex items-center space-x-2 text-xs">
    <div v-if="usage" class="flex items-center space-x-1">
      <span class="text-gray-400">Token:</span>
      <div class="w-16 bg-gray-200 rounded-full h-1.5">
        <div
          class="h-1.5 rounded-full progress-bar"
          :class="progressPercent > 80 ? 'bg-red-500' : 'bg-primary-500'"
          :style="{ width: progressPercent + '%' }"
        ></div>
      </div>
      <span class="text-gray-400">{{ remaining }}</span>
    </div>
    <span v-else class="text-gray-400">Token: --</span>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { apiClient } from '../utils/api';

const usage = ref<any>(null);

const progressPercent = computed(() => {
  if (!usage.value || !usage.value.budget) return 0;
  return Math.min(100, (usage.value.daily_usage / usage.value.budget) * 100);
});

const remaining = computed(() => {
  if (!usage.value) return '--';
  const budget = usage.value.budget || 1000000;
  const used = usage.value.daily_usage || 0;
  return (budget - used).toLocaleString();
});

onMounted(async () => {
  try {
    const res = await apiClient.getTokenUsage();
    usage.value = res.data;
  } catch (e) {
    // ignore
  }
});
</script>
