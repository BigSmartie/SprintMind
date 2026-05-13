<script setup>
import { computed, onMounted, ref, watch } from 'vue';

import { deleteDocument, getDocuments, getProfile, getTasks, uploadDocument } from '../api';

const props = defineProps({
  refreshKey: {
    type: Number,
    default: 0,
  },
});

const teamRoles = [
  {
    owner: '成员1',
    agent: '需求分析 Agent',
    duty: '负责项目目标、范围与用户故事。',
  },
  {
    owner: '成员2',
    agent: '迭代规划 Agent',
    duty: '负责 Sprint 计划、任务拆解与推进。',
  },
  {
    owner: '成员3',
    agent: '风险质控 Agent',
    duty: '负责风险、验收与答辩准备。',
  },
];

const profile = ref(null);
const tasks = ref([]);
const docs = ref([]);
const isUploading = ref(false);
const uploadError = ref('');

const fetchData = async () => {
  try {
    const [profileRes, tasksRes, docsRes] = await Promise.all([
      getProfile(),
      getTasks(),
      getDocuments(),
    ]);
    profile.value = profileRes.data;
    tasks.value = tasksRes.data || [];
    docs.value = docsRes.data || [];
  } catch {
    // backend may still be booting
  }
};

onMounted(fetchData);
watch(() => props.refreshKey, fetchData);

const todoCount = computed(() => tasks.value.filter((task) => task.status === 'todo').length);
const progressCount = computed(() => tasks.value.filter((task) => task.status === 'in_progress').length);
const doneCount = computed(() => tasks.value.filter((task) => task.status === 'done').length);
const activeTasks = computed(() => tasks.value.filter((task) => task.status !== 'done'));
const completedTasks = computed(() => tasks.value.filter((task) => task.status === 'done'));

const currentGoal = computed(() => {
  const goals = profile.value?.current_goals || [];
  return goals[0] || '构建一个可演示的软件项目管理多智能体系统';
});

const projectTagline = computed(() => {
  return profile.value?.persona_notes || '课程导向、过程清晰、适合三人团队分工展示。';
});

const onFileSelect = async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  uploadError.value = '';
  isUploading.value = true;
  try {
    await uploadDocument(file);
    await fetchData();
  } catch {
    uploadError.value = '资料上传失败，请稍后再试。';
  } finally {
    isUploading.value = false;
    event.target.value = '';
  }
};

const removeDoc = async (docId) => {
  if (!confirm('确认从知识库中删除这份资料吗？')) return;
  await deleteDocument(docId);
  await fetchData();
};

const priorityLabelMap = {
  high: '高优先级',
  medium: '中优先级',
  low: '低优先级',
};
</script>

<template>
  <aside class="sidebar glass">
    <section class="section hero-section">
      <p class="eyebrow">Project Workspace</p>
      <h1 class="project-name">SprintMind</h1>
      <p class="project-goal">{{ currentGoal }}</p>

      <div class="stats-grid">
        <div class="stat-card">
          <span class="stat-value">{{ todoCount }}</span>
          <span class="stat-label">待办</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ progressCount }}</span>
          <span class="stat-label">进行中</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ doneCount }}</span>
          <span class="stat-label">已完成</span>
        </div>
      </div>

      <p class="project-note">{{ projectTagline }}</p>
    </section>

    <section class="section">
      <div class="section-header">
        <span class="label-xs">Team Agents</span>
      </div>

      <div class="role-list">
        <article v-for="role in teamRoles" :key="role.agent" class="role-card">
          <div class="role-top">
            <span class="role-owner">{{ role.owner }}</span>
            <span class="role-agent">{{ role.agent }}</span>
          </div>
          <p class="role-duty">{{ role.duty }}</p>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="section-header">
        <span class="label-xs">Sprint Tasks</span>
        <span class="section-count">{{ tasks.length }}</span>
      </div>

      <div v-if="activeTasks.length" class="task-list">
        <article v-for="task in activeTasks" :key="task.id" class="task-card">
          <div class="task-top">
            <span class="task-status" :class="task.status">{{ task.status }}</span>
            <span class="task-priority" :class="task.priority">
              {{ priorityLabelMap[task.priority] || task.priority }}
            </span>
          </div>
          <p class="task-content">{{ task.content }}</p>
          <div class="task-meta">
            <span>{{ task.owner || '待分配' }}</span>
            <span>{{ task.linked_goal || '未关联目标' }}</span>
          </div>
        </article>
      </div>
      <p v-else class="empty-label">等待规划 Agent 生成任务。</p>

      <div v-if="completedTasks.length" class="done-group">
        <div class="section-header done-header">
          <span class="label-xs">Completed</span>
        </div>
        <div class="task-list done-list">
          <article v-for="task in completedTasks" :key="task.id" class="task-card done-card">
            <p class="task-content">{{ task.content }}</p>
            <div class="task-meta">
              <span>{{ task.owner || '未分配' }}</span>
              <span>已完成</span>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section class="section knowledge-section">
      <div class="section-header">
        <span class="label-xs">Project Assets</span>
        <span class="section-count">{{ docs.length }}</span>
      </div>

      <div v-if="docs.length" class="doc-list">
        <article v-for="doc in docs" :key="doc.doc_id" class="doc-card">
          <div class="doc-main">
            <p class="doc-name">{{ doc.source_file }}</p>
            <p class="doc-meta">{{ doc.doc_type }} · {{ doc.chunk_count }} chunks</p>
          </div>
          <button class="icon-btn" @click="removeDoc(doc.doc_id)">删除</button>
        </article>
      </div>
      <p v-else class="empty-label">还没有项目资料，上传需求文档后会更好用。</p>

      <p v-if="uploadError" class="upload-error">{{ uploadError }}</p>

      <input id="project-file-upload" class="file-input" type="file" @change="onFileSelect" :disabled="isUploading" />
      <label for="project-file-upload" class="upload-button btn-primary" :class="{ disabled: isUploading }">
        {{ isUploading ? '上传中...' : '上传项目资料' }}
      </label>
    </section>
  </aside>
</template>

<style scoped>
.sidebar {
  width: min(360px, 32vw);
  min-width: 300px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  gap: 0;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(243, 249, 248, 0.76)),
    radial-gradient(circle at top left, rgba(61, 181, 170, 0.12), transparent 28%);
}

.section {
  padding: 24px;
  border-bottom: 1px solid rgba(24, 38, 66, 0.08);
}

.hero-section {
  background:
    radial-gradient(circle at top right, rgba(61, 181, 170, 0.22), transparent 38%),
    linear-gradient(160deg, rgba(255, 255, 255, 0.86), rgba(236, 245, 244, 0.78));
}

.eyebrow {
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.project-name {
  margin-top: 10px;
  font-size: 38px;
  line-height: 1;
  color: var(--text-primary);
}

.project-goal {
  margin-top: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.stat-card {
  padding: 14px 10px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.82);
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-label {
  display: block;
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
}

.project-note {
  margin-top: 14px;
  font-size: 13px;
  color: var(--text-secondary);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-count {
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(14, 126, 120, 0.1);
  color: var(--accent-strong);
  font-size: 12px;
  font-weight: 600;
}

.role-list,
.task-list,
.doc-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.role-card,
.task-card,
.doc-card {
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.85);
  box-shadow: 0 10px 20px rgba(20, 51, 69, 0.04);
}

.role-top,
.task-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.role-owner {
  font-size: 12px;
  color: var(--accent-strong);
  font-weight: 700;
}

.role-agent {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
}

.role-duty {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.task-status,
.task-priority {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.task-status.todo {
  background: rgba(242, 158, 76, 0.14);
  color: #bb6f1f;
}

.task-status.in_progress {
  background: rgba(15, 138, 124, 0.14);
  color: #0f756b;
}

.task-status.done {
  background: rgba(76, 175, 80, 0.14);
  color: #2d7d32;
}

.task-priority.high {
  background: rgba(210, 74, 62, 0.12);
  color: #a53b31;
}

.task-priority.medium {
  background: rgba(52, 94, 168, 0.12);
  color: #36548a;
}

.task-priority.low {
  background: rgba(92, 126, 78, 0.12);
  color: #4b6c3e;
}

.task-content,
.doc-name {
  margin-top: 10px;
  color: var(--text-primary);
  line-height: 1.55;
  font-weight: 600;
}

.task-meta,
.doc-meta {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  color: var(--text-muted);
  font-size: 12px;
}

.done-group {
  margin-top: 16px;
}

.done-header {
  margin-bottom: 10px;
}

.done-card {
  opacity: 0.72;
}

.doc-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.doc-main {
  min-width: 0;
}

.doc-name {
  margin-top: 0;
  word-break: break-word;
}

.icon-btn {
  border: none;
  background: rgba(210, 74, 62, 0.1);
  color: #a53b31;
  padding: 8px 10px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 12px;
}

.empty-label {
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.knowledge-section {
  flex: 1;
}

.file-input {
  display: none;
}

.upload-button {
  width: 100%;
  margin-top: 14px;
}

.upload-button.disabled {
  opacity: 0.6;
  pointer-events: none;
}

.upload-error {
  margin-top: 12px;
  color: #b13c34;
  font-size: 13px;
}

@media (max-width: 980px) {
  .sidebar {
    width: 100%;
    min-width: 0;
  }
}
</style>
