<template>
  <div v-if="showInitOverlay" class="fixed inset-0 z-[9999] bg-gray-900 flex items-center justify-center">
    <div class="max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
      <div class="text-center mb-6">
        <div class="text-5xl mb-3">🔑</div>
        <h1 class="text-xl font-bold text-white mb-2">需要先配置 API Key</h1>
        <p class="text-gray-400 text-sm">检测到尚未配置任何 AI 提供方的 API Key</p>
      </div>

      <div v-if="!store.backendOnline" class="bg-red-900/30 border border-red-700/50 rounded-lg p-4 mb-4">
        <p class="text-red-400 text-sm font-medium">⚠️ 无法连接到后端服务</p>
        <p class="text-red-300/70 text-xs mt-1">请先启动后端服务，再刷新此页面</p>
      </div>

      <div class="bg-amber-900/20 border border-amber-700/30 rounded-lg p-4 mb-4">
        <p class="text-amber-400 text-sm font-medium mb-2">💡 可选方案</p>
        <div class="space-y-2">
          <div class="flex items-start gap-2">
            <span class="text-amber-400 text-xs mt-0.5">1.</span>
            <div>
              <p class="text-amber-300 text-xs font-medium">配置 API Key（推荐）</p>
              <p class="text-amber-400/70 text-[10px]">功能完整，见下方引导</p>
            </div>
          </div>
          <div class="flex items-start gap-2">
            <span class="text-amber-400 text-xs mt-0.5">2.</span>
            <div>
              <p class="text-amber-300 text-xs font-medium">使用本地备用库（无需 API Key，功能有限，已随依赖安装）</p>
            </div>
          </div>
        </div>
      </div>

      <div class="bg-gray-800 rounded-lg p-5 mb-4">
        <h2 class="text-white font-semibold mb-3 text-sm">使用 CLI 初始化</h2>

        <div class="space-y-3">
          <div>
            <p class="text-gray-400 text-[10px] mb-1">步骤 1：进入项目目录</p>
            <div class="bg-gray-900 rounded px-3 py-2 font-mono text-xs text-green-400 select-all">
              cd agent && cd cli
            </div>
          </div>

          <div>
            <p class="text-gray-400 text-[10px] mb-1">步骤 2：运行初始化命令</p>
            <div class="bg-gray-900 rounded px-3 py-2 font-mono text-xs text-green-400 select-all">
              npm run dev -- setup
            </div>
          </div>

          <div>
            <p class="text-gray-400 text-[10px] mb-1">步骤 3：按提示选择 AI 提供方并输入 API Key</p>
            <div class="bg-gray-900 rounded px-3 py-2 text-[10px] text-gray-300 space-y-1">
              <p>? 请选择 AI 提供方：<span class="text-yellow-400">千问 (Qwen/DashScope)</span></p>
              <p>? 请输入千问 API Key：<span class="text-yellow-400">sk-xxxxxxxx</span></p>
              <p class="text-green-400">✅ 配置已保存！</p>
            </div>
          </div>
        </div>
      </div>

      <div class="bg-gray-800/50 rounded-lg p-3 mb-4">
        <p class="text-gray-400 text-[10px] mb-2">支持的 AI 提供方</p>
        <div class="flex gap-3">
          <div class="flex-1 bg-gray-900/50 rounded p-2.5">
            <p class="text-white text-xs font-medium">千问 Qwen</p>
            <p class="text-gray-500 text-[10px] mt-0.5">DashScope API Key</p>
            <a href="https://dashscope.console.aliyun.com/apiKey" target="_blank" class="text-primary-400 text-[10px] hover:underline mt-1 inline-block">获取 Key →</a>
          </div>
          <div class="flex-1 bg-gray-900/50 rounded p-2.5">
            <p class="text-white text-xs font-medium">腾讯混元</p>
            <p class="text-gray-500 text-[10px] mt-0.5">Hunyuan API Key</p>
            <a href="https://console.cloud.tencent.com/hunyuan" target="_blank" class="text-primary-400 text-[10px] hover:underline mt-1 inline-block">获取 Key →</a>
          </div>
        </div>
      </div>

      <div class="text-center">
        <button
          @click="retryInit"
          class="px-6 py-2 bg-primary-500 hover:bg-primary-600 text-white rounded-lg text-sm font-medium transition-colors"
          :disabled="retrying"
        >
          {{ retrying ? '检测中...' : '已完成配置，点击刷新' }}
        </button>
      </div>
    </div>
  </div>

  <div v-else class="h-screen flex flex-col overflow-hidden bg-gray-50" :class="{ 'select-none': resizingLeft || resizingRight || resizingInput }">
    <header class="h-14 bg-white border-b flex items-center justify-between px-5 flex-shrink-0">
      <div class="flex items-center">
        <div class="flex items-center">
          <span class="text-2xl font-extrabold tracking-wider text-gray-800">LVV</span>
          <div class="ml-1.5 flex flex-col leading-none">
            <span class="text-[8px] font-medium text-primary-500 tracking-widest">Love</span>
            <span class="text-[8px] font-medium text-primary-500 tracking-widest">Working</span>
          </div>
        </div>
      </div>

      <div class="flex items-center space-x-1">
        <button
          v-for="item in coreNavItems"
          :key="item.path"
          @click="switchMode(item.path)"
          class="flex items-center px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors"
          :class="isActive(item.path) ? 'bg-primary-50 text-primary-600' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'"
        >
          <span class="mr-1">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </button>

        <div class="relative" ref="moreMenuRef">
          <button
            @click="showMoreMenu = !showMoreMenu"
            class="flex items-center px-2 py-1.5 rounded-md text-xs font-medium text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            ···
          </button>
          <div
            v-if="showMoreMenu"
            class="absolute right-0 top-full mt-1 w-40 bg-white border rounded-lg shadow-lg py-1 z-50"
          >
            <router-link
              to="/tasks"
              class="flex items-center px-3 py-2 text-xs text-gray-600 hover:bg-gray-50"
              @click="showMoreMenu = false"
            >
              📋 任务中心
            </router-link>
            <router-link
              to="/skills"
              class="flex items-center px-3 py-2 text-xs text-gray-600 hover:bg-gray-50"
              @click="showMoreMenu = false"
            >
              🧩 Skills 扩展
            </router-link>
            <button
              @click="showSettings = true; showMoreMenu = false"
              class="w-full flex items-center px-3 py-2 text-xs text-gray-600 hover:bg-gray-50"
            >
              ⚙️ 设置
            </button>
            <label class="flex items-center px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 cursor-pointer">
              <input type="checkbox" v-model="store.offlineMode" class="mr-2 rounded" />
              脱机模式
            </label>
            <div class="border-t my-1"></div>
          </div>
        </div>

        <div class="w-px h-5 bg-gray-200 mx-1"></div>

        <span v-if="store.currentConvId" class="text-[10px] text-gray-400">
          {{ store.currentConvId.slice(0, 8) }}...
        </span>
        <span v-if="store.currentConvType && store.currentConvId" class="text-[10px] px-1.5 py-0.5 rounded-full" :class="taskTypeBadgeClass(store.currentConvType)">
          {{ taskTypeLabel(store.currentConvType) }}
        </span>
        <span v-if="store.isProcessing" class="text-[10px] text-primary-500 animate-pulse">●</span>
        <button
          v-if="store.currentConvId"
          @click="handleRollback"
          class="text-[10px] text-orange-500 hover:text-orange-700 font-medium ml-1"
          title="回退上一轮对话"
        >
          ↩
        </button>
        <button
          v-if="store.currentConvId"
          @click="handleRegenerate"
          class="text-[10px] text-blue-500 hover:text-blue-700 font-medium"
          title="重新生成最后回复"
        >
          🔄
        </button>
        <button
          @click="handleNewConversation"
          class="text-[10px] text-primary-500 hover:text-primary-700 font-medium"
        >
          ＋新对话
        </button>
      </div>
    </header>

    <div class="flex-1 flex overflow-hidden">
      <div class="flex flex-col border-r bg-white overflow-hidden" :style="{ width: leftPanelWidth + '%' }">
        <div class="flex-shrink-0" style="height: 33.33%">
          <div class="h-full overflow-y-auto p-3">
            <WorkflowPanel />
          </div>
        </div>
        <div class="flex-1 overflow-hidden border-t">
          <ConversationPanel />
        </div>
      </div>

      <div
        class="w-1.5 cursor-col-resize bg-gray-200 hover:bg-primary-300 transition-colors flex-shrink-0"
        @mousedown="startResizeLeft"
      ></div>

      <div class="flex flex-col overflow-hidden relative" :style="{ width: (100 - leftPanelWidth) + '%' }"
        @dragover.prevent="globalDragging = true"
        @dragleave.prevent="handleGlobalDragLeave"
        @drop.prevent="handleGlobalDrop"
      >
        <div
          v-if="globalDragging"
          class="absolute inset-0 z-50 bg-primary-50/90 border-2 border-dashed border-primary-400 rounded-lg flex items-center justify-center"
        >
          <div class="text-center">
            <div class="text-4xl mb-3">📥</div>
            <p class="text-primary-600 text-sm font-medium">松开即可添加文件</p>
            <p class="text-primary-400 text-xs mt-1">支持 MD/PDF/DOCX/Excel/PPT/TXT/代码文件</p>
          </div>
        </div>

        <template v-if="isFullPanelMode">
          <div v-if="route.path !== '/'" class="flex items-center px-4 py-2.5 border-b bg-white flex-shrink-0">
            <button
              @click="goBack"
              class="flex items-center px-2.5 py-1 rounded-md text-xs font-medium text-primary-500 hover:bg-primary-50 transition-colors"
            >
              ← 返回
            </button>
            <span class="ml-3 text-sm font-semibold text-gray-700">{{ fullPanelTitle }}</span>
          </div>
          <div class="flex-1 overflow-y-auto">
            <HomeView v-if="route.path === '/'" />
            <TasksView v-else-if="route.path === '/tasks'" />
            <SkillsView v-else-if="route.path === '/skills'" />
          </div>
        </template>

        <template v-else>
          <div class="flex-1 flex overflow-hidden">
            <div class="overflow-y-auto p-4 border-r bg-gray-50/50" :style="{ width: rightLeftWidth + '%' }">
              <div class="mb-2 flex items-center justify-between">
                <div class="flex items-center space-x-2">
                  <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider">思考过程</h3>
                  <span class="text-[10px] bg-primary-100 text-primary-600 px-1.5 py-0.5 rounded font-medium">{{ modeLabel }}</span>
                </div>
                <div v-if="store.conversationRounds.length > 1 && !(store.actorText || store.criticText)" class="flex items-center space-x-1">
                  <button
                    @click="selectedRoundIndex = Math.max(0, selectedRoundIndex - 1)"
                    :disabled="selectedRoundIndex <= 0"
                    class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 hover:bg-gray-200 disabled:opacity-30"
                  >↑</button>
                  <span class="text-[10px] text-gray-400">{{ selectedRoundIndex + 1 }} / {{ store.conversationRounds.length }}</span>
                  <button
                    @click="selectedRoundIndex = Math.min(store.conversationRounds.length - 1, selectedRoundIndex + 1)"
                    :disabled="selectedRoundIndex >= store.conversationRounds.length - 1"
                    class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 hover:bg-gray-200 disabled:opacity-30"
                  >↓</button>
                </div>
              </div>
              <div ref="thinkingPanelRef" class="bg-white rounded-lg p-4 text-sm text-gray-600 stream-text min-h-[200px] shadow-sm max-h-[calc(100vh-200px)] overflow-y-auto">
                <div v-if="activeTranscriptText || activeThinkingActor || activeThinkingCritic || activeThinkingRounds.length > 0">
                  <div v-if="activeTranscriptText" class="mb-4">
                    <div class="text-[10px] font-semibold text-red-500 mb-1">🎙️ 转文字</div>
                    <div class="text-red-700 stream-text whitespace-pre-wrap">{{ activeTranscriptText }}</div>
                  </div>
                  <template v-if="activeThinkingRounds.length > 0">
                    <div v-for="(round, rIdx) in activeThinkingRounds" :key="'round-'+rIdx" class="mb-4">
                      <div v-if="round.reactText" class="mb-3">
                        <div class="text-[10px] font-semibold text-green-600 mb-1">🤖 ReAct 第{{ round.iteration }}轮</div>
                        <div class="text-green-800 stream-text whitespace-pre-wrap">{{ round.reactText }}</div>
                      </div>
                      <div v-if="round.actorText" class="mb-3">
                        <div class="text-[10px] font-semibold text-blue-500 mb-1">Actor 第{{ round.iteration }}次</div>
                        <div class="text-blue-700 stream-text" v-html="formatDiffText(round.actorText)"></div>
                      </div>
                      <div v-if="round.criticText">
                        <div class="text-[10px] font-semibold text-yellow-600 mb-1">Critic 第{{ round.iteration }}次</div>
                        <div class="text-yellow-800 stream-text" v-html="formatDiffText(round.criticText)"></div>
                      </div>
                    </div>
                  </template>
                  <template v-else>
                    <div v-if="activeThinkingActor" class="mb-3">
                      <div class="text-[10px] font-semibold text-blue-500 mb-1">Actor 思考</div>
                      <div class="text-blue-700 stream-text" v-html="formattedActiveActor"></div>
                    </div>
                    <div v-if="activeThinkingCritic">
                      <div class="text-[10px] font-semibold text-yellow-600 mb-1">Critic 审查</div>
                      <div class="text-yellow-800 stream-text" v-html="formattedActiveCritic"></div>
                    </div>
                  </template>
                </div>
                <div v-else class="text-center text-gray-300 mt-12">
                  <svg class="w-10 h-10 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                  </svg>
                  <p class="text-xs">点击右侧对话轮次查看对应思考</p>
                </div>
              </div>
            </div>

            <div
              class="w-1 cursor-col-resize bg-gray-200 hover:bg-primary-300 transition-colors flex-shrink-0"
              @mousedown="startResizeRight"
            ></div>

            <div class="overflow-y-auto p-4" :style="{ width: (100 - rightLeftWidth) + '%' }">
              <div class="mb-2 flex items-center space-x-2">
                <h3 class="text-xs font-semibold text-green-500 uppercase tracking-wider">正式对话</h3>
                <span class="text-[10px] bg-green-100 text-green-600 px-1.5 py-0.5 rounded font-medium">{{ modeLabel }}</span>
              </div>
              <div class="space-y-3">
                <div
                  v-for="(round, idx) in store.conversationRounds"
                  :key="'hist-'+idx"
                  @click="selectRound(idx)"
                  class="bg-green-50 rounded-lg p-4 text-sm shadow-sm cursor-pointer transition-all border-2"
                  :class="selectedRoundIndex === idx && !(store.actorText || store.criticText) ? 'border-green-400 ring-1 ring-green-200' : 'border-transparent hover:border-green-200'"
                >
                  <div class="mb-3 pb-3 border-b border-green-200">
                    <div class="flex items-center justify-between">
                      <div class="text-[10px] font-semibold text-gray-500 mb-1">👤 用户</div>
                      <div class="text-[10px] text-gray-400">{{ formatDialogTime(round.timestamp) }}</div>
                    </div>
                    <div class="text-gray-700">{{ round.userMessage }}</div>
                    <div v-if="round.refFiles && round.refFiles.length > 0" class="mt-1 flex flex-wrap gap-2">
                      <a
                        v-for="rf in round.refFiles"
                        :key="rf.filename"
                        :href="getRefFileDownloadUrl(rf)"
                        :download="rf.filename"
                        class="inline-flex items-center space-x-1.5 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-xs text-blue-700 hover:bg-blue-100 hover:border-blue-300 transition-colors"
                      >
                        <span>📎</span>
                        <span class="font-medium">{{ rf.filename }}</span>
                        <span class="text-blue-400">⬇</span>
                      </a>
                    </div>
                  </div>
                  <div>
                    <div class="flex items-center justify-between">
                      <div class="text-[10px] font-semibold text-green-600 mb-1">🤖 回答</div>
                      <div class="text-[10px] text-gray-400">{{ formatDialogTime(round.timestamp) }}</div>
                    </div>
                    <div class="text-gray-800 stream-text" v-html="formatText(round.finalOutput)"></div>
                    <div v-if="round.generatedFiles && round.generatedFiles.length > 0" class="mt-2 pt-2 border-t border-green-200">
                      <div class="text-[10px] font-semibold text-gray-500 mb-1">📎 生成文件</div>
                      <div class="flex flex-wrap gap-2">
                        <a
                          v-for="gf in round.generatedFiles"
                          :key="gf.filename"
                          :href="getFileDownloadUrl(gf)"
                          :download="gf.filename"
                          class="inline-flex items-center space-x-1.5 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-xs text-blue-700 hover:bg-blue-100 hover:border-blue-300 transition-colors"
                        >
                          <span class="text-sm">{{ formatIcon(gf.file_format) }}</span>
                          <span class="font-medium">{{ gf.file_name || gf.filename }}</span>
                          <span class="text-[10px] text-blue-400">{{ (gf.file_format || '').toUpperCase() }}</span>
                          <span class="text-blue-400">⬇</span>
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="store.lastUserMessage || store.finalOutput" class="bg-green-50 rounded-lg p-4 text-sm shadow-sm border-2 border-green-300">
                  <div v-if="store.lastUserMessage" class="mb-3 pb-3 border-b border-green-200">
                    <div class="flex items-center justify-between">
                      <div class="text-[10px] font-semibold text-gray-500 mb-1">👤 用户</div>
                      <div class="text-[10px] text-primary-500 animate-pulse" v-if="store.isProcessing">生成中...</div>
                      <div class="text-[10px] text-gray-400" v-else>{{ formatDialogTime(null) }}</div>
                    </div>
                    <div class="text-gray-700">{{ store.lastUserMessage }}</div>
                    <div v-if="store.currentRefFiles.length > 0" class="mt-1 flex flex-wrap gap-2">
                      <a
                        v-for="rf in store.currentRefFiles"
                        :key="rf.filename"
                        :href="getRefFileDownloadUrl(rf)"
                        :download="rf.filename"
                        class="inline-flex items-center space-x-1.5 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-xs text-blue-700 hover:bg-blue-100 hover:border-blue-300 transition-colors"
                      >
                        <span>📎</span>
                        <span class="font-medium">{{ rf.filename }}</span>
                        <span class="text-blue-400">⬇</span>
                      </a>
                    </div>
                  </div>
                  <div v-if="store.finalOutput">
                    <div class="flex items-center justify-between">
                      <div class="text-[10px] font-semibold text-green-600 mb-1">🤖 回答</div>
                      <div class="text-[10px] text-gray-400">{{ formatDialogTime(null) }}</div>
                    </div>
                    <div class="text-gray-800 stream-text" v-html="formattedFinalOutput"></div>
                    <div v-if="currentConvFiles.length > 0" class="mt-2 pt-2 border-t border-green-200">
                      <div class="text-[10px] font-semibold text-gray-500 mb-1">📎 生成文件</div>
                      <div class="flex flex-wrap gap-2">
                        <a
                          v-for="gf in currentConvFiles"
                          :key="gf.filename"
                          :href="getFileDownloadUrl(gf)"
                          :download="gf.filename"
                          class="inline-flex items-center space-x-1.5 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-xs text-blue-700 hover:bg-blue-100 hover:border-blue-300 transition-colors"
                        >
                          <span class="text-sm">{{ formatIcon(gf.file_format) }}</span>
                          <span class="font-medium">{{ gf.file_name || gf.filename }}</span>
                          <span class="text-[10px] text-blue-400">{{ (gf.file_format || '').toUpperCase() }}</span>
                          <span class="text-blue-400">⬇</span>
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="!store.conversationRounds.length && !store.lastUserMessage && !store.finalOutput" class="bg-green-50 rounded-lg p-4 text-sm min-h-[200px] shadow-sm">
                  <div class="text-center text-gray-300 mt-12">
                    <svg class="w-10 h-10 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <p class="text-xs">等待生成结果...</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div
            class="h-1.5 cursor-row-resize bg-gray-200 hover:bg-primary-300 transition-colors flex-shrink-0"
            @mousedown="startResizeInput"
          ></div>

          <div class="flex-shrink-0 border-t bg-white p-4 overflow-y-auto" :style="{ height: inputAreaHeight + 'px', minHeight: '80px' }">
            <router-view />
          </div>
        </template>
      </div>
    </div>
    <SettingsPanel :visible="showSettings" @close="showSettings = false" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAppStore } from './stores/app';
import { streamPost, apiClient, validateUploadFile } from './utils/api';
import WorkflowPanel from './components/WorkflowPanel.vue';
import ConversationPanel from './components/ConversationPanel.vue';
import SettingsPanel from './components/SettingsPanel.vue';
import HomeView from './views/HomeView.vue';
import TasksView from './views/TasksView.vue';
import SkillsView from './views/SkillsView.vue';

const store = useAppStore();
const route = useRoute();
const router = useRouter();
const showSettings = ref(false);
const showMoreMenu = ref(false);
const moreMenuRef = ref<HTMLElement | null>(null);
const retrying = ref(false);
const selectedRoundIndex = ref(-1);
const thinkingPanelRef = ref<HTMLElement | null>(null);
const globalDragging = ref(false);
const leftPanelWidth = ref(33.33);
const rightLeftWidth = ref(40);
const inputAreaHeight = ref(180);
const resizingLeft = ref(false);
const resizingRight = ref(false);
const resizingInput = ref(false);

const activeThinkingRounds = computed(() => {
  if (store.thinkingRounds.length > 0) {
    return [...store.thinkingRounds].sort((a, b) => a.iteration - b.iteration);
  }
  if (selectedRoundIndex.value >= 0 && selectedRoundIndex.value < store.conversationRounds.length) {
    const round = store.conversationRounds[selectedRoundIndex.value];
    if (round.thinkingRounds && round.thinkingRounds.length > 0) {
      return [...round.thinkingRounds].sort((a, b) => a.iteration - b.iteration);
    }
    const state = store.streamStates.get(store.currentConvId || '');
    if (state) {
      const history = state.thinkingHistory;
      if (selectedRoundIndex.value < history.length && history[selectedRoundIndex.value].thinkingRounds?.length > 0) {
        return [...history[selectedRoundIndex.value].thinkingRounds].sort((a, b) => a.iteration - b.iteration);
      }
    }
  }
  return [];
});

const activeTranscriptText = computed(() => {
  if (store.transcriptText) return store.transcriptText;
  if (selectedRoundIndex.value >= 0 && selectedRoundIndex.value < store.conversationRounds.length) {
    return store.conversationRounds[selectedRoundIndex.value].transcriptText || '';
  }
  return '';
});

const activeThinkingActor = computed(() => {
  if (store.actorText || store.criticText) {
    return store.actorText;
  }
  if (selectedRoundIndex.value >= 0 && selectedRoundIndex.value < store.conversationRounds.length) {
    return store.conversationRounds[selectedRoundIndex.value].actorText;
  }
  return '';
});

const activeThinkingCritic = computed(() => {
  if (store.actorText || store.criticText) {
    return store.criticText;
  }
  if (selectedRoundIndex.value >= 0 && selectedRoundIndex.value < store.conversationRounds.length) {
    return store.conversationRounds[selectedRoundIndex.value].criticText;
  }
  return '';
});

const formattedActiveActor = computed(() => {
  if (!activeThinkingActor.value) return '';
  return formatDiffText(activeThinkingActor.value);
});

const formattedActiveCritic = computed(() => {
  if (!activeThinkingCritic.value) return '';
  return formatDiffText(activeThinkingCritic.value);
});

const modeLabel = computed(() => {
  const route = router.currentRoute.value.path;
  const labels: Record<string, string> = {
    '/chat': '💬 通用对话',
    '/meeting': '🎙️ 会议纪要',
    '/literature': '📚 文献摘要',
    '/polish': '✍️ 多语言润色',
    '/ppt': '📊 PPT生成',
    '/tasks': '📋 任务中心',
    '/skills': '🧩 Skills',
  };
  return labels[route] || '💬 通用对话';
});

function selectRound(idx: number) {
  if (store.actorText || store.criticText) return;
  selectedRoundIndex.value = idx;
}

watch(() => store.conversationRounds.length, (newLen) => {
  if (newLen > 0) {
    selectedRoundIndex.value = newLen - 1;
  }
});

watch(() => store.actorText, (newVal) => {
  if (newVal) {
    selectedRoundIndex.value = -1;
  }
  nextTick(() => {
    if (thinkingPanelRef.value) {
      thinkingPanelRef.value.scrollTop = thinkingPanelRef.value.scrollHeight;
    }
  });
});

watch(() => store.criticText, () => {
  nextTick(() => {
    if (thinkingPanelRef.value) {
      thinkingPanelRef.value.scrollTop = thinkingPanelRef.value.scrollHeight;
    }
  });
});

watch(() => store.transcriptText, () => {
  nextTick(() => {
    if (thinkingPanelRef.value) {
      thinkingPanelRef.value.scrollTop = thinkingPanelRef.value.scrollHeight;
    }
  });
});

watch(() => store.reactText, () => {
  nextTick(() => {
    if (thinkingPanelRef.value) {
      thinkingPanelRef.value.scrollTop = thinkingPanelRef.value.scrollHeight;
    }
  });
});

watch(selectedRoundIndex, () => {
  nextTick(() => {
    if (thinkingPanelRef.value) {
      thinkingPanelRef.value.scrollTop = 0;
    }
  });
});

const showInitOverlay = computed(() => {
  if (store.offlineMode) return false;
  return store.initialized === false;
});

const coreNavItems = [
  { path: '/', icon: '🏠', label: '仪表盘' },
  { path: '/chat', icon: '💬', label: '通用对话' },
  { path: '/meeting', icon: '📝', label: '会议纪要' },
  { path: '/literature', icon: '📚', label: '文献摘要' },
  { path: '/polish', icon: '✨', label: '多语言润色' },
  { path: '/ppt', icon: '📊', label: 'PPT生成' },
];

const taskTypeLabels: Record<string, string> = {
  chat: '通用对话',
  meeting: '会议纪要',
  literature: '文献摘要',
  polish: '多语言润色',
  ppt: 'PPT生成',
  xlsx: 'Excel生成',
  docx: '文档生成',
};

const taskTypeBadgeClasses: Record<string, string> = {
  chat: 'bg-blue-100 text-blue-600',
  meeting: 'bg-green-100 text-green-600',
  literature: 'bg-purple-100 text-purple-600',
  polish: 'bg-yellow-100 text-yellow-600',
  ppt: 'bg-red-100 text-red-600',
  xlsx: 'bg-emerald-100 text-emerald-600',
  docx: 'bg-indigo-100 text-indigo-600',
};

function taskTypeLabel(type: string) {
  return taskTypeLabels[type] || type;
}

function taskTypeBadgeClass(type: string) {
  return taskTypeBadgeClasses[type] || 'bg-gray-100 text-gray-600';
}

const currentPageTitle = computed(() => {
  const pageTitles: Record<string, string> = {
    '/': '🏠 仪表盘',
    '/chat': '💬 通用对话',
    '/meeting': '📝 会议纪要',
    '/literature': '📚 文献摘要',
    '/polish': '✨ 多语言润色',
    '/ppt': '📊 PPT 生成',
    '/tasks': '📋 任务中心',
    '/skills': '🧩 Skills 扩展',
  };
  return pageTitles[route.path] || 'LVV';
});

const isFullPanelMode = computed(() => {
  return route.path === '/' || route.path === '/tasks' || route.path === '/skills';
});

const fullPanelTitle = computed(() => {
  const titles: Record<string, string> = {
    '/tasks': '📋 任务中心',
    '/skills': '🧩 Skills 扩展',
  };
  return titles[route.path] || '';
});

function goBack() {
  router.back();
}

function isActive(path: string) {
  return route.path === path;
}

async function switchMode(path: string) {
  if (route.path === path) return;
  if (store.isProcessing) {
    store.isProcessing = false;
    store.resetStream();
  }
  store.actorText = '';
  store.criticText = '';
  store.finalOutput = '';
  store.lastUserMessage = '';
  store.workflowSteps = [];
  store.conversationRounds = [];
  store.thinkingHistory = [];
  const taskTypeMap: Record<string, string> = {
    '/': 'chat',
    '/chat': 'chat',
    '/meeting': 'meeting',
    '/literature': 'literature',
    '/polish': 'polish',
    '/ppt': 'ppt',
  };
  const taskType = taskTypeMap[path] || 'chat';
  await store.startNewConversation(taskType);
  router.push(path);
}

function handleClickOutside(e: MouseEvent) {
  if (moreMenuRef.value && !moreMenuRef.value.contains(e.target as Node)) {
    showMoreMenu.value = false;
  }
}

function handleGlobalDragLeave(event: DragEvent) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  const x = event.clientX;
  const y = event.clientY;
  if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
    globalDragging.value = false;
  }
}

async function handleGlobalDrop(event: DragEvent) {
  globalDragging.value = false;
  const files = event.dataTransfer?.files;
  if (!files || files.length === 0) return;
  const currentRoute = window.location.pathname;
  let mode = 'chat';
  if (currentRoute.includes('meeting')) mode = 'meeting';
  else if (currentRoute.includes('literature')) mode = 'literature';
  else if (currentRoute.includes('polish')) mode = 'polish';
  else if (currentRoute.includes('ppt')) mode = 'ppt';
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const validationError = validateUploadFile(file);
    if (validationError) {
      alert(validationError);
      continue;
    }
    try {
      const res = await apiClient.uploadFile(file, mode, store.currentConvId || undefined, undefined, () => {});
      store.droppedFileInfo = {
        filename: res.data.filename,
        file_path: res.data.file_path,
        stored_filename: res.data.stored_filename || res.data.file_path.split(/[/\\]/).pop() || res.data.filename,
        relative_path: res.data.relative_path,
      };
    } catch (e) {
      console.error('Global file drop upload failed:', e);
    }
  }
}

function startResizeLeft(e: MouseEvent) {
  resizingLeft.value = true;
  const startX = e.clientX;
  const startWidth = leftPanelWidth.value;
  const containerWidth = (e.currentTarget as HTMLElement).parentElement!.clientWidth;

  function onMouseMove(ev: MouseEvent) {
    const diff = ev.clientX - startX;
    const newWidth = startWidth + (diff / containerWidth) * 100;
    leftPanelWidth.value = Math.max(15, Math.min(50, newWidth));
  }
  function onMouseUp() {
    resizingLeft.value = false;
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }
  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

function startResizeRight(e: MouseEvent) {
  resizingRight.value = true;
  const startX = e.clientX;
  const startWidth = rightLeftWidth.value;
  const containerWidth = (e.currentTarget as HTMLElement).parentElement!.clientWidth;

  function onMouseMove(ev: MouseEvent) {
    const diff = ev.clientX - startX;
    const newWidth = startWidth + (diff / containerWidth) * 100;
    rightLeftWidth.value = Math.max(15, Math.min(70, newWidth));
  }
  function onMouseUp() {
    resizingRight.value = false;
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }
  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

function startResizeInput(e: MouseEvent) {
  resizingInput.value = true;
  const startY = e.clientY;
  const startHeight = inputAreaHeight.value;

  function onMouseMove(ev: MouseEvent) {
    const diff = startY - ev.clientY;
    const newHeight = startHeight + diff;
    inputAreaHeight.value = Math.max(80, Math.min(500, newHeight));
  }
  function onMouseUp() {
    resizingInput.value = false;
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }
  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

async function retryInit() {
  retrying.value = true;
  await store.checkInitStatus();
  retrying.value = false;
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
  store.checkInitStatus();
  store.startHealthPolling();
});

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside);
  store.stopHealthPolling();
});

async function handleNewConversation() {
  const taskTypeMap: Record<string, string> = {
    '/chat': 'chat',
    '/meeting': 'meeting',
    '/literature': 'literature',
    '/polish': 'polish',
    '/ppt': 'ppt',
  };
  const taskType = taskTypeMap[route.path] || 'chat';
  await store.startNewConversation(taskType);
}

async function handleRollback() {
  if (!store.currentConvId || store.isProcessing) return;
  if (confirm('确定回退上一轮对话？')) {
    await store.rollbackConversation();
  }
}

async function handleRegenerate() {
  if (!store.currentConvId || store.isProcessing) return;
  const lastMessage = await store.regenerateLastResponse();
  if (lastMessage) {
    store.resetStream();
    store.isProcessing = true;
    store.clearWorkflow();
    store.addWorkflowStep('重新生成');
    store.addWorkflowStep('Actor 生成回复');
    store.addWorkflowStep('Critic 审查');
    store.addWorkflowStep('修正与输出');

    try {
      const streamUrl = getStreamUrlForType(store.currentConvType);
      if (!streamUrl) return;

      store.updateWorkflowStep(0, 'completed');
      store.updateWorkflowStep(1, 'active');

      for await (const event of streamPost(streamUrl, getStreamBodyForType(store.currentConvType, lastMessage))) {
        if (event.type === 'stream' && event.role === 'actor') {
          store.actorText += event.content || '';
        } else if (event.type === 'stream' && event.role === 'critic') {
          store.criticText += event.content || '';
          if (store.workflowSteps[2]?.status !== 'completed') {
            store.updateWorkflowStep(1, 'completed');
            store.updateWorkflowStep(2, 'active');
          }
        } else if (event.type === 'title_generated') {
          if (event.conv_id && event.title) {
            store.loadConversations();
          }
        } else if (event.type === 'actor_done') {
          if (event.title) {
            store.loadConversations();
          }
        } else if (event.type === 'complete') {
          store.updateWorkflowStep(2, 'completed');
          store.updateWorkflowStep(3, 'completed');
          store.finalOutput = event.output || store.actorText;
          store.isProcessing = false;
          store.saveMessage('actor', store.finalOutput).then(() => {
            store.saveMessage('critic', store.criticText).then(() => {
              store.loadConversations();
            });
          }).catch((e: any) => console.error('Save failed:', e));
        }
      }
    } catch (e) {
      console.error('Regenerate failed:', e);
    } finally {
      store.isProcessing = false;
    }
  }
}

function getStreamUrlForType(type: string): string {
  const urlMap: Record<string, string> = {
    chat: '/chat/stream',
    meeting: '/meeting/minutes/stream',
    literature: '/literature/summarize/stream',
    polish: '/polish/stream',
    ppt: '/ppt/generate/stream',
    xlsx: '/xlsx/generate/stream',
    docx: '/docx/generate/stream',
  };
  return urlMap[type] || '/chat/stream';
}

function getStreamBodyForType(type: string, message: string): any {
  const bodyMap: Record<string, any> = {
    chat: { message },
    meeting: { transcript: message, language: 'auto' },
    literature: { file_path: message, query: '请生成这篇文献的详细摘要' },
    polish: { text: message, target_language: 'auto', style: 'academic' },
    ppt: { topic: message, content: '', style: 'academic', template: 'default' },
    xlsx: { topic: message, content: '' },
    docx: { topic: message, content: '', style: 'default' },
  };
  return bodyMap[type] || { message };
}

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

const formattedFinalOutput = computed(() => {
  if (!store.finalOutput) return '';
  return formatDiffText(store.finalOutput);
});

function formatText(raw: string): string {
  if (!raw) return '';
  return formatDiffText(raw);
}

function formatDialogTime(ts: string | null): string {
  try {
    const d = ts ? new Date(ts) : new Date();
    const h = d.getHours().toString().padStart(2, '0');
    const m = d.getMinutes().toString().padStart(2, '0');
    const s = d.getSeconds().toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
  } catch { return ''; }
}

function formatIcon(fmt: string): string {
  const icons: Record<string, string> = { md: '📝', html: '🌐', txt: '📄', pdf: '📄', docx: '📃', xlsx: '📊', pptx: '📊', wav: '🎵', mp3: '🎵', webm: '🎵', csv: '📊' };
  return icons[fmt] || '📄';
}

function getFileDownloadUrl(file: any): string {
  if (file.relative_path) {
    const cleanPath = String(file.relative_path).replace(/\\/g, '/');
    return `/api/files/download/${cleanPath}`;
  }
  if (file.download_url) {
    return file.download_url.startsWith('/') ? `/api${file.download_url}` : file.download_url;
  }
  const storedName = file.stored_filename || file.filename;
  const mode = store.currentConvType || 'chat';
  const convId = store.currentConvId || '';
  return `/api/chat/download/${storedName}?mode=${mode}&conv_id=${convId}`;
}

function getRefFileDownloadUrl(refFile: any): string {
  if (refFile.relative_path) {
    const cleanPath = String(refFile.relative_path).replace(/\\/g, '/');
    return `/api/files/download/${cleanPath}`;
  }
  if (refFile.download_url) {
    const url = refFile.download_url.startsWith('/') ? refFile.download_url : `/${refFile.download_url}`;
    return refFile.download_url.startsWith('/api/') ? refFile.download_url : `/api${url}`;
  }
  const path = refFile.stored_filename || refFile.filename;
  if (path) {
    return `/api/files/download/${path}`;
  }
  return '#';
}

const currentConvFiles = computed(() => {
  if (!store.currentConvId) return [];
  return store.generatedFiles.filter(f => f.conv_id === store.currentConvId);
});
</script>
