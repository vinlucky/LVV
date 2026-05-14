#!/usr/bin/env node

import * as dotenv from 'dotenv';
import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';
import axios from 'axios';
import chalk from 'chalk';
import { Command } from 'commander';
import inquirer from 'inquirer';

dotenv.config({ path: process.env.ENV_FILE || path.resolve(__dirname, '../../.env') });

const AI_CORE_URL = process.env.AI_CORE_URL || `http://localhost:${process.env.AI_CORE_PORT || 8000}`;
const GATEWAY_URL = process.env.GATEWAY_URL || AI_CORE_URL;
const ENV_PATH = process.env.ENV_FILE || path.resolve(__dirname, '../../.env');
const ENV_EXAMPLE_PATH = path.resolve(__dirname, '../../.env.example');

const api = axios.create({ baseURL: GATEWAY_URL, timeout: 120000 });

let currentConvId: string | null = null;
let currentConvType: string | null = null;

const taskTypeLabels: Record<string, string> = {
  chat: '💬 通用对话',
  meeting: '📝 会议纪要',
  literature: '📚 文献摘要',
  polish: '✨ 多语言润色',
  ppt: '📊 PPT生成',
  general: '🤖 通用模式',
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function printBanner() {
  const banner = chalk.cyan.bold(`
  ██╗     ██╗   ██╗██╗   ██╗██╗  ██╗
  ██║     ██║   ██║██║   ██║╚██╗██╔╝
  ██║     ██║   ██║██║   ██║ ╚███╔╝
  ███████╗╚██████╔╝╚██████╔╝ ██╔██╗
  ╚══════╝ ╚═════╝  ╚═════╝  ╚═╝ ╚╝
`) + chalk.magenta.bold(`
        L o v e   W o r k i n g
`) + chalk.yellow.bold(`
            [ CLI ]
`) + chalk.gray('  ─────────────────────────────────────\n') +
    chalk.white('  Your AI Office Assistant  |  v1.0.0\n');
  console.log(banner);
}

function printConvStatus() {
  if (currentConvId) {
    const typeLabel = taskTypeLabels[currentConvType || ''] || currentConvType || '未知';
    console.log(chalk.cyan(`📌 当前对话: ${currentConvId.slice(0, 8)}... | 类型: ${typeLabel}\n`));
  } else {
    console.log(chalk.gray('📌 当前无活跃对话\n'));
  }
}

function loadEnv(): Record<string, string> {
  if (!fs.existsSync(ENV_PATH)) return {};
  const content = fs.readFileSync(ENV_PATH, 'utf-8');
  const env: Record<string, string> = {};
  content.split('\n').forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) return;
    const eqIndex = trimmed.indexOf('=');
    if (eqIndex === -1) return;
    const key = trimmed.slice(0, eqIndex).trim();
    const value = trimmed.slice(eqIndex + 1).trim();
    if (value) env[key] = value;
  });
  return env;
}

function hasApiKey(env: Record<string, string>): boolean {
  const provider = env.DEFAULT_PROVIDER || 'qwen';
  if (provider === 'mock') return true;
  if (provider === 'qwen') return !!env.QWEN_API_KEY;
  if (provider === 'tencent') return !!env.TENCENT_API_KEY;
  return !!env.QWEN_API_KEY || !!env.TENCENT_API_KEY;
}

function saveEnv(key: string, value: string) {
  let content = '';
  if (!fs.existsSync(ENV_PATH)) {
    if (fs.existsSync(ENV_EXAMPLE_PATH)) {
      fs.copyFileSync(ENV_EXAMPLE_PATH, ENV_PATH);
    }
  }
  if (fs.existsSync(ENV_PATH)) {
    content = fs.readFileSync(ENV_PATH, 'utf-8');
  }
  const regex = new RegExp(`^${key}=.*$`, 'm');
  if (regex.test(content)) {
    content = content.replace(regex, `${key}=${value}`);
  } else {
    content += `\n${key}=${value}`;
  }
  fs.writeFileSync(ENV_PATH, content.trim() + '\n');
}

async function createConversation(taskType: string, initialMessage?: string): Promise<string | null> {
  try {
    const res = await api.post('/conversations', { task_type: taskType, initial_message: initialMessage });
    currentConvId = res.data.conv_id;
    currentConvType = taskType;
    return res.data.conv_id;
  } catch (e) {
    return null;
  }
}

async function saveMessage(convId: string, role: string, content: string) {
  try {
    await api.post('/conversations/message', { conv_id: convId, role, content });
  } catch (e) {
    // ignore
  }
}

async function ensureConversation(taskType: string, userInput?: string, forceNew: boolean = false) {
  if (forceNew || !currentConvId || currentConvType !== taskType) {
    const convId = await createConversation(taskType, userInput);
    if (!convId) {
      console.log(chalk.red('❌ 创建对话失败，请检查后端服务是否运行'));
    }
  } else {
    if (userInput) {
      await saveMessage(currentConvId!, 'user', userInput);
    }
  }
}

async function streamPost(
  url: string,
  body: any,
  taskType?: string,
  userInput?: string,
  forceNew: boolean = false,
) {
  if (taskType) {
    await ensureConversation(taskType, userInput, forceNew);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000);

  let response: Response;
  try {
    response = await fetch(GATEWAY_URL + url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    console.log(chalk.red(`\n❌ 请求失败: HTTP ${response.status} ${response.statusText}`));
    return;
  }

  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let actorText = '';
  let criticText = '';
  let finalOutput = '';
  let completeReceived = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim();
        if (data === '[DONE]') {
          const output = finalOutput || actorText;
          if (!completeReceived) {
            console.log(chalk.green('\n===\n' + output));
          }
          if (currentConvId) {
            const convId = currentConvId!;
            saveMessage(convId, 'actor', output).then(() => {
              if (criticText) {
                saveMessage(convId, 'critic', criticText);
              }
            }).catch((e: any) => console.error('Save failed:', e));
          }
          return;
        }
        try {
          const event = JSON.parse(data);
          if (event.type === 'stream' && event.role === 'actor' && event.content) {
            process.stdout.write(chalk.blue(event.content));
            actorText += event.content;
          } else if (event.type === 'stream' && event.role === 'critic' && event.content) {
            process.stdout.write(chalk.yellow(event.content));
            criticText += event.content;
          } else if (event.type === 'step' && event.message) {
            console.log(chalk.blue(`\n${event.message}`));
          } else if (event.type === 'file_generated' && event.file) {
            console.log(chalk.cyan(`\n📁 文件已生成: ${event.file.file_name}.${event.file.file_format} (${formatFileSize(event.file.file_size)})`));
            console.log(chalk.cyan(`   下载: ${GATEWAY_URL}${event.file.download_url}\n`));
          } else if (event.type === 'mode_suggestion') {
            const modeNames: Record<string, string> = {
              literature: '📚 文献摘要',
              meeting: '🎙️ 会议纪要',
              polish: '✍️ 多语言润色',
              ppt: '📊 PPT生成',
            };
            const modeCmds: Record<string, string> = {
              literature: 'lvv literature',
              meeting: 'lvv meeting',
              polish: 'lvv polish',
              ppt: 'lvv ppt',
            };
            const modeName = modeNames[event.suggested_mode] || event.suggested_mode;
            const modeCmd = modeCmds[event.suggested_mode] || `lvv ${event.suggested_mode}`;
            console.log(chalk.magenta(`\n💡 AI 建议：${event.reason}`));
            console.log(chalk.magenta(`   您可以运行 ${chalk.bold(modeCmd)} 切换到${modeName}模式\n`));
          } else if (event.type === 'actor_done') {
            console.log(chalk.blue(`\n✅ Actor 输出完成（剩余循环次数: ${event.remaining_iterations ?? '未知'}）`));
          } else if (event.type === 'title_generated') {
            if (event.conv_id && event.title) {
              console.log(chalk.gray(`\n📝 对话标题已自动生成: ${event.title}`));
            }
          } else if (event.type === 'critic_done') {
            if (event.approved) {
              console.log(chalk.green(`\n✅ Critic 审查通过，即将输出正式结果...`));
            } else {
              console.log(chalk.yellow(`\n⚠️ Critic 审查未通过，Actor 将重新生成...`));
            }
          } else if (event.type === 'complete') {
            completeReceived = true;
            finalOutput = event.output || actorText;
            console.log(chalk.green('\n===\n' + finalOutput));
            if (currentConvId) {
              const convId = currentConvId!;
              saveMessage(convId, 'actor', finalOutput).then(() => {
                if (criticText) {
                  saveMessage(convId, 'critic', criticText);
                }
              }).catch((e: any) => console.error('Save failed:', e));
            }
            return;
          } else if (event.type === 'skill_imported') {
            console.log(chalk.green(`\n✅ Skill "${event.skill_name}" 已成功导入！\n`));
          } else if (event.type === 'lang_mismatch') {
            reader.cancel();
            completeReceived = true;
            const sourceLang = event.source_language_name || event.source_language;
            const targetLang = event.target_language_name || event.target_language;
            console.log(chalk.yellow(`\n⚠️ ${event.message || `检测到原文语言为 ${sourceLang}，但目标语言选择了 ${targetLang}`}`));
            const { doTranslate } = await inquirer.prompt([
              {
                type: 'list',
                name: 'doTranslate',
                message: '是否需要翻译？',
                choices: [
                  { name: `✅ 确认，翻译为 ${targetLang}`, value: 'translate' },
                  { name: `📝 使用原文语言（${sourceLang}）仅润色不翻译`, value: 'polish_only' },
                  { name: '❌ 取消', value: 'cancel' },
                ],
              },
            ]);
            if (doTranslate === 'cancel') {
              console.log(chalk.gray('已取消\n'));
              return;
            }
            const resolvedLang = doTranslate === 'translate' ? event.target_language : (event.source_language || 'auto');
            console.log(chalk.blue(`\n⏳ 重新处理（${doTranslate === 'translate' ? '翻译模式' : '仅润色模式'}）...\n`));
            const confirmBody = { ...body, target_language: resolvedLang, confirm_lang: true };
            await streamPost(url, confirmBody, undefined, undefined, false);
            return;
          } else if (event.type === 'mode_suggestion') {
            reader.cancel();
            completeReceived = true;
            const suggestedName = (event as any).mode_name || (event as any).suggested_mode || '';
            console.log(chalk.yellow(`\n⚠️ 检测到当前模式可能不合适！`));
            console.log(chalk.gray(`   ${(event as any).reason || ''}`));
            const { switchMode } = await inquirer.prompt([
              {
                type: 'list',
                name: 'switchMode',
                message: '是否切换模式？',
                choices: [
                  { name: `✅ 切换到 ${suggestedName}`, value: 'switch' },
                  { name: '📌 继续当前模式', value: 'stay' },
                  { name: '❌ 取消', value: 'cancel' },
                ],
              },
            ]);
            if (switchMode === 'cancel') {
              console.log(chalk.gray('已取消\n'));
              return;
            }
            if (switchMode === 'switch') {
              const suggestedMode = (event as any).suggested_mode;
              const modeUrlMap: Record<string, string> = {
                chat: '/chat/stream',
                meeting: '/meeting/minutes/stream',
                literature: '/literature/summarize/stream',
                polish: '/polish/stream',
                ppt: '/ppt/generate/stream',
              };

              let polishTargetLang = 'auto';
              let polishStyle = 'academic';

              if (suggestedMode === 'polish') {
                const langAndStyle = await inquirer.prompt([
                  {
                    type: 'list',
                    name: 'targetLanguage',
                    message: '目标语言：',
                    choices: [
                      { name: '自动识别', value: 'auto' },
                      { name: '英文 (en)', value: 'en' },
                      { name: '中文 (zh)', value: 'zh' },
                      { name: '日文 (ja)', value: 'ja' },
                      { name: '韩文 (ko)', value: 'ko' },
                      { name: '法文 (fr)', value: 'fr' },
                      { name: '德文 (de)', value: 'de' },
                      { name: '西班牙文 (es)', value: 'es' },
                      { name: '俄文 (ru)', value: 'ru' },
                      { name: '葡萄牙文 (pt)', value: 'pt' },
                      { name: '意大利文 (it)', value: 'it' },
                      { name: '阿拉伯文 (ar)', value: 'ar' },
                    ],
                  },
                  {
                    type: 'list',
                    name: 'style',
                    message: '写作风格：',
                    choices: [
                      { name: '学术写作', value: 'academic' },
                      { name: '商业计划书', value: 'business' },
                      { name: '正式公文', value: 'formal' },
                      { name: '教授邮件', value: 'email_professor' },
                      { name: '日常交流', value: 'casual' },
                    ],
                  },
                ]);
                polishTargetLang = langAndStyle.targetLanguage;
                polishStyle = langAndStyle.style;
                console.log(chalk.green(`\n🔄 切换到 ${suggestedName} 模式（${polishTargetLang === 'auto' ? '自动识别' : polishTargetLang} / ${polishStyle}）\n`));
              } else {
                console.log(chalk.green(`\n🔄 切换到 ${suggestedName} 模式\n`));
              }

              const modeBodyMap: Record<string, (msg: string) => any> = {
                chat: (msg: string) => ({ message: msg }),
                meeting: (msg: string) => ({ transcript: msg, language: 'auto' }),
                literature: (msg: string) => ({ file_path: msg, query: '请生成这篇文献的详细摘要' }),
                polish: (msg: string) => ({ text: msg, target_language: polishTargetLang, style: polishStyle, detect_source_lang: true }),
                ppt: (msg: string) => ({ topic: msg, content: '', style: 'academic', template: 'default' }),
              };
              const newUrl = modeUrlMap[suggestedMode] || '/chat/stream';
              const msg = userInput || '';
              const newBody = modeBodyMap[suggestedMode] ? modeBodyMap[suggestedMode]!(msg) : { message: msg };
              await streamPost(newUrl, newBody, suggestedMode, msg, true);
            } else {
              console.log(chalk.blue('\n⏳ 继续当前模式...\n'));
              await streamPost(url, { ...body, skip_mode_check: true }, undefined, undefined, false);
            }
            return;
          }
        } catch (e) {
          // skip
        }
      }
    }
  }
}

async function firstTimeSetup() {
  printBanner();
  const env = loadEnv();

  console.log(chalk.cyan('📋 当前配置状态：\n'));
  console.log(`  千问 API Key:  ${env.QWEN_API_KEY ? chalk.green('✅ 已配置') : chalk.red('❌ 未配置')}`);
  console.log(`  腾讯 API Key:  ${env.TENCENT_API_KEY ? chalk.green('✅ 已配置') : chalk.red('❌ 未配置')}`);
  console.log(`  默认提供方:    ${chalk.yellow(env.DEFAULT_PROVIDER || 'qwen (默认)')}\n`);

  if (hasApiKey(env)) {
    const { needReconfigure } = await inquirer.prompt([
      {
        type: 'confirm',
        name: 'needReconfigure',
        message: '当前已有可用 API Key，是否重新配置？',
        default: false,
      },
    ]);
    if (!needReconfigure) return;
  } else {
    console.log(chalk.yellow('⚠️  未检测到有效的 API Key，请先配置才能使用 AI 功能\n'));
  }

  const providerChoices = [
    { name: '千问 (Qwen/DashScope)', value: 'qwen' },
    { name: '腾讯 (Hunyuan)', value: 'tencent' },
  ];

  const { provider } = await inquirer.prompt([
    {
      type: 'list',
      name: 'provider',
      message: '请选择 AI 提供方：',
      choices: providerChoices,
      default: env.DEFAULT_PROVIDER || 'qwen',
    },
  ]);

  const existingKey = provider === 'qwen' ? env.QWEN_API_KEY : env.TENCENT_API_KEY;

  const { apiKey } = await inquirer.prompt([
    {
      type: 'input',
      name: 'apiKey',
      message: `请输入 ${provider === 'qwen' ? '千问' : '腾讯'} API Key${existingKey ? chalk.gray('（留空保留现有 Key）') : ''}：`,
      validate: (input: string) => {
        if (!input.trim() && !existingKey) return 'API Key 不能为空';
        return true;
      },
    },
  ]);

  const finalKey = apiKey.trim() || existingKey;
  saveEnv(provider === 'qwen' ? 'QWEN_API_KEY' : 'TENCENT_API_KEY', finalKey!);
  saveEnv('DEFAULT_PROVIDER', provider);

  console.log(chalk.green('\n✅ 配置已保存！'));
  console.log(chalk.gray(`   提供方: ${provider}`));
  console.log(chalk.gray(`   API Key: ${finalKey!.slice(0, 8)}...${finalKey!.slice(-4)}\n`));
}

async function interactiveMenu() {
  printConvStatus();

  const choices: { name: string; value: string }[] = [];

  if (currentConvId) {
    choices.push({ name: `💬 继续当前对话 (${taskTypeLabels[currentConvType || ''] || currentConvType})`, value: 'continue' });
  }
  choices.push(
    { name: '💬 新建通用对话', value: 'new_chat' },
    { name: '📝 新建会议纪要', value: 'new_meeting' },
    { name: '📚 新建文献摘要', value: 'new_literature' },
    { name: '✨ 新建多语言润色', value: 'new_polish' },
    { name: '📊 新建PPT生成', value: 'new_ppt' },
    { name: '📋 对话历史', value: 'history' },
    { name: '📋 任务中心', value: 'tasks' },
    { name: '🧩 Skills 扩展', value: 'skills' },
    { name: '⚙️  切换模型/API', value: 'switch' },
    { name: '🚪 退出', value: 'exit' },
  );

  const { task } = await inquirer.prompt([
    {
      type: 'list',
      name: 'task',
      message: '请选择操作：',
      choices,
    },
  ]);

  switch (task) {
    case 'continue':
      await continueChat();
      break;
    case 'new_chat':
      await chatTask(true);
      break;
    case 'new_meeting':
      await meetingTask(true);
      break;
    case 'new_literature':
      await literatureTask(true);
      break;
    case 'new_polish':
      await polishTask(true);
      break;
    case 'new_ppt':
      await pptTaskWithOutlineOutput(true);
      break;
    case 'history':
      await conversationHistory();
      break;
    case 'tasks':
      await tasksList();
      break;
    case 'skills':
      await skillsMenu();
      break;
    case 'switch':
      await switchProvider();
      break;
    case 'exit':
      console.log(chalk.cyan('👋 再见！'));
      process.exit(0);
  }
}

async function continueChat() {
  if (!currentConvId) {
    console.log(chalk.yellow('当前无活跃对话，请先新建对话'));
    return;
  }

  const { action } = await inquirer.prompt([
    {
      type: 'list',
      name: 'action',
      message: '请选择：',
      choices: [
        { name: '💬 继续对话', value: 'input' },
        { name: '↩️ 返回主菜单', value: 'back' },
      ],
    },
  ]);
  if (action === 'back') return;

  const { message } = await inquirer.prompt([
    { type: 'input', name: 'message', message: '继续对话（输入消息）：' },
  ]);

  if (!message.trim()) return;

  console.log(chalk.blue('\n===思考中===\n'));

  const streamUrlMap: Record<string, string> = {
    chat: '/chat/stream',
    meeting: '/meeting/minutes/stream',
    literature: '/literature/summarize/stream',
    polish: '/polish/stream',
    ppt: '/ppt/generate/stream',
  };
  const streamBodyMap: Record<string, (msg: string) => any> = {
    chat: (msg) => ({ message: msg }),
    meeting: (msg) => ({ transcript: msg, language: 'auto' }),
    literature: (msg) => ({ file_path: msg, query: '请生成这篇文献的详细摘要' }),
    polish: (msg) => ({ text: msg, target_language: 'auto', style: 'academic', detect_source_lang: true }),
    ppt: (msg) => ({ topic: msg, content: '', style: 'academic', template: 'default' }),
  };

  const convType = currentConvType || 'chat';
  const url = streamUrlMap[convType] || '/chat/stream';
  const body = (streamBodyMap[convType] || streamBodyMap.chat)(message);
  await streamPost(url, body, convType, message, false);
}

async function chatTask(forceNew: boolean = false) {
  const { action } = await inquirer.prompt([
    {
      type: 'list',
      name: 'action',
      message: '请选择：',
      choices: [
        { name: '💬 输入问题开始对话', value: 'input' },
        { name: '↩️ 返回主菜单', value: 'back' },
      ],
    },
  ]);
  if (action === 'back') return;

  const { message } = await inquirer.prompt([
    { type: 'input', name: 'message', message: forceNew ? '新建对话，请输入你的问题：' : '请输入你的问题：' },
  ]);

  if (!message.trim()) return;

  console.log(chalk.blue('\n===思考中===\n'));
  await streamPost('/chat/stream', { message }, 'chat', message, forceNew);
}

async function meetingTask(forceNew: boolean = false) {
  const { inputType } = await inquirer.prompt([
    {
      type: 'list',
      name: 'inputType',
      message: '输入方式：',
      choices: [
        { name: '↩️ 返回主菜单', value: 'back' },
        { name: '文本输入', value: 'text' },
        { name: '上传录音文件', value: 'file' },
      ],
    },
  ]);

  if (inputType === 'back') return;

  let transcript = '';
  let language = 'zh';

  if (inputType === 'text') {
    const { text } = await inquirer.prompt([
      { type: 'editor', name: 'text', message: '请输入会议记录文本：' },
    ]);
    transcript = text;
  } else {
    const { filePath } = await inquirer.prompt([
      { type: 'input', name: 'filePath', message: '请输入录音文件路径：' },
    ]);
    console.log(chalk.blue('上传并转写中...'));
    try {
      const FormData = (await import('form-data')).default;
      const fsModule = await import('fs');
      const pathModule = await import('path');
      const resolvedPath = pathModule.resolve(filePath);
      if (!fsModule.existsSync(resolvedPath)) {
        console.log(chalk.red(`文件不存在: ${resolvedPath}`));
        return;
      }
      const form = new FormData();
      form.append('file', fsModule.createReadStream(resolvedPath), pathModule.basename(resolvedPath));
      form.append('language', 'zh');
      form.append('mode', 'meeting');
      const asrRes = await axios.post(GATEWAY_URL + '/meeting/transcribe-sync', form, {
        headers: form.getHeaders(),
        timeout: 180000,
      });
      if (asrRes.data.transcript) {
        transcript = asrRes.data.transcript;
        console.log(chalk.green('✅ 转写完成'));
      } else {
        console.log(chalk.yellow('⚠️ 未识别到语音内容，请确保录音清晰'));
        return;
      }
    } catch (e: any) {
      console.log(chalk.red(`转写失败: ${e.message || e}`));
      return;
    }
  }

  const { lang } = await inquirer.prompt([
    {
      type: 'list',
      name: 'lang',
      message: '语言模式：',
      choices: [
        { name: '自动识别', value: 'auto' },
        { name: '中文', value: 'zh' },
        { name: '英文', value: 'en' },
        { name: '双语对照', value: 'bilingual' },
      ],
    },
  ]);
  language = lang;

  console.log(chalk.blue('\n⏳ 正在生成会议纪要...\n'));
  await streamPost('/meeting/minutes/stream', { transcript, language }, 'meeting', transcript, forceNew);
}

async function literatureTask(forceNew: boolean = false) {
  const { action } = await inquirer.prompt([
    {
      type: 'list',
      name: 'action',
      message: '请选择：',
      choices: [
        { name: '📚 输入文件路径开始', value: 'input' },
        { name: '↩️ 返回主菜单', value: 'back' },
      ],
    },
  ]);
  if (action === 'back') return;

  const { filePath } = await inquirer.prompt([
    { type: 'input', name: 'filePath', message: '请输入PDF文件路径：' },
  ]);

  const { query } = await inquirer.prompt([
    { type: 'input', name: 'query', message: '查询问题（留空则生成摘要）：', default: '请生成这篇文献的详细摘要' },
  ]);

  console.log(chalk.blue('\n⏳ 正在处理文献...\n'));
  await streamPost('/literature/summarize/stream', { file_path: filePath, query }, 'literature', query, forceNew);
}

async function polishTask(forceNew: boolean = false) {
  const { action } = await inquirer.prompt([
    {
      type: 'list',
      name: 'action',
      message: '请选择：',
      choices: [
        { name: '✨ 输入文本开始润色', value: 'input' },
        { name: '↩️ 返回主菜单', value: 'back' },
      ],
    },
  ]);
  if (action === 'back') return;

  const { text } = await inquirer.prompt([
    { type: 'editor', name: 'text', message: '请输入需要润色的文本：' },
  ]);

  const { targetLanguage, style } = await inquirer.prompt([
    {
      type: 'list',
      name: 'targetLanguage',
      message: '目标语言：',
      choices: [
        { name: '自动识别', value: 'auto' },
        { name: '英文 (en)', value: 'en' },
        { name: '中文 (zh)', value: 'zh' },
        { name: '日文 (ja)', value: 'ja' },
        { name: '韩文 (ko)', value: 'ko' },
        { name: '法文 (fr)', value: 'fr' },
        { name: '德文 (de)', value: 'de' },
        { name: '西班牙文 (es)', value: 'es' },
        { name: '俄文 (ru)', value: 'ru' },
        { name: '葡萄牙文 (pt)', value: 'pt' },
        { name: '意大利文 (it)', value: 'it' },
        { name: '阿拉伯文 (ar)', value: 'ar' },
      ],
    },
    {
      type: 'list',
      name: 'style',
      message: '写作风格：',
      choices: [
        { name: '学术写作', value: 'academic' },
        { name: '商业计划书', value: 'business' },
        { name: '正式公文', value: 'formal' },
        { name: '教授邮件', value: 'email_professor' },
        { name: '日常交流', value: 'casual' },
      ],
    },
  ]);

  try {
    const detectRes = await axios.post(GATEWAY_URL + '/polish/detect-language', { text });
    const detectedLang = detectRes.data?.lang || 'auto';
    const detectedName = detectRes.data?.name || detectedLang;
    const langNameMap: Record<string, string> = {
      auto: '自动识别', en: '英文', zh: '中文', ja: '日文', ko: '韩文',
      fr: '法文', de: '德文', es: '西班牙文', ru: '俄文', pt: '葡萄牙文', it: '意大利文', ar: '阿拉伯文',
    };
    const styleNameMap: Record<string, string> = {
      academic: '学术写作', business: '商业计划书', formal: '正式公文', email_professor: '教授邮件', casual: '日常交流',
    };
    const resolvedTarget = targetLanguage === 'auto' ? detectedLang : targetLanguage;
    const resolvedTargetName = langNameMap[resolvedTarget] || resolvedTarget;
    const isTranslation = detectedLang !== 'auto' && resolvedTarget !== 'auto' && detectedLang !== resolvedTarget;

    if (isTranslation) {
      console.log(chalk.cyan(`\n🌐 翻译模式：${detectedName} → ${resolvedTargetName}`));
    } else {
      console.log(chalk.cyan(`\n✍️ 润色模式：${detectedName} 润色`));
    }
    console.log(chalk.gray(`   风格：${styleNameMap[style] || style}`));

    const { confirmPolish } = await inquirer.prompt([
      {
        type: 'list',
        name: 'confirmPolish',
        message: isTranslation ? '确认翻译？' : '确认润色？',
        choices: [
          { name: `✅ 确认${isTranslation ? '翻译' : '润色'}`, value: true },
          { name: '❌ 取消', value: false },
        ],
      },
    ]);
    if (!confirmPolish) {
      console.log(chalk.gray('已取消\n'));
      return;
    }
  } catch (e) {
    // detection failed, proceed directly
  }

  console.log(chalk.blue('\n⏳ 正在润色...\n'));
  await streamPost('/polish/stream', { text, target_language: targetLanguage, style, detect_source_lang: true }, 'polish', text, forceNew);
}

async function pptTask(forceNew: boolean = false) {
  const { topic, content } = await inquirer.prompt([
    { type: 'input', name: 'topic', message: 'PPT 主题：' },
    { type: 'editor', name: 'content', message: '参考内容（可选）：' },
  ]);

  console.log(chalk.blue('\n⏳ 正在生成PPT...\n'));
  await streamPost('/ppt/generate/stream', { topic, content, style: 'academic', template: 'default' }, 'ppt', topic, forceNew);
}

async function pptTaskWithOutlineOutput(forceNew: boolean = false) {
  const { action } = await inquirer.prompt([
    {
      type: 'list',
      name: 'action',
      message: '请选择：',
      choices: [
        { name: '📊 输入主题生成PPT', value: 'input' },
        { name: '↩️ 返回主菜单', value: 'back' },
      ],
    },
  ]);
  if (action === 'back') return;

  const { topic, content } = await inquirer.prompt([
    { type: 'input', name: 'topic', message: 'PPT 主题：' },
    { type: 'editor', name: 'content', message: '参考内容（可选）：' },
  ]);

  if (!topic || !topic.trim()) {
    console.log(chalk.red('\n❌ 错误: PPT 主题不能为空'));
    console.log(chalk.yellow('💡 提示: 请输入明确的PPT主题，例如：'));
    console.log(chalk.gray('   - "人工智能发展趋势"'));
    console.log(chalk.gray('   - "2024年Q3销售总结"'));
    console.log(chalk.gray('   - "机器学习入门教程"\n'));
    return;
  }

  console.log(chalk.blue('\n⏳ 正在生成PPT大纲...\n'));
  
  let outlineData: any = null;
  let actorText = '';
  let criticText = '';
  let finalOutput = '';
  let completeReceived = false;

  if (forceNew || !currentConvId || currentConvType !== 'ppt') {
    const convId = await createConversation('ppt', topic);
    if (!convId) {
      console.log(chalk.red('❌ 创建对话失败，请检查后端服务是否运行'));
      return;
    }
  } else {
    if (topic) {
      await saveMessage(currentConvId!, 'user', topic);
    }
  }

  try {
    const response = await fetch(GATEWAY_URL + '/ppt/generate/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, content, style: 'academic', template: 'default' }),
    });

    if (!response.ok) {
      console.log(chalk.red(`\n❌ 请求失败: HTTP ${response.status} ${response.statusText}`));
      console.log(chalk.yellow('💡 提示: 请确保后端服务正在运行'));
      console.log(chalk.gray('   启动后端: lvv start 或 cd ai-core && python -m uvicorn app.main:app\n'));
      return;
    }

    if (!response.body) return;

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          if (data === '[DONE]') {
            if (!completeReceived) {
              if (outlineData) {
                printPPTOutline(outlineData);
              } else {
                console.log(chalk.yellow('\n⚠️ PPT大纲生成失败，未获取到有效数据'));
                console.log(chalk.yellow('💡 建议:'));
                console.log(chalk.gray('   - 尝试使用更明确的主题'));
                console.log(chalk.gray('   - 提供更详细的参考内容'));
                console.log(chalk.gray('   - 检查API Key是否有效\n'));
              }
              const output = finalOutput || actorText;
              if (currentConvId) {
                await saveMessage(currentConvId, 'actor', output);
                if (criticText) {
                  await saveMessage(currentConvId, 'critic', criticText);
                }
              }
            }
            return;
          }
          try {
            const event = JSON.parse(data);
            if (event.type === 'stream' && event.role === 'actor' && event.content) {
              process.stdout.write(chalk.blue(event.content));
              actorText += event.content;
            } else if (event.type === 'stream' && event.role === 'critic' && event.content) {
              process.stdout.write(chalk.yellow(event.content));
              criticText += event.content;
            } else if (event.type === 'step' && event.message) {
              console.log(chalk.blue(`\n${event.message}`));
            } else if (event.type === 'preview_ready' && event.outline) {
              outlineData = event.outline;
            } else if (event.type === 'actor_done') {
              console.log(chalk.blue(`\n✅ Actor 输出完成（剩余循环次数: ${event.remaining_iterations ?? '未知'}）`));
            } else if (event.type === 'critic_done') {
              if (event.approved) {
                console.log(chalk.green(`\n✅ Critic 审查通过，即将输出正式结果...`));
              } else {
                console.log(chalk.yellow(`\n⚠️ Critic 审查未通过，Actor 将重新生成...`));
              }
            } else if (event.type === 'complete') {
              completeReceived = true;
              finalOutput = event.output || actorText;
              if (outlineData) {
                printPPTOutline(outlineData);
              }
              if (currentConvId) {
                await saveMessage(currentConvId, 'actor', finalOutput);
                if (criticText) {
                  await saveMessage(currentConvId, 'critic', criticText);
                }
              }
              return;
            } else if (event.type === 'error') {
              console.log(chalk.red(`\n❌ 错误: ${event.message}`));
              console.log(chalk.yellow('💡 提示: PPT生成遇到错误'));
              console.log(chalk.gray('   - 确保主题清晰明确'));
              console.log(chalk.gray('   - 参考内容应为文本格式'));
              console.log(chalk.gray('   - 如需使用其他功能，请返回主菜单选择\n'));
            }
          } catch (e) {
            // skip
          }
        }
      }
    }
  } catch (e) {
    console.log(chalk.red('\n❌ PPT生成失败'));
    console.log(chalk.yellow('💡 提示: 请检查网络连接和后端服务状态'));
    console.log(chalk.gray('   - 使用 "lvv start" 启动服务'));
    console.log(chalk.gray('   - 使用 "lvv setup" 配置API Key\n'));
  }
}

function printPPTOutline(outline: any) {
  console.log('\n' + chalk.cyan.bold('═══════════════════════════════════════'));
  console.log(chalk.cyan.bold('📊 PPT 大纲'));
  console.log(chalk.cyan.bold('═══════════════════════════════════════\n'));
  
  console.log(chalk.white.bold(`标题: ${outline.title || '未命名'}`));
  if (outline.subtitle) {
    console.log(chalk.gray(`副标题: ${outline.subtitle}`));
  }
  if (outline.author) {
    console.log(chalk.gray(`作者: ${outline.author}`));
  }
  console.log();

  if (outline.slides && outline.slides.length > 0) {
    console.log(chalk.yellow.bold(`共 ${outline.slides.length} 页幻灯片\n`));
    
    outline.slides.forEach((slide: any, idx: number) => {
      console.log(chalk.green.bold(`第 ${idx + 1} 页: ${slide.title}`));
      if (slide.bullets && slide.bullets.length > 0) {
        slide.bullets.forEach((bullet: string) => {
          console.log(chalk.white(`  • ${bullet}`));
        });
      }
      if (slide.notes) {
        console.log(chalk.gray(`  备注: ${slide.notes}`));
      }
      if (slide.image_keywords) {
        console.log(chalk.blue(`  配图关键词: ${slide.image_keywords}`));
      }
      console.log();
    });
  }
  
  console.log(chalk.cyan.bold('═══════════════════════════════════════\n'));
}

async function conversationHistory() {
  try {
    const res = await api.get('/conversations', { params: { limit: 20 } });
    const convs = res.data.conversations || [];

    if (convs.length === 0) {
      console.log(chalk.yellow('\n暂无对话记录\n'));
      return;
    }

    const choices = convs.map((c: any) => ({
      name: `${taskTypeLabels[c.task_type] || c.task_type} | ${c.conv_id.slice(0, 8)}... | ${new Date(c.created_at).toLocaleString('zh-CN')}`,
      value: c.conv_id,
    }));

    choices.push({ name: '↩ 返回', value: '__back__' });

    const { selected } = await inquirer.prompt([
      {
        type: 'list',
        name: 'selected',
        message: '选择对话查看详情或切换：',
        choices,
      },
    ]);

    if (selected === '__back__') return;

    const detailRes = await api.get(`/conversations/${selected}`);
    const conv = detailRes.data;
    const messages = conv.messages || [];

    console.log(chalk.cyan(`\n═══ 对话详情 ═══`));
    console.log(chalk.white(`ID: ${conv.conv_id}`));
    console.log(chalk.white(`类型: ${taskTypeLabels[conv.task_type] || conv.task_type}`));
    console.log(chalk.white(`创建时间: ${new Date(conv.created_at).toLocaleString('zh-CN')}`));
    console.log(chalk.white(`消息数: ${messages.length}\n`));

    for (const msg of messages) {
      const roleLabels: Record<string, string> = {
        user: chalk.yellow('👤 用户'),
        actor: chalk.green('🤖 输出'),
        critic: chalk.gray('🔍 审查'),
      };
      const label = roleLabels[msg.role] || msg.role;
      const content = msg.content.length > 200 ? msg.content.slice(0, 200) + '...' : msg.content;
      console.log(`${label}: ${content}\n`);
    }

    const { action } = await inquirer.prompt([
      {
        type: 'list',
        name: 'action',
        message: '下一步操作：',
        choices: [
          { name: '切换到此对话并继续', value: 'switch' },
          { name: '删除此对话', value: 'delete' },
          { name: '返回', value: 'back' },
        ],
      },
    ]);

    if (action === 'switch') {
      currentConvId = conv.conv_id;
      currentConvType = conv.task_type;
      console.log(chalk.green(`已切换到对话 ${conv.conv_id.slice(0, 8)}...`));
    } else if (action === 'delete') {
      await api.delete(`/conversations/${conv.conv_id}`);
      if (currentConvId === conv.conv_id) {
        currentConvId = null;
        currentConvType = null;
      }
      console.log(chalk.green('对话已删除'));
    }
  } catch (e) {
    console.log(chalk.red('获取对话历史失败'));
  }
}

async function skillsMenu() {
  while (true) {
    const { action } = await inquirer.prompt([
      {
        type: 'list',
        name: 'action',
        message: '🧩 Skills 扩展',
        choices: [
          { name: '📋 查看已安装 Skills', value: 'list' },
          { name: '🔗 从 Git 仓库导入', value: 'import_git' },
          { name: '📁 从本地 .zip 导入', value: 'import_zip' },
          { name: '▶  执行 Skill', value: 'execute' },
          { name: '🗑️ 删除 Skill', value: 'remove' },
          { name: '🔄 重新加载', value: 'reload' },
          { name: '↩️  返回主菜单', value: 'back' },
        ],
      },
    ]);

    if (action === 'back') break;

    switch (action) {
      case 'list':
        await skillsListAction();
        break;
      case 'import_git':
        await skillsImportGitAction();
        break;
      case 'import_zip':
        await skillsImportZipAction();
        break;
      case 'execute':
        await skillsExecuteAction();
        break;
      case 'remove':
        await skillsRemoveAction();
        break;
      case 'reload':
        await skillsReloadAction();
        break;
    }
  }
}

async function skillsListAction() {
  try {
    const res = await api.get('/skills');
    const skills = res.data.skills || [];
    if (skills.length === 0) {
      console.log(chalk.yellow('\n暂无已安装的 Skill\n'));
      return;
    }
    console.log(chalk.cyan(`\n🧩 已安装 Skills (${skills.length})：\n`));
    skills.forEach((s: any) => {
      const icon = s.icon || '🧩';
      const typeLabel = s.type === 'prompt' ? chalk.magenta('Prompt') : chalk.green('Function');
      console.log(`  ${icon} ${chalk.bold(s.name)} ${typeLabel} v${s.version}`);
      console.log(`    ${chalk.gray(s.description)}`);
      if (s.tags && s.tags.length) {
        console.log(`    ${chalk.blue(s.tags.join(', '))}`);
      }
    });
    console.log();
  } catch (e) {
    console.log(chalk.red('获取 Skills 列表失败'));
  }
}

async function skillsImportGitAction() {
  const { url } = await inquirer.prompt([
    { type: 'input', name: 'url', message: '输入 Git 仓库 URL（GitHub / GitCode / Gitee 等）：' },
  ]);
  if (!url.trim()) return;

  const { branch } = await inquirer.prompt([
    { type: 'input', name: 'branch', message: '分支：', default: 'main' },
  ]);
  const { subpath } = await inquirer.prompt([
    { type: 'input', name: 'subpath', message: '子路径（可选，直接回车跳过）：', default: '' },
  ]);

  console.log(chalk.blue(`\n⏳ 正在从 Git 仓库导入: ${url}...\n`));
  try {
    const res = await api.post('/skills/import/git', { url: url.trim(), branch, subpath: subpath.trim() });
    const data = res.data;

    console.log(chalk.cyan('═══ 安全评估报告 ═══'));
    if (data.trust_level) {
      const trustLabels: Record<string, string> = {
        verified: '✅ 官方验证 (Verified)',
        community: '🟡 社区来源',
        unknown: '⚪ 未知来源',
        untrusted: '🔴 不受信任',
      };
      console.log(`  来源信任: ${trustLabels[data.trust_level] || data.trust_level}`);
    }
    if (data.scan_result) {
      const riskLabels: Record<string, string> = {
        low: '🟢 低风险',
        medium: '🟡 中风险',
        high: '🔴 高风险',
      };
      console.log(`  风险等级: ${riskLabels[data.scan_result.risk_level] || data.scan_result.risk_level}`);
      if (data.scan_result.warnings && data.scan_result.warnings.length) {
        console.log(chalk.yellow('  警告:'));
        data.scan_result.warnings.forEach((w: string) => console.log(chalk.yellow(`    - ${w}`)));
      }
      if (data.scan_result.network_calls && data.scan_result.network_calls.length) {
        console.log(chalk.blue(`  网络请求: ${data.scan_result.network_calls.join(', ')}`));
      }
      if (data.scan_result.file_operations && data.scan_result.file_operations.length) {
        console.log(chalk.blue(`  文件操作: ${data.scan_result.file_operations.join(', ')}`));
      }
    }
    console.log();

    if (data.scan_result && data.scan_result.risk_level === 'medium') {
      const { proceed } = await inquirer.prompt([
        {
          type: 'list',
          name: 'proceed',
          message: '⚠️ 检测到中风险行为，是否继续安装？',
          choices: [
            { name: '❌ 取消安装', value: false },
            { name: '✅ 继续安装（已了解风险）', value: true },
          ],
        },
      ]);
      if (!proceed) {
        console.log(chalk.yellow('已取消安装\n'));
        try { await api.delete(`/skills/${data.skill_name}`); } catch {}
        return;
      }
    }

    console.log(chalk.green(`✅ Skill "${data.skill_name}" 导入成功\n`));
  } catch (e: any) {
    console.log(chalk.red(`导入失败: ${e.response?.data?.detail || e.message}\n`));
  }
}

async function skillsImportZipAction() {
  const { filePath } = await inquirer.prompt([
    { type: 'input', name: 'filePath', message: '输入 .skill.zip 文件路径：' },
  ]);
  if (!filePath.trim()) return;

  const FormData = (await import('form-data')).default;
  const resolvedPath = path.resolve(filePath.trim());

  if (!fs.existsSync(resolvedPath)) {
    console.log(chalk.red(`文件不存在: ${resolvedPath}\n`));
    return;
  }
  if (!resolvedPath.endsWith('.zip')) {
    console.log(chalk.red('仅支持 .skill.zip 文件\n'));
    return;
  }

  console.log(chalk.blue(`\n⏳ 正在从本地文件导入: ${resolvedPath}...\n`));
  try {
    const formData = new FormData();
    formData.append('file', fs.createReadStream(resolvedPath));
    const res = await api.post('/skills/import/upload', formData, {
      headers: formData.getHeaders(),
    });
    const data = res.data;

    console.log(chalk.cyan('═══ 安全评估报告 ═══'));
    if (data.trust_level) {
      const trustLabels: Record<string, string> = {
        verified: '✅ 官方验证', community: '🟡 社区来源',
        unknown: '⚪ 未知来源', untrusted: '🔴 不受信任',
      };
      console.log(`  来源信任: ${trustLabels[data.trust_level] || data.trust_level}`);
    }
    if (data.scan_result) {
      const riskLabels: Record<string, string> = {
        low: '🟢 低风险', medium: '🟡 中风险', high: '🔴 高风险',
      };
      console.log(`  风险等级: ${riskLabels[data.scan_result.risk_level] || data.scan_result.risk_level}`);
      if (data.scan_result.warnings && data.scan_result.warnings.length) {
        console.log(chalk.yellow('  警告:'));
        data.scan_result.warnings.forEach((w: string) => console.log(chalk.yellow(`    - ${w}`)));
      }
    }
    console.log();

    if (data.scan_result && data.scan_result.risk_level === 'medium') {
      const { proceed } = await inquirer.prompt([
        {
          type: 'list',
          name: 'proceed',
          message: '⚠️ 检测到中风险行为，是否继续安装？',
          choices: [
            { name: '❌ 取消安装', value: false },
            { name: '✅ 继续安装（已了解风险）', value: true },
          ],
        },
      ]);
      if (!proceed) {
        console.log(chalk.yellow('已取消安装\n'));
        try { await api.delete(`/skills/${data.skill_name}`); } catch {}
        return;
      }
    }

    console.log(chalk.green(`✅ Skill "${data.skill_name}" 导入成功\n`));
  } catch (e: any) {
    console.log(chalk.red(`导入失败: ${e.response?.data?.detail || e.message}\n`));
  }
}

async function skillsExecuteAction() {
  let skills: any[] = [];
  try {
    const res = await api.get('/skills');
    skills = res.data.skills || [];
  } catch (e) {
    console.log(chalk.red('获取 Skills 列表失败\n'));
    return;
  }

  if (skills.length === 0) {
    console.log(chalk.yellow('暂无可执行的 Skill，请先导入\n'));
    return;
  }

  const { skillName } = await inquirer.prompt([
    {
      type: 'list',
      name: 'skillName',
      message: '选择要执行的 Skill：',
      choices: skills.map((s: any) => ({
        name: `${s.icon || '🧩'} ${s.name} - ${s.description}`,
        value: s.name,
      })),
    },
  ]);

  const skill = skills.find((s: any) => s.name === skillName);
  const context: any = {};

  if (skill && skill.input_schema) {
    for (const [key, field] of Object.entries(skill.input_schema)) {
      const f = field as any;
      const { value } = await inquirer.prompt([
        {
          type: f.type === 'string' ? 'editor' : 'input',
          name: 'value',
          message: `${f.description || key}${f.required ? ' (必填)' : ''}:`,
          default: f.default || '',
        },
      ]);
      context[key] = value;
    }
  } else {
    const { text } = await inquirer.prompt([
      { type: 'editor', name: 'text', message: '输入文本内容：' },
    ]);
    context.text = text;
  }

  console.log(chalk.blue(`\n⏳ 正在执行 Skill: ${skillName}...\n`));
  try {
    const res = await api.post(`/skills/${skillName}/execute`, { context });
    const data = res.data;
    if (data.output) {
      console.log(chalk.green('═══ 执行结果 ═══'));
      console.log(chalk.green(data.output));
    } else {
      console.log(chalk.green('═══ 执行结果 ═══'));
      console.log(JSON.stringify(data, null, 2));
    }
    if (data.critic_feedbacks && data.critic_feedbacks.length) {
      console.log(chalk.gray('\n═══ Critic 反馈 ═══'));
      data.critic_feedbacks.forEach((fb: string, i: number) => {
        console.log(chalk.gray(`[${i + 1}] ${fb}`));
      });
    }
    console.log();
  } catch (e: any) {
    console.log(chalk.red(`执行失败: ${e.response?.data?.detail || e.message}\n`));
  }
}

async function skillsRemoveAction() {
  let skills: any[] = [];
  try {
    const res = await api.get('/skills');
    skills = res.data.skills || [];
  } catch (e) {
    console.log(chalk.red('获取 Skills 列表失败\n'));
    return;
  }

  if (skills.length === 0) {
    console.log(chalk.yellow('暂无可删除的 Skill\n'));
    return;
  }

  const { skillName } = await inquirer.prompt([
    {
      type: 'list',
      name: 'skillName',
      message: '选择要删除的 Skill：',
      choices: [
        ...skills.map((s: any) => ({
          name: `${s.icon || '🧩'} ${s.name}`,
          value: s.name,
        })),
        { name: '↩️ 取消', value: '' },
      ],
    },
  ]);

  if (!skillName) return;

  const { confirm } = await inquirer.prompt([
    {
      type: 'list',
      name: 'confirm',
      message: `确定删除 Skill "${skillName}"？`,
      choices: [
        { name: '❌ 取消', value: false },
        { name: '🗑️ 确认删除', value: true },
      ],
    },
  ]);
  if (!confirm) return;

  try {
    await api.delete(`/skills/${skillName}`);
    console.log(chalk.green(`✅ Skill "${skillName}" 已删除\n`));
  } catch (e: any) {
    console.log(chalk.red(`删除失败: ${e.response?.data?.detail || e.message}\n`));
  }
}

async function skillsReloadAction() {
  try {
    const res = await api.post('/skills/reload');
    console.log(chalk.green(`✅ 已重新加载 ${res.data.skills_loaded} 个 Skill\n`));
  } catch (e) {
    console.log(chalk.red('重新加载失败\n'));
  }
}

async function tasksList() {
  try {
    const res = await api.get('/tasks');
    const tasks = res.data;
    if (tasks.length === 0) {
      console.log(chalk.yellow('暂无任务'));
      return;
    }
    console.log(chalk.cyan('\n📋 任务列表：\n'));
    tasks.forEach((task: any) => {
      const statusColors: Record<string, string> = {
        pending: chalk.yellow('⏳ 等待中'),
        processing: chalk.blue('🔄 处理中'),
        completed: chalk.green('✅ 已完成'),
        failed: chalk.red('❌ 失败'),
      };
      console.log(`  ${task.task_id.slice(0, 8)}... | ${task.task_type} | ${statusColors[task.status] || task.status} | ${task.created_at}`);
    });
    console.log();
  } catch (e) {
    console.log(chalk.red('获取任务列表失败'));
  }
}

async function switchProvider() {
  const env = loadEnv();
  const currentProvider = env.DEFAULT_PROVIDER || 'qwen';

  console.log(chalk.cyan('\n📋 当前配置状态：\n'));
  console.log(`  千问 API Key:  ${env.QWEN_API_KEY ? chalk.green('✅ 已配置 (' + env.QWEN_API_KEY.slice(0, 8) + '...)') : chalk.red('❌ 未配置')}`);
  console.log(`  腾讯 API Key:  ${env.TENCENT_API_KEY ? chalk.green('✅ 已配置 (' + env.TENCENT_API_KEY.slice(0, 8) + '...)') : chalk.red('❌ 未配置')}`);
  console.log(`  默认提供方:    ${chalk.yellow(currentProvider)}\n`);

  const { action } = await inquirer.prompt([
    {
      type: 'list',
      name: 'action',
      message: '请选择操作：',
      choices: [
        { name: '切换 AI 提供方', value: 'switch' },
        { name: '修改 API Key', value: 'apikey' },
        { name: '切换模型', value: 'model' },
        { name: '返回', value: 'back' },
      ],
    },
  ]);

  if (action === 'back') return;

  if (action === 'switch') {
    const { provider } = await inquirer.prompt([
      {
        type: 'list',
        name: 'provider',
        message: '选择 AI 提供方：',
        choices: [
          { name: '千问 (Qwen)', value: 'qwen' },
          { name: '腾讯 (Tencent)', value: 'tencent' },
          { name: 'Mock (离线演示)', value: 'mock' },
        ],
      },
    ]);
    saveEnv('DEFAULT_PROVIDER', provider);
    try {
      await api.post('/switch', { provider });
    } catch (e) {
      // API may not be running
    }
    console.log(chalk.green(`已切换到 ${provider}`));
  } else if (action === 'apikey') {
    const { provider } = await inquirer.prompt([
      {
        type: 'list',
        name: 'provider',
        message: '选择要修改的提供方：',
        choices: [
          { name: `千问 ${env.QWEN_API_KEY ? chalk.green('✅') : chalk.red('❌')}`, value: 'qwen' },
          { name: `腾讯 ${env.TENCENT_API_KEY ? chalk.green('✅') : chalk.red('❌')}`, value: 'tencent' },
        ],
        default: currentProvider,
      },
    ]);

    const existingKey = provider === 'qwen' ? env.QWEN_API_KEY : env.TENCENT_API_KEY;

    const { apiKey } = await inquirer.prompt([
      {
        type: 'input',
        name: 'apiKey',
        message: `请输入 ${provider === 'qwen' ? '千问' : '腾讯'} API Key${existingKey ? chalk.gray('（留空保留现有 Key）') : ''}：`,
        validate: (input: string) => {
          if (!input.trim() && !existingKey) return 'API Key 不能为空';
          return true;
        },
      },
    ]);

    const finalKey = apiKey.trim() || existingKey;
    saveEnv(provider === 'qwen' ? 'QWEN_API_KEY' : 'TENCENT_API_KEY', finalKey!);

    console.log(chalk.green('\n✅ API Key 已更新！'));
    console.log(chalk.gray(`   提供方: ${provider}`));
    console.log(chalk.gray(`   API Key: ${finalKey!.slice(0, 8)}...${finalKey!.slice(-4)}\n`));
  } else if (action === 'model') {
    const { modelName } = await inquirer.prompt([
      { type: 'input', name: 'modelName', message: '输入模型名称（如 qwen-max, qwen-coder-turbo-0919）：' },
    ]);
    try {
      await api.post('/switch', { provider: currentProvider, model_name: modelName });
    } catch (e) {
      // ignore
    }
    console.log(chalk.green(`模型已切换到 ${modelName}`));
  }
}

async function demoMode() {
  console.log(chalk.cyan('🎬 演示模式启动！\n'));

  console.log(chalk.blue('💬 任务1: 通用对话'));
  await streamPost('/chat/stream', { message: '你好，请介绍一下你自己' }, 'chat', '你好，请介绍一下你自己', true);

  console.log('\n' + chalk.blue('📝 任务2: 生成会议纪要'));
  await streamPost('/meeting/minutes/stream', {
    transcript: '今天我们讨论了项目进度。张三负责前端开发，预计下周完成。李四负责后端API，已经完成80%。王五负责测试，下周一启动。会议决定下周三进行集成测试。',
    language: 'zh',
  }, 'meeting', '今天我们讨论了项目进度...', true);

  console.log('\n' + chalk.blue('✨ 任务3: 多语言润色'));
  await streamPost('/polish/stream', {
    text: 'I think this research is very good and we should do more experiments to prove our hypothesis.',
    target_language: 'en',
    style: 'academic',
    detect_source_lang: true,
  }, 'polish', 'I think this research is very good...', true);

  console.log(chalk.green('\n\n🎬 演示完成！'));
}

const program = new Command();

program
  .name('agent-cli')
  .description('LVV - Love Working CLI')
  .version('1.0.0');

program
  .command('setup')
  .description('首次使用配置')
  .action(async () => {
    await firstTimeSetup();
  });

const PROJECT_ROOT = path.resolve(__dirname, '../..');

async function startBackendServices(): Promise<boolean> {
  return await startAllServices(false);
}

async function startAllServices(includeWeb: boolean = true): Promise<boolean> {
  const isWindows = process.platform === 'win32';
  const aiCorePort = process.env.AI_CORE_PORT || '8000';
  const webPort = process.env.WEB_PORT || '5173';

  if (!fs.existsSync(ENV_PATH)) {
    if (fs.existsSync(ENV_EXAMPLE_PATH)) {
      console.log(chalk.yellow('  ⚠️ .env 文件不存在，从 .env.example 创建...'));
      fs.copyFileSync(ENV_EXAMPLE_PATH, ENV_PATH);
      console.log(chalk.green('  ✅ .env 已创建! 请编辑该文件配置 API Key'));
    } else {
      console.log(chalk.red('  ❌ 找不到 .env 和 .env.example 文件'));
      return false;
    }
  }

  const aiCoreDir = path.join(PROJECT_ROOT, 'ai-core');
  const webDir = path.join(PROJECT_ROOT, 'web');

  const venvPython = isWindows
    ? path.join(aiCoreDir, '.venv', 'Scripts', 'python.exe')
    : path.join(aiCoreDir, '.venv', 'bin', 'python');

  if (!fs.existsSync(venvPython)) {
    console.log(chalk.red('\n  ❌ Python 虚拟环境不存在！'));
    console.log(chalk.yellow('  请先运行安装脚本:'));
    if (isWindows) {
      console.log(chalk.cyan('    lvv install'));
    } else {
      console.log(chalk.cyan('    ./lvv.sh install'));
    }
    console.log('');
    return false;
  }

  console.log(chalk.cyan('\n🚀 正在启动服务...\n'));

  if (isWindows) {
    spawn(`start "LVV-AICore" /d "${aiCoreDir}" cmd /k .venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port ${aiCorePort}`, [], {
      detached: true, stdio: 'ignore', shell: true
    }).unref();
  } else {
    spawn(venvPython, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', aiCorePort], {
      cwd: aiCoreDir, detached: true, stdio: 'ignore'
    }).unref();
  }
  console.log(chalk.green(`  ✅ AI Core 启动中... (端口 ${aiCorePort})`));

  await new Promise(r => setTimeout(r, 2000));

  if (includeWeb) {
    if (isWindows) {
      spawn(`start "LVV-Web" /d "${webDir}" cmd /k npx vite --host 127.0.0.1 --port ${webPort}`, [], {
        detached: true, stdio: 'ignore', shell: true
      }).unref();
    } else {
      spawn('npx', ['vite', '--host', '127.0.0.1', '--port', webPort], {
        cwd: webDir, detached: true, stdio: 'ignore'
      }).unref();
    }
    console.log(chalk.green(`  ✅ Web UI 启动中... (端口 ${webPort})`));
  }

  console.log(chalk.gray('\n  等待服务就绪...'));

  const dots = ['.', '..', '...'];
  for (let i = 0; i < 120; i++) {
    process.stdout.write(`\r  等待服务就绪${dots[i % 3]}   `);
    await new Promise(r => setTimeout(r, 1000));
    const status = await checkBackendStatus();
    if (status.aiCore) {
      process.stdout.write('\r                          \r');
      console.log(chalk.green('\n  ✅ 所有服务已就绪！\n'));
      if (includeWeb) {
        console.log(chalk.cyan(`  🌐 Web 界面: http://localhost:${webPort}\n`));
      }
      return true;
    }
  }

  process.stdout.write('\r                          \r');
  const status = await checkBackendStatus();
  if (status.aiCore) {
    console.log(chalk.green('\n  ✅ 服务已就绪！\n'));
    return true;
  }

  console.log(chalk.red('\n  ❌ 服务启动超时，请检查日志或手动启动\n'));
  return false;
}

interface HealthStatus {
  status: string;
  all_offline: boolean;
  online_providers: string[];
  offline_providers: string[];
  local_fallback?: {
    available: Record<string, boolean>;
    summary: Record<string, string>;
  };
}

async function checkBackendStatus(retries: number = 3): Promise<{ aiCore: boolean; web?: boolean; health?: HealthStatus }> {
  let aiCore = false;
  let web = false;
  let health: HealthStatus | undefined;

  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const res = await axios.get(AI_CORE_URL + '/health', { timeout: 5000 });
      aiCore = true;
      health = res.data;
      break;
    } catch (e) {
      if (attempt < retries - 1) {
        await new Promise(r => setTimeout(r, 1000));
      }
    }
  }

  try {
    const webPort = process.env.WEB_PORT || '5173';
    await axios.get(`http://localhost:${webPort}`, { timeout: 3000 });
    web = true;
  } catch (e) {
    // not running
  }

  return { aiCore, web, health };
}

function printHealthWarnings(health?: HealthStatus) {
  if (!health) return;

  if (health.all_offline) {
    console.log(chalk.red('\n⚠️  所有AI模型均不可用！\n'));
    console.log(chalk.yellow('  可选方案：'));
    console.log(chalk.cyan('  1. 配置 API Key（推荐，见下方引导）'));
    console.log(chalk.cyan('  2. 使用本地备用库（无需 API Key，功能有限，已随依赖安装）\n'));
    return;
  }

  if (health.online_providers && health.online_providers.length > 0) {
    console.log(chalk.green(`  [OK] 在线提供商: ${health.online_providers.join(', ')}`));
  }

  if (health.local_fallback?.available) {
    const available = Object.entries(health.local_fallback.available)
      .filter(([_, v]) => v)
      .map(([k, _]) => k);
    if (available.length > 0) {
      console.log(chalk.green(`  [OK] 本地备用: ${available.join(', ')}`));
    } else {
      console.log(chalk.yellow('  [--] 本地备用库未安装（可选）'));
    }
  }
}

async function runInteractive() {
  printBanner();
  
  let { aiCore, health } = await checkBackendStatus();
  
  printHealthWarnings(health);
  
  const env = loadEnv();
  if (!hasApiKey(env)) {
    await firstTimeSetup();
  }
  
  if (!health || health.all_offline) {
    const currentEnv = loadEnv();
    if (!hasApiKey(currentEnv)) {
      console.log(chalk.yellow('  API Key 仍未配置，部分功能不可用。\n'));
    }
  } else {
    console.log(chalk.green('✅ AI 模型已就绪！\n'));
  }

  if (!aiCore) {
    console.log(chalk.red('❌ 后端服务未启动！\n'));

    const { action } = await inquirer.prompt([
      {
        type: 'list',
        name: 'action',
        message: '下一步：',
        choices: [
          { name: '🚀 一键启动所有服务（后端+Web前端+CLI）', value: 'start_all' },
          { name: '🔧 仅启动后端服务', value: 'start' },
          { name: '� 重新检查服务状态', value: 'recheck' },
          { name: '�🚪 退出（手动启动后端）', value: 'exit' },
          { name: '⏩ 忽略，继续进入（部分功能不可用）', value: 'continue' },
        ],
      },
    ]);

    if (action === 'recheck') {
      await runInteractive();
      return;
    } else if (action === 'start_all') {
      const started = await startAllServices(true);
      if (!started) {
        const { retryAction } = await inquirer.prompt([
          {
            type: 'list',
            name: 'retryAction',
            message: '服务启动未成功，请选择：',
            choices: [
              { name: '🔄 重新检测状态（建议等待两分钟后再检测）', value: 'recheck' },
              { name: '� 重新尝试启动', value: 'retry' },
              { name: '⏩ 进入离线模式（使用离线演示数据）', value: 'continue' },
              { name: '🚪 退出', value: 'exit' },
            ],
          },
        ]);
        if (retryAction === 'recheck') {
          const status = await checkBackendStatus();
          if (status.aiCore) {
            console.log(chalk.green('✅ 检测到服务已就绪，进入CLI模式'));
            await runInteractive();
            return;
          } else {
            console.log(chalk.yellow('⚠️  服务仍未就绪'));
            await runInteractive();
            return;
          }
        }
        if (retryAction === 'retry') {
          await runInteractive();
          return;
        }
        if (retryAction === 'exit') {
          process.exit(0);
        }
      }
    } else if (action === 'start') {
      const started = await startBackendServices();
      if (!started) {
        const { retryAction } = await inquirer.prompt([
          {
            type: 'list',
            name: 'retryAction',
            message: '服务启动未成功，请选择：',
            choices: [
              { name: '🔄 重新检测状态（建议等待两分钟后再检测）', value: 'recheck' },
              { name: '🔁 重新尝试启动', value: 'retry' },
              { name: '⏩ 进入离线模式（使用离线演示数据）', value: 'continue' },
              { name: '🚪 退出', value: 'exit' },
            ],
          },
        ]);
        if (retryAction === 'recheck') {
          const status = await checkBackendStatus();
          if (status.aiCore) {
            console.log(chalk.green('✅ 检测到服务已就绪，进入CLI模式'));
            await runInteractive();
            return;
          } else {
            console.log(chalk.yellow('⚠️  服务仍未就绪'));
            await runInteractive();
            return;
          }
        }
        if (retryAction === 'retry') {
          await runInteractive();
          return;
        }
        if (retryAction === 'exit') {
          process.exit(0);
        }
      }
    } else if (action === 'exit') {
      process.exit(0);
    }
  } else {
    console.log(chalk.green('✅ 后端服务运行中\n'));
  }

  let lastBackendOnline = aiCore;
  let consecutiveFailures = 0;
  const healthCheckInterval = setInterval(async () => {
    try {
      const res = await axios.get(AI_CORE_URL + '/health', { timeout: 10000 });
      consecutiveFailures = 0;
      const nowOnline = true;
      if (!lastBackendOnline && nowOnline) {
        console.log(chalk.green('\n  ✅ 后端服务已恢复！'));
        const health = res.data;
        if (health) printHealthWarnings(health);
        console.log('');
      }
      lastBackendOnline = nowOnline;
    } catch (e) {
      consecutiveFailures++;
      if (consecutiveFailures >= 3 && lastBackendOnline) {
        console.log(chalk.red('\n  ⚠️  后端服务已断开！'));
        console.log(chalk.red('     AI Core 不可用'));
        console.log(chalk.gray('     部分功能可能不可用，系统将在恢复后通知您\n'));
        lastBackendOnline = false;
      }
    }
  }, 30_000);

  process.on('exit', () => clearInterval(healthCheckInterval));

  while (true) {
    await interactiveMenu();
  }
}

program
  .command('interactive')
  .description('交互式菜单')
  .alias('i')
  .action(async () => {
    await runInteractive();
  });

program
  .command('start')
  .description('启动后端服务并进入交互模式')
  .action(async () => {
    await runInteractive();
  });

program
  .command('start-all')
  .description('一键启动所有服务（AI Core + Web UI）')
  .alias('sa')
  .action(async () => {
    printBanner();
    const started = await startAllServices(true);
    if (started) {
      const { openCLI } = await inquirer.prompt([
        {
          type: 'confirm',
          name: 'openCLI',
          message: '是否进入 CLI 交互模式？',
          default: true,
        },
      ]);
      if (openCLI) {
        await runInteractive();
      }
    }
  });

program
  .command('demo')
  .description('演示模式 - 自动运行预设任务')
  .action(async () => {
    printBanner();
    await demoMode();
  });

program
  .command('switch <target>')
  .description('切换AI提供方或模型 (qwen/tencent/mock/qwen-max/qwen-coder-turbo-0919等)')
  .action(async (target: string) => {
    const knownProviders = ['qwen', 'tencent', 'mock'];
    if (knownProviders.includes(target)) {
      saveEnv('DEFAULT_PROVIDER', target);
      try {
        await api.post('/switch', { provider: target });
      } catch (e) {
        // ignore
      }
      console.log(chalk.green(`已切换到 ${target}`));
    } else {
      const env = loadEnv();
      const currentProvider = env.DEFAULT_PROVIDER || 'qwen';
      saveEnv('LLM_DEFAULT', target);
      try {
        await api.post('/switch', { provider: currentProvider, model_name: target });
      } catch (e) {
        // ignore
      }
      console.log(chalk.green(`模型已切换到 ${target} (提供方: ${currentProvider})`));
    }
  });

program
  .command('chat [message]')
  .description('通用对话')
  .option('-s, --system-prompt <prompt>', '系统提示词')
  .option('-n, --new', '强制新建对话')
  .action(async (message?: string, opts?: any) => {
    if (!message) {
      const { input } = await inquirer.prompt([
        { type: 'input', name: 'input', message: '请输入你的问题：' },
      ]);
      message = input;
    }
    if (!message?.trim()) return;
    console.log(chalk.blue('\n===思考中===\n'));
    await streamPost('/chat/stream', { message, system_prompt: opts?.systemPrompt }, 'chat', message, opts?.new);
  });

program
  .command('meeting')
  .description('生成会议纪要')
  .option('-t, --transcript <text>', '会议记录文本')
  .option('-f, --file <path>', '录音文件路径')
  .option('-l, --language <lang>', '语言模式 (auto/zh/en/bilingual)', 'auto')
  .option('-n, --new', '强制新建对话')
  .action(async (opts) => {
    if (!opts.transcript && !opts.file) {
      console.log(chalk.red('请提供 --transcript 或 --file 参数'));
      return;
    }
    const transcript = opts.transcript || `[FILE:${opts.file}]`;
    await streamPost('/meeting/minutes/stream', { transcript, language: opts.language }, 'meeting', transcript, opts.new);
  });

program
  .command('literature <filePath>')
  .description('生成文献摘要')
  .option('-q, --query <text>', '查询问题', '请生成这篇文献的详细摘要')
  .option('-n, --new', '强制新建对话')
  .action(async (filePath: string, opts) => {
    await streamPost('/literature/summarize/stream', { file_path: filePath, query: opts.query }, 'literature', opts.query, opts.new);
  });

program
  .command('polish')
  .description('多语言润色')
  .option('-t, --text <text>', '待润色文本')
  .option('-l, --language <lang>', '目标语言 (auto/en/zh/ja/ko/fr/de/es/ru/pt/it/ar)', 'auto')
  .option('-s, --style <style>', '写作风格', 'academic')
  .option('-n, --new', '强制新建对话')
  .action(async (opts) => {
    if (!opts.text) {
      console.log(chalk.red('请提供 --text 参数'));
      return;
    }
    await streamPost('/polish/stream', { text: opts.text, target_language: opts.language, style: opts.style, detect_source_lang: true }, 'polish', opts.text, opts.new);
  });

program
  .command('ppt <topic>')
  .description('生成PPT')
  .option('-c, --content <text>', '参考内容')
  .option('-s, --style <style>', '风格', 'academic')
  .option('-n, --new', '强制新建对话')
  .action(async (topic: string, opts) => {
    if (!topic || !topic.trim()) {
      console.log(chalk.red('\n❌ 错误: PPT 主题不能为空'));
      console.log(chalk.yellow('💡 用法: lvv ppt "主题" [-c 参考内容]'));
      console.log(chalk.gray('   例如: lvv ppt "人工智能发展趋势"\n'));
      return;
    }

    console.log(chalk.blue('\n⏳ 正在生成PPT大纲...\n'));
    
    let outlineData: any = null;
    let actorText = '';
    let criticText = '';
    let finalOutput = '';
    let completeReceived = false;

    if (opts.new || !currentConvId || currentConvType !== 'ppt') {
      const convId = await createConversation('ppt', topic);
      if (!convId) {
        console.log(chalk.red('❌ 创建对话失败，请检查后端服务是否运行'));
        console.log(chalk.yellow('💡 提示: 使用 "lvv start" 启动后端服务\n'));
        return;
      }
    } else {
      if (topic) {
        await saveMessage(currentConvId!, 'user', topic);
      }
    }

    try {
      const response = await fetch(GATEWAY_URL + '/ppt/generate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, content: opts.content || '', style: opts.style, template: 'default' }),
      });

      if (!response.ok) {
        console.log(chalk.red(`\n❌ 请求失败: HTTP ${response.status} ${response.statusText}`));
        console.log(chalk.yellow('💡 提示: 请确保后端服务正在运行'));
        console.log(chalk.gray('   启动后端: lvv start 或 cd ai-core && python -m uvicorn app.main:app\n'));
        return;
      }

      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data === '[DONE]') {
              if (!completeReceived) {
                if (outlineData) {
                  printPPTOutline(outlineData);
                } else {
                  console.log(chalk.yellow('\n⚠️ PPT大纲生成失败，未获取到有效数据'));
                  console.log(chalk.yellow('💡 建议:'));
                  console.log(chalk.gray('   - 尝试使用更明确的主题'));
                  console.log(chalk.gray('   - 使用 -c 参数提供参考内容'));
                  console.log(chalk.gray('   - 检查API Key是否有效\n'));
                }
                const output = finalOutput || actorText;
                if (currentConvId) {
                  await saveMessage(currentConvId, 'actor', output);
                  if (criticText) {
                    await saveMessage(currentConvId, 'critic', criticText);
                  }
                }
              }
              return;
            }
            try {
              const event = JSON.parse(data);
              if (event.type === 'stream' && event.role === 'actor' && event.content) {
                process.stdout.write(chalk.blue(event.content));
                actorText += event.content;
              } else if (event.type === 'stream' && event.role === 'critic' && event.content) {
                process.stdout.write(chalk.yellow(event.content));
                criticText += event.content;
              } else if (event.type === 'step' && event.message) {
                console.log(chalk.blue(`\n${event.message}`));
              } else if (event.type === 'preview_ready' && event.outline) {
                outlineData = event.outline;
              } else if (event.type === 'actor_done') {
                console.log(chalk.blue(`\n✅ Actor 输出完成（剩余循环次数: ${event.remaining_iterations ?? '未知'}）`));
              } else if (event.type === 'critic_done') {
                if (event.approved) {
                  console.log(chalk.green(`\n✅ Critic 审查通过，即将输出正式结果...`));
                } else {
                  console.log(chalk.yellow(`\n⚠️ Critic 审查未通过，Actor 将重新生成...`));
                }
              } else if (event.type === 'complete') {
                completeReceived = true;
                finalOutput = event.output || actorText;
                if (outlineData) {
                  printPPTOutline(outlineData);
                }
                if (currentConvId) {
                  await saveMessage(currentConvId, 'actor', finalOutput);
                  if (criticText) {
                    await saveMessage(currentConvId, 'critic', criticText);
                  }
                }
                return;
              } else if (event.type === 'error') {
                console.log(chalk.red(`\n❌ 错误: ${event.message}`));
                console.log(chalk.yellow('💡 提示: PPT生成遇到错误'));
                console.log(chalk.gray('   - 确保主题清晰明确'));
                console.log(chalk.gray('   - 参考内容应为文本格式'));
                console.log(chalk.gray('   - 如需使用其他功能，请使用对应命令:\n'));
                console.log(chalk.gray('     lvv chat - 通用对话'));
                console.log(chalk.gray('     lvv meeting - 会议纪要'));
                console.log(chalk.gray('     lvv literature - 文献摘要'));
                console.log(chalk.gray('     lvv polish - 文本润色\n'));
              }
            } catch (e) {
              // skip
            }
          }
        }
      }
    } catch (e) {
      console.log(chalk.red('\n❌ PPT生成失败'));
      console.log(chalk.yellow('💡 提示: 请检查网络连接和后端服务状态'));
      console.log(chalk.gray('   - 使用 "lvv start" 启动服务'));
      console.log(chalk.gray('   - 使用 "lvv setup" 配置API Key\n'));
    }
  });

program
  .command('history')
  .description('查看对话历史')
  .option('-t, --type <taskType>', '按类型筛选 (chat/meeting/literature/polish/ppt)')
  .action(async (opts) => {
    try {
      const params: any = { limit: 20 };
      if (opts.type) params.task_type = opts.type;
      const res = await api.get('/conversations', { params });
      const convs = res.data.conversations || [];
      if (convs.length === 0) {
        console.log(chalk.yellow('暂无对话记录'));
        return;
      }
      convs.forEach((c: any) => {
        const label = taskTypeLabels[c.task_type] || c.task_type;
        const time = new Date(c.created_at).toLocaleString('zh-CN');
        const active = c.conv_id === currentConvId ? chalk.green(' ← 当前') : '';
        console.log(`  ${c.conv_id.slice(0, 8)}... | ${label} | ${time}${active}`);
      });
    } catch (e) {
      console.log(chalk.red('获取对话历史失败'));
    }
  });

program
  .command('tasks')
  .description('查看任务列表')
  .option('-s, --status <status>', '过滤状态')
  .action(async (opts) => {
    try {
      const res = await api.get('/tasks', { params: { status: opts.status } });
      const tasks = res.data;
      if (tasks.length === 0) {
        console.log(chalk.yellow('暂无任务'));
        return;
      }
      tasks.forEach((task: any) => {
        console.log(`${task.task_id.slice(0, 8)} | ${task.task_type} | ${task.status} | ${task.created_at}`);
      });
    } catch (e) {
      console.log(chalk.red('获取任务列表失败'));
    }
  });

program
  .command('token-usage')
  .description('查看Token消耗')
  .action(async () => {
    try {
      const res = await api.get('/token-usage');
      console.log(`今日已用: ${res.data.daily_usage} / ${res.data.budget}`);
      console.log(`剩余: ${res.data.remaining}`);
    } catch (e) {
      console.log(chalk.red('获取Token消耗失败'));
    }
  });

function loadRecommendations(): any[] {
  const configPaths = [
    path.resolve(__dirname, '..', 'skills-recommendations.json'),
    path.resolve(process.cwd(), 'skills-recommendations.json'),
    path.resolve(process.env.HOME || process.env.USERPROFILE || '.', '.lvv', 'skills-recommendations.json'),
  ];
  for (const p of configPaths) {
    if (fs.existsSync(p)) {
      try {
        const data = JSON.parse(fs.readFileSync(p, 'utf-8'));
        return data.categories || [];
      } catch {}
    }
  }
  return [];
}

const skillCommand = program.command('skill').description('Skills 扩展管理');

skillCommand
  .command('list')
  .description('列出所有可用 Skills')
  .action(async () => {
    try {
      const res = await api.get('/skills');
      const skills = res.data.skills || [];
      if (skills.length === 0) {
        console.log(chalk.yellow('暂无可用 Skill'));
        return;
      }
      console.log(chalk.cyan(`\n🧩 可用 Skills (${skills.length})：\n`));
      skills.forEach((s: any) => {
        const icon = s.icon || '🧩';
        const typeLabel = s.type === 'prompt' ? chalk.magenta('Prompt') : chalk.green('Function');
        console.log(`  ${icon} ${chalk.bold(s.name)} ${typeLabel} v${s.version}`);
        console.log(`    ${chalk.gray(s.description)}`);
        if (s.tags && s.tags.length) {
          console.log(`    ${chalk.blue(s.tags.join(', '))}`);
        }
      });
      console.log();
    } catch (e) {
      console.log(chalk.red('获取 Skills 列表失败'));
    }
  });

skillCommand
  .command('import [source]')
  .description('导入 Skill（交互式选择或指定 URL/路径）')
  .option('-b, --branch <branch>', 'Git 分支', 'main')
  .option('-s, --subpath <subpath>', 'Skill 在仓库中的子路径', '')
  .option('--overwrite', '覆盖已存在的 Skill')
  .action(async (source: string | undefined, opts: any) => {
    if (!source) {
      const { method } = await inquirer.prompt([
        {
          type: 'list',
          name: 'method',
          message: '选择导入方式：',
          choices: [
            { name: '🔗 从 Git 仓库导入（GitHub / GitCode / Gitee）', value: 'git' },
            { name: '📁 从本地 .skill.zip 文件导入', value: 'zip' },
            { name: '📋 从推荐列表导入', value: 'recommended' },
            { name: '↩️  取消', value: 'cancel' },
          ],
        },
      ]);

      if (method === 'cancel') return;

      if (method === 'recommended') {
        const categories = loadRecommendations();
        if (categories.length === 0) {
          console.log(chalk.yellow('暂无推荐 Skill（配置文件未找到）'));
          return;
        }

        const skillChoices: Array<{ name: string; value: { url: string; subpath: string; branch: string } }> = [];
        for (const cat of categories) {
          for (const s of cat.skills) {
            skillChoices.push({
              name: `${s.icon} ${s.name} - ${s.description} [${cat.name}]`,
              value: { url: cat.repo_url, subpath: s.subpath, branch: cat.branch || 'main' },
            });
          }
        }
        skillChoices.push({ name: '↩️  返回', value: { url: '', subpath: '', branch: 'main' } });

        const { selected } = await inquirer.prompt([
          {
            type: 'list',
            name: 'selected',
            message: '选择要导入的 Skill：',
            choices: skillChoices,
          },
        ]);
        if (!selected.url) return;

        console.log(chalk.blue(`\n⏳ 正在预览: ${selected.url} (${selected.subpath})...\n`));
        try {
          const previewRes = await api.post('/skills/preview/git', {
            url: selected.url,
            branch: selected.branch,
            subpath: selected.subpath,
          });
          const preview = previewRes.data;

          console.log(chalk.cyan('═══ 安全评估报告 ═══'));
          const trustLabels: Record<string, string> = {
            verified: '✅ 官方验证 (Verified)', community: '🟡 社区来源',
            unknown: '⚪ 未知来源', untrusted: '🔴 不受信任',
          };
          console.log(`  来源信任: ${trustLabels[preview.trust_level] || preview.trust_level}`);
          if (preview.config) {
            console.log(`  Skill 名称: ${preview.config.name || '-'}`);
            console.log(`  描述: ${preview.config.description || '-'}`);
            console.log(`  类型: ${preview.config.type || '-'}`);
          }
          if (preview.scan_result) {
            const riskLabels: Record<string, string> = {
              low: '🟢 低风险', medium: '� 中风险', high: '🔴 高风险',
            };
            console.log(`  风险等级: ${riskLabels[preview.scan_result.risk_level] || preview.scan_result.risk_level}`);
            if (preview.scan_result.warnings && preview.scan_result.warnings.length) {
              console.log(chalk.yellow('  警告:'));
              preview.scan_result.warnings.forEach((w: string) => console.log(chalk.yellow(`    - ${w}`)));
            }
          }
          if (preview.files && preview.files.length) {
            console.log(`  包含文件: ${preview.files.slice(0, 10).join(', ')}${preview.files.length > 10 ? '...' : ''}`);
          }
          console.log();

          if (preview.scan_result && preview.scan_result.risk_level === 'high') {
            console.log(chalk.red('⛔ 安全扫描发现高风险行为，无法安装此 Skill\n'));
            return;
          }

          const { doImport } = await inquirer.prompt([
            {
              type: 'list',
              name: 'doImport',
              message: preview.scan_result?.risk_level === 'medium'
                ? '⚠️ 检测到中风险行为，是否确认导入？'
                : '确认导入此 Skill？',
              choices: [
                { name: '✅ 确认导入', value: true },
                { name: '❌ 取消', value: false },
              ],
            },
          ]);
          if (!doImport) {
            console.log(chalk.yellow('已取消导入\n'));
            return;
          }

          console.log(chalk.blue(`\n⏳ 正在安装...`));
          const importRes = await api.post('/skills/import/git', {
            url: selected.url,
            branch: selected.branch,
            subpath: selected.subpath,
          });
          console.log(chalk.green(`✅ Skill "${importRes.data.skill_name}" 导入成功\n`));
        } catch (e: any) {
          console.log(chalk.red(`操作失败: ${e.response?.data?.detail || e.message}\n`));
        }
        return;
      }

      if (method === 'git') {
        const { url } = await inquirer.prompt([
          { type: 'input', name: 'url', message: '输入 Git 仓库 URL：' },
        ]);
        if (!url.trim()) return;
        const { branch } = await inquirer.prompt([
          { type: 'input', name: 'branch', message: '分支：', default: 'main' },
        ]);
        const { subpath } = await inquirer.prompt([
          { type: 'input', name: 'subpath', message: '子路径（可选）：', default: '' },
        ]);

        console.log(chalk.blue(`\n⏳ 正在预览: ${url}...\n`));
        try {
          const previewRes = await api.post('/skills/preview/git', {
            url: url.trim(), branch, subpath: subpath.trim(),
          });
          const preview = previewRes.data;
          await showPreviewAndConfirm(preview, async () => {
            const importRes = await api.post('/skills/import/git', {
              url: url.trim(), branch, subpath: subpath.trim(),
            });
            console.log(chalk.green(`✅ Skill "${importRes.data.skill_name}" 导入成功\n`));
          });
        } catch (e: any) {
          console.log(chalk.red(`操作失败: ${e.response?.data?.detail || e.message}\n`));
        }
        return;
      }

      if (method === 'zip') {
        const { filePath } = await inquirer.prompt([
          { type: 'input', name: 'filePath', message: '输入 .skill.zip 文件路径：' },
        ]);
        if (!filePath.trim()) return;
        source = filePath.trim();
      }
    }

    if (!source) return;

    const isUrl = source.startsWith('http://') || source.startsWith('https://') || source.includes('github.com') || source.includes('gitcode.com');

    try {
      if (isUrl) {
        console.log(chalk.blue(`正在预览: ${source}...`));
        const previewRes = await api.post('/skills/preview/git', {
          url: source, branch: opts.branch, subpath: opts.subpath,
        });
        await showPreviewAndConfirm(previewRes.data, async () => {
          const importRes = await api.post('/skills/import/git', {
            url: source, branch: opts.branch, subpath: opts.subpath,
          });
          console.log(chalk.green(`✅ Skill "${importRes.data.skill_name}" 导入成功\n`));
        });
      } else {
        if (!source.endsWith('.zip')) {
          console.log(chalk.red('本地导入仅支持 .skill.zip 文件'));
          return;
        }
        const FormData = (await import('form-data')).default;
        const filePath = path.resolve(source);
        if (!fs.existsSync(filePath)) {
          console.log(chalk.red(`文件不存在: ${filePath}`));
          return;
        }
        console.log(chalk.blue(`正在预览: ${filePath}...`));
        const formData = new FormData();
        formData.append('file', fs.createReadStream(filePath));
        formData.append('overwrite', String(!!opts.overwrite));
        const previewRes = await api.post('/skills/preview/upload', formData, {
          headers: formData.getHeaders(),
        });
        await showPreviewAndConfirm(previewRes.data, async () => {
          const formData2 = new FormData();
          formData2.append('file', fs.createReadStream(filePath));
          formData2.append('overwrite', String(!!opts.overwrite));
          const importRes = await api.post('/skills/import/upload', formData2, {
            headers: formData2.getHeaders(),
          });
          console.log(chalk.green(`✅ Skill "${importRes.data.skill_name}" 导入成功\n`));
        });
      }
    } catch (e: any) {
      const detail = e.response?.data?.detail || e.message;
      console.log(chalk.red(`导入失败: ${detail}`));
    }
  });

async function showPreviewAndConfirm(preview: any, onConfirm: () => Promise<void>) {
  console.log(chalk.cyan('═══ 安全评估报告 ═══'));
  const trustLabels: Record<string, string> = {
    verified: '✅ 官方验证 (Verified)', community: '🟡 社区来源',
    unknown: '⚪ 未知来源', untrusted: '🔴 不受信任',
  };
  console.log(`  来源信任: ${trustLabels[preview.trust_level] || preview.trust_level}`);
  if (preview.config) {
    console.log(`  Skill 名称: ${preview.config.name || '-'}`);
    console.log(`  描述: ${preview.config.description || '-'}`);
    console.log(`  类型: ${preview.config.type || '-'}`);
  }
  if (preview.scan_result) {
    const riskLabels: Record<string, string> = {
      low: '🟢 低风险', medium: '🟡 中风险', high: '🔴 高风险',
    };
    console.log(`  风险等级: ${riskLabels[preview.scan_result.risk_level] || preview.scan_result.risk_level}`);
    if (preview.scan_result.warnings && preview.scan_result.warnings.length) {
      console.log(chalk.yellow('  警告:'));
      preview.scan_result.warnings.forEach((w: string) => console.log(chalk.yellow(`    - ${w}`)));
    }
    if (preview.scan_result.network_calls && preview.scan_result.network_calls.length) {
      console.log(chalk.blue(`  🌐 网络请求: ${preview.scan_result.network_calls.join(', ')}`));
    }
    if (preview.scan_result.file_operations && preview.scan_result.file_operations.length) {
      console.log(chalk.blue(`  📁 文件操作: ${preview.scan_result.file_operations.join(', ')}`));
    }
  }
  if (preview.files && preview.files.length) {
    console.log(`  包含文件: ${preview.files.slice(0, 10).join(', ')}${preview.files.length > 10 ? '...' : ''}`);
  }
  console.log();

  if (preview.scan_result && preview.scan_result.risk_level === 'high') {
    console.log(chalk.red('⛔ 安全扫描发现高风险行为，无法安装此 Skill\n'));
    return;
  }

  const { doImport } = await inquirer.prompt([
    {
      type: 'list',
      name: 'doImport',
      message: preview.scan_result?.risk_level === 'medium'
        ? '⚠️ 检测到中风险行为，是否确认导入？'
        : '确认导入此 Skill？',
      choices: [
        { name: '✅ 确认导入', value: true },
        { name: '❌ 取消', value: false },
      ],
    },
  ]);
  if (!doImport) {
    console.log(chalk.yellow('已取消导入\n'));
    return;
  }

  console.log(chalk.blue(`\n⏳ 正在安装...`));
  await onConfirm();
}

skillCommand
  .command('remove [name]')
  .description('删除 Skill（交互式选择或指定名称）')
  .action(async (name: string | undefined) => {
    if (!name) {
      let skills: any[] = [];
      try {
        const res = await api.get('/skills');
        skills = res.data.skills || [];
      } catch (e) {
        console.log(chalk.red('获取 Skills 列表失败'));
        return;
      }
      if (skills.length === 0) {
        console.log(chalk.yellow('暂无可删除的 Skill'));
        return;
      }
      const { selected } = await inquirer.prompt([
        {
          type: 'list',
          name: 'selected',
          message: '选择要删除的 Skill：',
          choices: [
            ...skills.map((s: any) => ({
              name: `${s.icon || '🧩'} ${s.name} - ${s.description}`,
              value: s.name,
            })),
            { name: '↩️  取消', value: '' },
          ],
        },
      ]);
      if (!selected) return;
      name = selected;
    }

    const { confirm } = await inquirer.prompt([
      {
        type: 'list',
        name: 'confirm',
        message: `确定删除 Skill "${name}"？`,
        choices: [
          { name: '❌ 取消', value: false },
          { name: '🗑️ 确认删除', value: true },
        ],
      },
    ]);
    if (!confirm) return;

    try {
      await api.delete(`/skills/${name}`);
      console.log(chalk.green(`✅ Skill "${name}" 已删除`));
    } catch (e: any) {
      const detail = e.response?.data?.detail || e.message;
      console.log(chalk.red(`删除失败: ${detail}`));
    }
  });

skillCommand
  .command('execute [name]')
  .description('执行 Skill（交互式选择或指定名称）')
  .option('-t, --text <text>', '输入文本')
  .option('-c, --context <json>', '输入上下文 (JSON 格式)')
  .action(async (name: string | undefined, opts: any) => {
    if (!name) {
      let skills: any[] = [];
      try {
        const res = await api.get('/skills');
        skills = res.data.skills || [];
      } catch (e) {
        console.log(chalk.red('获取 Skills 列表失败'));
        return;
      }
      if (skills.length === 0) {
        console.log(chalk.yellow('暂无可执行的 Skill，请先导入'));
        return;
      }
      const { selected } = await inquirer.prompt([
        {
          type: 'list',
          name: 'selected',
          message: '选择要执行的 Skill：',
          choices: skills.map((s: any) => ({
            name: `${s.icon || '🧩'} ${s.name} - ${s.description}`,
            value: s.name,
          })),
        },
      ]);
      name = selected;
    }

    let context: any = {};
    if (opts.context) {
      try {
        context = JSON.parse(opts.context);
      } catch (e) {
        console.log(chalk.red('--context 参数必须是有效的 JSON'));
        return;
      }
    }
    if (opts.text) {
      context.text = opts.text;
    }
    if (Object.keys(context).length === 0) {
      const { input } = await inquirer.prompt([
        { type: 'editor', name: 'input', message: '请输入文本内容：' },
      ]);
      context.text = input;
    }
    console.log(chalk.blue(`\n⏳ 正在执行 Skill: ${name}...\n`));
    try {
      const res = await api.post(`/skills/${name}/execute`, { context });
      const data = res.data;
      if (data.output) {
        console.log(chalk.green('═══ 执行结果 ═══'));
        console.log(chalk.green(data.output));
      } else {
        console.log(chalk.green('═══ 执行结果 ═══'));
        console.log(JSON.stringify(data, null, 2));
      }
      if (data.critic_feedbacks && data.critic_feedbacks.length) {
        console.log(chalk.gray('\n═══ Critic 反馈 ═══'));
        data.critic_feedbacks.forEach((fb: string, i: number) => {
          console.log(chalk.gray(`[${i + 1}] ${fb}`));
        });
      }
    } catch (e: any) {
      const detail = e.response?.data?.detail || e.message;
      console.log(chalk.red(`执行失败: ${detail}`));
    }
  });

skillCommand
  .command('reload')
  .description('重新加载所有 Skills')
  .action(async () => {
    try {
      const res = await api.post('/skills/reload');
      console.log(chalk.green(`✅ 已重新加载 ${res.data.skills_loaded} 个 Skill`));
    } catch (e) {
      console.log(chalk.red('重新加载失败'));
    }
  });

process.on('unhandledRejection', (reason, promise) => {
  console.error(chalk.red('\n❌ 未处理的 Promise 拒绝:'), reason);
});

process.on('uncaughtException', (error) => {
  console.error(chalk.red('\n❌ 未捕获的异常:'), error.message);
  console.error(chalk.gray(error.stack || ''));
  process.exit(1);
});

if (process.argv.length <= 2) {
  (async () => {
    try {
      await runInteractive();
    } catch (error: any) {
      console.error(chalk.red('\n❌ 交互模式异常退出:'), error?.message || error);
      console.error(chalk.gray(error?.stack || ''));
      process.exit(1);
    }
  })();
} else {
  program.parse();
}
