<template>
  <div
    class="relative p-4 space-y-4"
    @dragover.prevent="isDragging = true"
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleZipDrop"
  >
    <div
      v-if="isDragging"
      class="absolute inset-0 z-10 bg-primary-50/80 border-2 border-dashed border-primary-400 rounded-lg flex items-center justify-center"
    >
      <span class="text-primary-600 text-sm font-medium">📥 松开即可导入 Skill</span>
    </div>

    <div class="flex items-center justify-between">
      <h2 class="text-sm font-semibold text-gray-700">🧩 Skills 扩展</h2>
      <div class="flex items-center space-x-2">
        <button
          @click="showImportMenu = !showImportMenu"
          class="px-3 py-1.5 text-xs bg-primary-500 text-white rounded-md hover:bg-primary-600 transition-colors"
        >
          ＋导入 Skill
        </button>
        <button
          @click="reloadSkills"
          class="px-3 py-1.5 text-xs bg-gray-100 text-gray-600 rounded-md hover:bg-gray-200 transition-colors"
        >
          🔄 刷新
        </button>
      </div>
    </div>

    <div v-if="showImportMenu" class="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
      <p class="text-xs text-blue-600 font-medium">导入 Skill</p>

      <div class="space-y-1.5">
        <p class="text-[10px] text-gray-500">方式一：上传 Skill 文件（也可拖拽到页面任意位置，支持 .zip .md .py 等所有格式）</p>
        <div class="flex items-center space-x-2">
          <input ref="zipInput" type="file" @change="handleZipUpload" class="hidden" :disabled="importing" />
          <button
            @click="($refs.zipInput as any)?.click()"
            :disabled="importing"
            class="px-3 py-1.5 text-xs bg-blue-100 text-blue-600 rounded-md hover:bg-blue-200 disabled:opacity-50 transition-colors"
          >
            {{ importing ? '导入中...' : '📁 选择 Skill 文件' }}
          </button>
          <input ref="folderInput" type="file" webkitdirectory @change="handleFolderUpload" class="hidden" :disabled="importing" />
          <button
            @click="($refs.folderInput as any)?.click()"
            :disabled="importing"
            class="px-3 py-1.5 text-xs bg-blue-100 text-blue-600 rounded-md hover:bg-blue-200 disabled:opacity-50 transition-colors"
          >
            {{ importing ? '导入中...' : '📂 选择文件夹' }}
          </button>
        </div>
        <div v-if="skillUploadProgress > 0 && skillUploadProgress < 100" class="mt-1.5 w-full bg-gray-200 rounded-full h-1.5">
          <div class="bg-primary-500 h-1.5 rounded-full transition-all duration-300" :style="{ width: skillUploadProgress + '%' }"></div>
        </div>
        <div v-if="skillUploadProgress > 0 && skillUploadProgress < 100" class="text-[10px] text-primary-500 mt-0.5">上传中 {{ skillUploadProgress }}%</div>
      </div>

      <div class="relative">
        <div class="absolute inset-0 flex items-center"><div class="w-full border-t border-blue-200"></div></div>
        <div class="relative flex justify-center"><span class="bg-blue-50 px-2 text-[10px] text-blue-400">或</span></div>
      </div>

      <div class="space-y-1.5">
        <p class="text-[10px] text-gray-500">方式二：从 Git 仓库导入（GitHub / GitCode / Gitee 等）</p>
        <div class="flex items-center space-x-2">
          <input
            v-model="gitUrl"
            type="text"
            placeholder="https://github.com/user/skill-repo"
            class="flex-1 px-3 py-1.5 text-xs border rounded-md focus:outline-none focus:ring-1 focus:ring-primary-500"
            @keyup.enter="importFromGit"
          />
          <button
            @click="importFromGit"
            :disabled="!gitUrl.trim() || importing"
            class="px-3 py-1.5 text-xs bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 transition-colors whitespace-nowrap"
          >
            {{ importing ? '导入中...' : '🔗 从 Git 导入' }}
          </button>
        </div>
        <div v-if="gitUrl.trim()" class="flex items-center space-x-2">
          <input
            v-model="gitSubpath"
            type="text"
            placeholder="子路径（可选，如 skills/my-skill）"
            class="flex-1 px-2 py-1 text-[10px] border rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
          <select v-model="gitBranch" class="px-2 py-1 text-[10px] border rounded focus:outline-none">
            <option value="main">main</option>
            <option value="master">master</option>
          </select>
        </div>
      </div>

      <div v-if="importMessage" class="rounded-md p-2 text-xs" :class="importSuccess ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'">
        {{ importMessage }}
      </div>

      <div v-if="importScanResult" class="bg-gray-50 border rounded-md p-2 text-xs space-y-1">
        <p class="font-medium text-gray-600">═══ 安全评估报告 ═══</p>
        <div class="flex items-center space-x-3">
          <span>来源信任:
            <span v-if="importTrustLevel === 'verified'" class="text-green-600">✅ 官方验证</span>
            <span v-else-if="importTrustLevel === 'community'" class="text-yellow-600">🟡 社区来源</span>
            <span v-else-if="importTrustLevel === 'untrusted'" class="text-red-600">🔴 不受信任</span>
            <span v-else class="text-gray-500">⚪ 未知来源</span>
          </span>
          <span>风险等级:
            <span v-if="importScanResult.risk_level === 'low'" class="text-green-600">🟢 低风险</span>
            <span v-else-if="importScanResult.risk_level === 'medium'" class="text-yellow-600">🟡 中风险</span>
            <span v-else-if="importScanResult.risk_level === 'high'" class="text-red-600">🔴 高风险</span>
          </span>
        </div>
        <div v-if="importScanResult.warnings && importScanResult.warnings.length">
          <p class="text-yellow-600">⚠️ 警告:</p>
          <p v-for="w in importScanResult.warnings" :key="w" class="text-yellow-600 ml-2">- {{ w }}</p>
        </div>
        <div v-if="importScanResult.network_calls && importScanResult.network_calls.length" class="text-blue-600">
          🌐 网络请求: {{ importScanResult.network_calls.join(', ') }}
        </div>
        <div v-if="importScanResult.file_operations && importScanResult.file_operations.length" class="text-blue-600">
          📁 文件操作: {{ importScanResult.file_operations.join(', ') }}
        </div>
      </div>

      <p class="text-[10px] text-amber-600">⚠️ 仅导入可信来源的 Skill，恶意 Skill 可能造成安全风险</p>
    </div>

    <div v-if="loading" class="text-center py-8 text-gray-400 text-xs">加载中...</div>

    <div v-else-if="skills.length === 0" class="text-center py-8">
      <p class="text-gray-400 text-xs">暂无可用 Skill</p>
      <p class="text-gray-300 text-[10px] mt-1">点击上方"＋导入 Skill"添加新的扩展能力</p>
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="skill in skills"
        :key="skill.name"
        class="bg-white border rounded-lg p-3 hover:shadow-sm transition-shadow"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center space-x-2">
              <span class="text-lg">{{ skill.icon || '🧩' }}</span>
              <span class="text-sm font-medium text-gray-800">{{ skill.name }}</span>
              <span class="text-[10px] px-1.5 py-0.5 rounded-full" :class="skill.type === 'prompt' ? 'bg-purple-100 text-purple-600' : 'bg-green-100 text-green-600'">
                {{ skill.type === 'prompt' ? 'Prompt' : 'Function' }}
              </span>
              <span class="text-[10px] text-gray-400">v{{ skill.version }}</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">{{ skill.description }}</p>
            <div v-if="skill.tags && skill.tags.length" class="flex flex-wrap gap-1 mt-1.5">
              <span v-for="tag in skill.tags" :key="tag" class="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
                {{ tag }}
              </span>
            </div>
          </div>
          <div class="flex items-center space-x-1 ml-2">
            <button
              @click="openExecutePanel(skill)"
              class="px-2 py-1 text-[10px] bg-primary-50 text-primary-600 rounded hover:bg-primary-100 transition-colors"
            >
              ▶ 执行
            </button>
            <button
              @click="deleteSkill(skill.name)"
              class="px-2 py-1 text-[10px] bg-red-50 text-red-500 rounded hover:bg-red-100 transition-colors"
            >
              ✕
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="executingSkill" class="fixed inset-0 bg-black/30 flex items-center justify-center z-50" @click.self="executingSkill = null">
      <div class="bg-white rounded-xl shadow-xl w-[500px] max-h-[80vh] overflow-y-auto p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-gray-800">
            {{ executingSkill.icon || '🧩' }} {{ executingSkill.name }}
          </h3>
          <button @click="executingSkill = null" class="text-gray-400 hover:text-gray-600">✕</button>
        </div>
        <p class="text-xs text-gray-500">{{ executingSkill.description }}</p>

        <div class="space-y-2">
          <div v-for="(field, key) in executingSkill.input_schema" :key="key" class="space-y-1">
            <label class="text-xs font-medium text-gray-600">
              {{ field.description || key }}
              <span v-if="field.required" class="text-red-400">*</span>
            </label>
            <textarea
              v-if="field.type === 'string'"
              v-model="executeContext[key]"
              :placeholder="field.default || ''"
              class="w-full px-3 py-2 text-xs border rounded-md focus:outline-none focus:ring-1 focus:ring-primary-500 min-h-[80px]"
            ></textarea>
            <input
              v-else
              v-model="executeContext[key]"
              :placeholder="field.default || ''"
              class="w-full px-3 py-2 text-xs border rounded-md focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
        </div>

        <div class="flex items-center space-x-2">
          <button
            @click="executeSkillAction"
            :disabled="executing"
            class="flex-1 px-4 py-2 text-xs bg-primary-500 text-white rounded-md hover:bg-primary-600 disabled:opacity-50 transition-colors"
          >
            {{ executing ? '执行中...' : '▶ 执行 Skill' }}
          </button>
        </div>

        <div v-if="executeResult" class="space-y-2">
          <h4 class="text-xs font-semibold text-green-600">执行结果</h4>
          <div class="bg-green-50 rounded-lg p-3 text-xs text-gray-700 whitespace-pre-wrap max-h-[300px] overflow-y-auto">
            {{ typeof executeResult === 'string' ? executeResult : JSON.stringify(executeResult, null, 2) }}
          </div>
        </div>

        <div v-if="executeError" class="space-y-2">
          <h4 class="text-xs font-semibold text-red-600">错误</h4>
          <div class="bg-red-50 rounded-lg p-3 text-xs text-red-700">
            {{ executeError }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { apiClient } from '../utils/api';

const skills = ref<any[]>([]);
const loading = ref(false);
const showImportMenu = ref(false);
const gitUrl = ref('');
const gitBranch = ref('main');
const gitSubpath = ref('');
const importing = ref(false);
const importMessage = ref('');
const importSuccess = ref(false);
const importScanResult = ref<any>(null);
const importTrustLevel = ref('');
const executingSkill = ref<any>(null);
const executeContext = ref<Record<string, any>>({});
const executing = ref(false);
const executeResult = ref<any>(null);
const executeError = ref('');
const isDragging = ref(false);
const skillUploadProgress = ref(0);

function clearImportMessage() {
  importMessage.value = '';
  importSuccess.value = false;
  importScanResult.value = null;
  importTrustLevel.value = '';
}

async function loadSkills() {
  loading.value = true;
  try {
    const res = await apiClient.listSkills();
    skills.value = res.data.skills || [];
  } catch (e) {
    console.error('Failed to load skills:', e);
  } finally {
    loading.value = false;
  }
}

async function reloadSkills() {
  try {
    await apiClient.reloadSkills();
    await loadSkills();
  } catch (e) {
    console.error('Failed to reload skills:', e);
  }
}

function handleDragLeave(event: DragEvent) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  const x = event.clientX;
  const y = event.clientY;
  if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
    isDragging.value = false;
  }
}

async function handleZipDrop(event: DragEvent) {
  isDragging.value = false;
  const files = event.dataTransfer?.files;
  if (!files) return;
  if (files.length === 1) {
    await importZipFile(files[0]);
    return;
  }
  await importFolderFiles(files);
}

async function handleZipUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  if (!input.files || !input.files[0]) return;
  await importZipFile(input.files[0]);
  input.value = '';
}

async function handleFolderUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  if (!input.files || input.files.length === 0) return;
  await importFolderFiles(input.files);
  input.value = '';
}

async function importFolderFiles(files: FileList | File[]) {
  importing.value = true;
  skillUploadProgress.value = 5;
  clearImportMessage();
  try {
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const relativePath = (file as any).webkitRelativePath || file.name;
      formData.append('files', file, relativePath);
    }
    const res = await apiClient.importSkillFromFolder(formData, (progress: number) => {
      skillUploadProgress.value = Math.round(progress);
    });
    const data = res.data;
    importScanResult.value = data.scan_result || null;
    importTrustLevel.value = data.trust_level || 'unknown';
    importMessage.value = `✅ Skill "${data.skill_name}" 导入成功`;
    importSuccess.value = true;
    skillUploadProgress.value = 100;
    setTimeout(() => { skillUploadProgress.value = 0; }, 1000);
    await loadSkills();
  } catch (e: any) {
    importMessage.value = '导入失败: ' + (e.response?.data?.detail || e.message);
    importSuccess.value = false;
    skillUploadProgress.value = 0;
  } finally {
    importing.value = false;
  }
}

async function importZipFile(file: File) {
  importing.value = true;
  skillUploadProgress.value = 5;
  clearImportMessage();
  try {
    const res = await apiClient.importSkillFromZip(file, (progress) => {
      skillUploadProgress.value = Math.round(progress);
    });
    const data = res.data;
    importScanResult.value = data.scan_result || null;
    importTrustLevel.value = data.trust_level || 'unknown';
    importMessage.value = `✅ Skill "${data.skill_name}" 导入成功`;
    importSuccess.value = true;
    skillUploadProgress.value = 100;
    setTimeout(() => { skillUploadProgress.value = 0; }, 1000);
    await loadSkills();
  } catch (e: any) {
    importMessage.value = '导入失败: ' + (e.response?.data?.detail || e.message);
    importSuccess.value = false;
    skillUploadProgress.value = 0;
  } finally {
    importing.value = false;
  }
}

async function importFromGit() {
  if (!gitUrl.value.trim()) return;

  importing.value = true;
  skillUploadProgress.value = 5;
  clearImportMessage();
  try {
    const progressInterval = setInterval(() => {
      if (skillUploadProgress.value < 90) {
        skillUploadProgress.value += 3;
      }
    }, 500);
    const res = await apiClient.importSkillFromGit(gitUrl.value.trim(), gitBranch.value, gitSubpath.value.trim());
    clearInterval(progressInterval);
    skillUploadProgress.value = 100;
    const data = res.data;
    importScanResult.value = data.scan_result || null;
    importTrustLevel.value = data.trust_level || 'unknown';
    importMessage.value = `✅ Skill "${data.skill_name}" 从 Git 导入成功`;
    importSuccess.value = true;
    setTimeout(() => { skillUploadProgress.value = 0; }, 1000);
    await loadSkills();
    gitUrl.value = '';
    gitSubpath.value = '';
  } catch (e: any) {
    skillUploadProgress.value = 0;
    importMessage.value = '导入失败: ' + (e.response?.data?.detail || e.message);
    importSuccess.value = false;
  } finally {
    importing.value = false;
  }
}

async function deleteSkill(name: string) {
  if (!confirm(`确定删除 Skill "${name}"？`)) return;
  try {
    await apiClient.deleteSkill(name);
    await loadSkills();
  } catch (e) {
    console.error('Failed to delete skill:', e);
  }
}

function openExecutePanel(skill: any) {
  executingSkill.value = skill;
  executeContext.value = {};
  executeResult.value = null;
  executeError.value = '';

  if (skill.input_schema) {
    for (const [key, field] of Object.entries(skill.input_schema)) {
      const f = field as any;
      executeContext.value[key] = f.default || '';
    }
  }
}

async function executeSkillAction() {
  if (!executingSkill.value) return;

  executing.value = true;
  executeResult.value = null;
  executeError.value = '';

  try {
    const res = await apiClient.executeSkill(executingSkill.value.name, executeContext.value);
    executeResult.value = res.data.output || res.data;
  } catch (e: any) {
    executeError.value = e.response?.data?.detail || e.message || '执行失败';
  } finally {
    executing.value = false;
  }
}

onMounted(() => {
  loadSkills();
});
</script>
