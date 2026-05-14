<template>
  <div class="bg-white rounded-lg shadow p-4">
    <h3 class="text-sm font-semibold text-gray-700 mb-3">Agentic Workflow</h3>
    <div class="space-y-2">
      <div
        v-for="(step, index) in store.workflowSteps"
        :key="index"
        class="workflow-step border rounded-lg p-3 text-sm"
        :class="{
          'active': step.status === 'active',
          'completed': step.status === 'completed',
          'border-gray-200': step.status === 'pending',
        }"
      >
        <div class="flex items-center">
          <span v-if="step.status === 'completed'" class="text-green-500 mr-2">&#10003;</span>
          <span v-else-if="step.status === 'active'" class="text-blue-500 mr-2 animate-spin">&#9696;</span>
          <span v-else class="text-gray-400 mr-2">&#9675;</span>
          <span :class="{ 'text-gray-400': step.status === 'pending' }">{{ step.name }}</span>
        </div>
      </div>
      <div v-if="store.workflowSteps.length === 0" class="text-gray-400 text-sm text-center py-4">
        等待任务开始...
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAppStore } from '../stores/app';
const store = useAppStore();
</script>
