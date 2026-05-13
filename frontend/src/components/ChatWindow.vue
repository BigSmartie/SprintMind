<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import DOMPurify from 'dompurify';
import { marked } from 'marked';

import { clearChat, sendMessageStream } from '../api';

marked.setOptions({ breaks: true, gfm: true });

const renderMd = (text) => DOMPurify.sanitize(marked.parse(text || ''));

const props = defineProps({
  messages: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(['message-added', 'message-cleared', 'workspace-updated']);

const samplePrompts = [
  '请把这个项目定义成符合课程要求的多智能体系统。',
  '根据我的项目资料生成三人团队的 Sprint 计划。',
  '帮我解释这三个 Agent 各自负责什么。',
  '从老师答辩视角帮我检查本项目有哪些风险。',
];

const inputMessage = ref('');
const imageBase64 = ref('');
const isSending = ref(false);
const chatContainer = ref(null);
const textareaRef = ref(null);
const pendingAssistant = ref(null);

const displayMessages = computed(() => {
  if (!pendingAssistant.value) return props.messages;
  return [...props.messages, pendingAssistant.value];
});

const scrollToBottom = () => nextTick(() => {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
  }
});

const resizeTextarea = () => nextTick(() => {
  if (!textareaRef.value) return;
  textareaRef.value.style.height = '0px';
  const nextHeight = Math.max(56, Math.min(textareaRef.value.scrollHeight, 180));
  textareaRef.value.style.height = `${nextHeight}px`;
});

watch(displayMessages, scrollToBottom, { deep: true });
watch(inputMessage, resizeTextarea);
onMounted(resizeTextarea);

const getAgentReports = (message) => message?.agentReports || message?.agent_reports || [];
const getProjectSnapshot = (message) => message?.projectSnapshot || message?.project_snapshot || null;
const getStreamStages = (message) => message?.streamStages || [];
const getShortSummary = (report) => {
  const text = (report?.summary || '').replace(/\s+/g, ' ').trim();
  if (!text) return '结构化结论';
  return text.length > 24 ? `${text.slice(0, 24)}…` : text;
};

const createPendingAssistant = () => ({
  role: 'assistant',
  content: '',
  streamStages: [],
  currentStatus: '正在准备请求',
  activeStage: 'prepare',
  isStreaming: true,
  agentReports: [],
  projectSnapshot: null,
});

const upsertStreamStage = (payload) => {
  if (!pendingAssistant.value) return;

  const nextStages = [...pendingAssistant.value.streamStages];
  const currentIndex = nextStages.findIndex((item) => item.stage === payload.stage);
  const nextItem = {
    stage: payload.stage,
    label: payload.label,
  };

  if (currentIndex === -1) {
    nextStages.push(nextItem);
  } else {
    nextStages[currentIndex] = nextItem;
  }

  pendingAssistant.value.streamStages = nextStages;
  pendingAssistant.value.currentStatus = payload.label;
  pendingAssistant.value.activeStage = payload.stage;
};

const appendStreamText = (text) => {
  if (!pendingAssistant.value || !text) return;
  pendingAssistant.value.content += text;
};

const finalizeStreamMessage = (payload) => {
  const finalContent = pendingAssistant.value?.content?.trim() || payload?.answer || '';
  const finalMessage = {
    role: 'assistant',
    content: finalContent,
    agentReports: payload?.agent_reports || [],
    projectSnapshot: payload?.project_snapshot || null,
    streamStages: pendingAssistant.value?.streamStages || [],
  };

  pendingAssistant.value = null;
  emit('message-added', finalMessage);
  emit('workspace-updated');
};

const submitMessage = async () => {
  if ((!inputMessage.value.trim() && !imageBase64.value) || isSending.value) return;

  const text = inputMessage.value.trim();
  const imgData = imageBase64.value;

  emit('message-added', { role: 'user', content: text, image: imgData });
  inputMessage.value = '';
  imageBase64.value = '';
  isSending.value = true;
  pendingAssistant.value = createPendingAssistant();
  resizeTextarea();

  try {
    await sendMessageStream(text, 'default', imgData, {
      status: (payload) => {
        upsertStreamStage(payload);
      },
      delta: (payload) => {
        appendStreamText(payload.text || '');
      },
      final: (payload) => {
        finalizeStreamMessage(payload);
      },
      error: (payload) => {
        throw new Error(payload?.detail || '流式响应失败，请稍后重试。');
      },
    });
  } catch (error) {
    pendingAssistant.value = null;
    const detail = error?.message?.includes('Failed to fetch')
      ? '连接后端失败，请确认服务已启动。'
      : (error?.message || '连接后端失败，请确认服务已启动。');
    emit('message-added', {
      role: 'assistant',
      content: detail,
    });
  } finally {
    isSending.value = false;
    scrollToBottom();
  }
};

const applyPrompt = (prompt) => {
  inputMessage.value = prompt;
  resizeTextarea();
};

const handlePaste = (event) => {
  const items = event.clipboardData?.items;
  if (!items) return;

  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile();
      const reader = new FileReader();
      reader.onload = (loadEvent) => {
        imageBase64.value = loadEvent.target?.result || '';
      };
      reader.readAsDataURL(file);
      event.preventDefault();
      break;
    }
  }
};

const removeImage = () => {
  imageBase64.value = '';
};

const triggerClear = async () => {
  if (!confirm('确认清空当前会话吗？')) return;
  pendingAssistant.value = null;
  await clearChat();
  emit('message-cleared');
};

const handleKeydown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    submitMessage();
  }
};
</script>

<template>
  <main class="chat-shell glass">
    <header class="chat-header">
      <div class="header-copy">
        <p class="eyebrow">SprintMind Workspace</p>
        <h2 class="header-title">多智能体项目协作台</h2>
        <p class="header-subtitle">
          把需求分析、任务规划、风险控制和项目展示串成一条清晰的协作流。
        </p>
      </div>
      <button class="btn-ghost" @click="triggerClear">清空会话</button>
    </header>

    <div ref="chatContainer" class="message-feed">
      <div v-if="!displayMessages.length" class="empty-state">
        <div class="empty-badge">SprintMind</div>
        <h3 class="empty-title">把课程项目从“想法”推进到“可展示成果”</h3>
        <p class="empty-copy">
          你可以上传项目资料、询问三位 Agent 的分工，或者直接要求系统生成 Sprint 计划与风险提示。
        </p>

        <div class="prompt-list">
          <button v-for="prompt in samplePrompts" :key="prompt" class="prompt-card" @click="applyPrompt(prompt)">
            {{ prompt }}
          </button>
        </div>
      </div>

      <div v-for="(msg, index) in displayMessages" :key="index" class="message-row" :class="msg.role">
        <div class="message-avatar" :class="msg.role">
          {{ msg.role === 'assistant' ? 'AI' : 'U' }}
        </div>

        <div class="message-stack">
          <div v-if="msg.role === 'assistant' && msg.isStreaming" class="stream-card">
            <p class="stream-title">{{ msg.currentStatus }}</p>
            <div class="stream-stage-list">
              <span
                v-for="stage in getStreamStages(msg)"
                :key="stage.stage"
                class="stream-stage"
                :class="{ active: stage.stage === msg.activeStage }"
              >
                {{ stage.label }}
              </span>
            </div>
          </div>

          <div class="message-bubble" :class="[msg.role, { streaming: msg.isStreaming }]">
            <img v-if="msg.image" :src="msg.image" alt="user upload" class="bubble-image" />
            <div v-if="msg.content" v-html="renderMd(msg.content)"></div>
            <p v-else class="bubble-placeholder">正在组织回答…</p>
          </div>

          <section v-if="msg.role === 'assistant' && getProjectSnapshot(msg)" class="snapshot-card">
            <div class="snapshot-top">
              <div>
                <p class="snapshot-name">{{ getProjectSnapshot(msg).project_name }}</p>
                <p class="snapshot-note">结构化总结已同步到项目协作区</p>
              </div>
              <span class="snapshot-risk">风险等级：{{ getProjectSnapshot(msg).risk_level }}</span>
            </div>

            <div class="snapshot-grid">
              <article class="snapshot-item">
                <span class="snapshot-label">项目目标</span>
                <p>{{ getProjectSnapshot(msg).objective }}</p>
              </article>
              <article class="snapshot-item">
                <span class="snapshot-label">Sprint 目标</span>
                <p>{{ getProjectSnapshot(msg).sprint_goal }}</p>
              </article>
              <article class="snapshot-item">
                <span class="snapshot-label">下一步建议</span>
                <p>{{ getProjectSnapshot(msg).next_step }}</p>
              </article>
              <article class="snapshot-item">
                <span class="snapshot-label">任务同步</span>
                <p>{{ getProjectSnapshot(msg).task_sync_message }}</p>
              </article>
            </div>
          </section>

          <section v-if="msg.role === 'assistant' && getAgentReports(msg).length" class="report-grid">
            <article v-for="report in getAgentReports(msg)" :key="report.agent_id" class="report-card">
              <div class="report-top">
                <div>
                  <p class="report-name">{{ report.agent_name }}</p>
                  <p class="report-focus">{{ report.focus }}</p>
                </div>
                <span class="report-chip">摘要</span>
              </div>
              <p class="report-summary">{{ getShortSummary(report) }}</p>
              <div class="report-content" v-html="renderMd(report.content)"></div>
            </article>
          </section>
        </div>
      </div>
    </div>

    <div class="composer-shell">
      <div v-if="imageBase64" class="image-preview">
        <img :src="imageBase64" alt="preview" />
        <button class="image-remove" @click="removeImage">×</button>
      </div>

      <div class="composer-card">
        <textarea
          ref="textareaRef"
          v-model="inputMessage"
          :disabled="isSending"
          rows="1"
          placeholder="描述项目、阶段目标或课程要求，也可以粘贴图片资料..."
          @keydown="handleKeydown"
          @paste="handlePaste"
        ></textarea>

        <button
          class="send-button btn-primary"
          :disabled="isSending || (!inputMessage.trim() && !imageBase64)"
          @click="submitMessage"
        >
          {{ isSending ? '协作中...' : '发送给团队' }}
        </button>
      </div>

      <p class="composer-hint">Enter 发送，Shift+Enter 换行，Ctrl+V 可直接粘贴截图。</p>
    </div>
  </main>
</template>

<style scoped>
.chat-shell {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(248, 251, 249, 0.72)),
    radial-gradient(circle at top right, rgba(61, 181, 170, 0.08), transparent 30%);
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
  padding: 28px 32px 22px;
  border-bottom: 1px solid rgba(24, 38, 66, 0.08);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.56), transparent),
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.36), transparent 50%);
}

.header-copy {
  max-width: 760px;
}

.eyebrow {
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.header-title {
  margin-top: 10px;
  font-size: clamp(30px, 3vw, 38px);
  line-height: 1.05;
  color: var(--text-primary);
}

.header-subtitle {
  margin-top: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
  max-width: 640px;
}

.message-feed {
  flex: 1;
  overflow-y: auto;
  padding: 26px 28px 110px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background:
    radial-gradient(circle at 20% 10%, rgba(61, 181, 170, 0.05), transparent 28%),
    radial-gradient(circle at 82% 18%, rgba(255, 209, 143, 0.08), transparent 24%);
}

.empty-state {
  width: min(100%, 860px);
  margin: auto;
  text-align: center;
}

.empty-badge {
  display: inline-flex;
  padding: 8px 16px;
  border-radius: 999px;
  background: rgba(14, 126, 120, 0.12);
  color: var(--accent-strong);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.empty-title {
  margin-top: 18px;
  font-size: clamp(30px, 4vw, 42px);
  line-height: 1.12;
  color: var(--text-primary);
}

.empty-copy {
  margin: 16px auto 0;
  max-width: 660px;
  color: var(--text-secondary);
  line-height: 1.75;
}

.prompt-list {
  margin-top: 28px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.prompt-card {
  padding: 18px 18px;
  border: 1px solid rgba(255, 255, 255, 0.88);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.84);
  color: var(--text-primary);
  line-height: 1.6;
  text-align: left;
  cursor: pointer;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast), border-color var(--transition-fast);
}

.prompt-card:hover {
  transform: translateY(-2px);
  border-color: rgba(61, 181, 170, 0.36);
  box-shadow: 0 18px 32px rgba(32, 66, 88, 0.08);
}

.message-row {
  width: min(100%, 1080px);
  margin: 0 auto;
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.message-row.user {
  grid-template-columns: minmax(0, 1fr) 44px;
}

.message-avatar {
  width: 44px;
  height: 44px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 12px;
  flex-shrink: 0;
}

.message-avatar.assistant {
  background: linear-gradient(135deg, #0f8a7c, #3da89b);
  color: white;
}

.message-avatar.user {
  background: rgba(32, 44, 76, 0.08);
  color: var(--text-secondary);
}

.message-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: min(100%, 860px);
}

.message-row.user .message-stack {
  justify-self: end;
  align-items: flex-end;
  width: min(100%, 760px);
}

.stream-card {
  width: min(100%, 720px);
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(244, 251, 250, 0.92);
  border: 1px solid rgba(214, 236, 232, 0.96);
  box-shadow: 0 10px 18px rgba(15, 111, 101, 0.06);
}

.stream-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--accent-strong);
}

.stream-stage-list {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.stream-stage {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(15, 138, 124, 0.08);
  color: var(--text-secondary);
  font-size: 12px;
  border: 1px solid rgba(15, 138, 124, 0.08);
}

.stream-stage.active {
  background: rgba(15, 138, 124, 0.16);
  color: var(--accent-strong);
  border-color: rgba(15, 138, 124, 0.18);
}

.message-bubble {
  width: auto;
  min-width: 180px;
  max-width: min(100%, 760px);
  padding: 18px 20px;
  border-radius: 24px;
  line-height: 1.75;
  box-shadow: 0 16px 30px rgba(32, 66, 88, 0.06);
  overflow-wrap: anywhere;
  word-break: break-word;
}

.message-bubble.assistant {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.98);
  border-top-left-radius: 14px;
}

.message-bubble.user {
  background: linear-gradient(135deg, #155b72, #0f8a7c 62%, #2ca89a);
  color: white;
  border-top-right-radius: 14px;
  max-width: min(100%, 680px);
  box-shadow: 0 20px 34px rgba(15, 138, 124, 0.16);
}

.message-bubble.streaming {
  min-width: 240px;
}

.bubble-placeholder {
  color: var(--text-muted);
}

.bubble-image {
  display: block;
  max-width: 320px;
  max-height: 240px;
  margin-bottom: 12px;
  border-radius: 14px;
}

.snapshot-card,
.report-card {
  width: 100%;
  border-radius: 22px;
  background: rgba(248, 252, 251, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.92);
  box-shadow: 0 18px 30px rgba(32, 66, 88, 0.05);
}

.snapshot-card {
  padding: 20px;
}

.snapshot-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.snapshot-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.snapshot-note {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
}

.snapshot-risk {
  padding: 6px 11px;
  border-radius: 999px;
  background: rgba(242, 158, 76, 0.14);
  color: #bb6f1f;
  font-size: 12px;
  font-weight: 700;
}

.snapshot-grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.snapshot-item {
  padding: 15px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
}

.snapshot-label {
  display: block;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.snapshot-item p {
  margin-top: 8px;
  color: var(--text-primary);
  line-height: 1.65;
}

.report-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.report-card {
  padding: 20px;
}

.report-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(24, 38, 66, 0.08);
}

.report-name {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}

.report-focus {
  margin-top: 6px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.55;
}

.report-chip {
  flex-shrink: 0;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(15, 138, 124, 0.08);
  color: var(--accent-strong);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
}

.report-summary {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(15, 138, 124, 0.06);
  color: var(--accent-strong);
  font-size: 14px;
  line-height: 1.6;
  font-weight: 600;
}

.report-content {
  margin-top: 16px;
  color: var(--text-primary);
  line-height: 1.75;
}

.composer-shell {
  padding: 18px 24px 24px;
  border-top: 1px solid rgba(24, 38, 66, 0.08);
  background: linear-gradient(180deg, rgba(248, 251, 250, 0), rgba(248, 251, 250, 0.76));
}

.image-preview {
  display: inline-flex;
  align-items: flex-start;
  position: relative;
  margin-bottom: 12px;
}

.image-preview img {
  width: 90px;
  height: 90px;
  object-fit: cover;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.92);
}

.image-remove {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 999px;
  background: #b13c34;
  color: white;
  cursor: pointer;
}

.composer-card {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 12px;
  border-radius: 26px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 18px 30px rgba(32, 66, 88, 0.06);
}

.composer-card textarea {
  flex: 1;
  min-height: 56px;
  max-height: 180px;
  border: none;
  resize: none;
  outline: none;
  background: transparent;
  font: inherit;
  color: var(--text-primary);
  line-height: 1.65;
  padding: 8px 10px;
}

.send-button {
  min-width: 136px;
  white-space: nowrap;
  align-self: stretch;
}

.composer-hint {
  margin-top: 10px;
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}

.message-bubble :deep(p),
.report-content :deep(p) {
  margin: 0 0 0.75em;
}

.message-bubble :deep(p:last-child),
.report-content :deep(p:last-child) {
  margin-bottom: 0;
}

.message-bubble :deep(ul),
.message-bubble :deep(ol),
.report-content :deep(ul),
.report-content :deep(ol) {
  padding-left: 1.25em;
  margin: 0.5em 0;
}

.message-bubble :deep(code),
.report-content :deep(code) {
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(15, 138, 124, 0.08);
  color: var(--accent-strong);
}

.message-bubble.user :deep(code) {
  background: rgba(255, 255, 255, 0.18);
  color: white;
}

.message-bubble :deep(pre),
.report-content :deep(pre) {
  padding: 14px;
  border-radius: 14px;
  background: #132232;
  color: #e9f5f4;
  overflow-x: auto;
}

@media (max-width: 1200px) {
  .prompt-list,
  .snapshot-grid {
    grid-template-columns: 1fr;
  }

  .message-stack,
  .message-row.user .message-stack {
    width: 100%;
  }
}

@media (max-width: 980px) {
  .chat-header {
    flex-direction: column;
    align-items: stretch;
  }

  .message-feed {
    padding-left: 18px;
    padding-right: 18px;
  }

  .message-row,
  .message-row.user {
    grid-template-columns: 1fr;
  }

  .message-avatar {
    display: none;
  }

  .message-stack,
  .message-row.user .message-stack {
    width: 100%;
  }

  .message-bubble,
  .message-bubble.user,
  .stream-card {
    max-width: 100%;
  }

  .report-top {
    flex-direction: column;
    align-items: flex-start;
  }

  .send-button {
    min-width: 112px;
  }
}
</style>
