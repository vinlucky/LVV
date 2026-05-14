<template>
  <div class="bg-white rounded-lg shadow p-4 mb-4">
    <h3 class="text-sm font-semibold text-gray-700 mb-3">思考过程</h3>
    <div class="bg-gray-50 rounded p-3 text-sm text-gray-500 stream-text max-h-64 overflow-y-auto">
      <div v-if="store.actorText || store.criticText">
        <div v-if="store.actorText" class="mb-3">
          <div class="text-[10px] font-semibold text-blue-500 mb-1">Actor 思考</div>
          <div class="text-blue-700 stream-text" v-html="formattedActorText"></div>
        </div>
        <div v-if="store.criticText">
          <div class="text-[10px] font-semibold text-yellow-600 mb-1">Critic 审查</div>
          <div class="text-yellow-800 stream-text" v-html="formattedCriticText"></div>
        </div>
      </div>
      <div v-else class="text-center text-gray-400">等待思考过程...</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useAppStore } from '../stores/app';

const store = useAppStore();

function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatDiffText(raw: string): string {
  const delParts: string[] = [];
  const insParts: string[] = [];
  let temp = raw;
  temp = temp.replace(/<del>([\s\S]*?)<\/del>/g, (_, content) => {
    delParts.push(content);
    return `__DEL_${delParts.length - 1}__`;
  });
  temp = temp.replace(/<ins>([\s\S]*?)<\/ins>/g, (_, content) => {
    insParts.push(content);
    return `__INS_${insParts.length - 1}__`;
  });
  temp = escapeHtml(temp);
  delParts.forEach((content, i) => {
    temp = temp.replace(`__DEL_${i}__`, `<span class="critic-mark" title="Critic 建议删除">${escapeHtml(content)}</span>`);
  });
  insParts.forEach((content, i) => {
    temp = temp.replace(`__INS_${i}__`, `<span class="insert-mark" title="Critic 建议添加">${escapeHtml(content)}</span>`);
  });
  return temp;
}

const formattedActorText = computed(() => {
  if (!store.actorText) return '';
  return formatDiffText(store.actorText);
});

const formattedCriticText = computed(() => {
  if (!store.criticText) return '';
  return formatDiffText(store.criticText);
});
</script>
