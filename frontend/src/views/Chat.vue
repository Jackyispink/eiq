<template>
  <section class="page-card chat-page">
    <div class="panel-head">
      <div>
        <h2 class="page-title">智能问答</h2>
        <p class="page-subtitle">基于分析批次进行追问，支持会话历史与来源切换。</p>
      </div>
    </div>

    <div class="chat-layout">
      <aside class="chat-sidebar">
        <div class="sidebar-head">
          <strong>历史会话</strong>
          <button class="ghost-btn" @click="startNewSession">新建</button>
        </div>
        <div v-if="loadingSessions" class="sidebar-empty">加载中...</div>
        <div v-else-if="!sessions.length" class="sidebar-empty">暂无会话</div>
        <button
          v-for="item in sessions"
          :key="item.id"
          class="session-item"
          :class="{ active: Number(activeSessionId) === Number(item.id) }"
          @click="selectSession(item.id)"
        >
          <p class="session-title">{{ item.title || `会话 ${item.id}` }}</p>
          <p class="session-meta">{{ item.updated_at || "" }}</p>
        </button>
      </aside>

      <div class="chat-main">
        <div class="conversation-box">
          <div v-if="!messages.length" class="empty-conversation">请输入问题开始问答</div>
          <div v-else class="message-list">
            <div
              v-for="msg in messages"
              :key="msg.id || `${msg.role}-${msg.created_at}-${msg.content?.slice(0, 12)}`"
              class="message-row"
              :class="msg.role === 'user' ? 'user' : 'assistant'"
            >
              <div class="message-bubble">
                <div v-if="msg.role === 'assistant'" v-html="formatAssistant(msg.content)"></div>
                <p v-else>{{ msg.content }}</p>
              </div>
            </div>
          </div>
        </div>

        <textarea
          v-model="question"
          class="chat-input"
          rows="4"
          placeholder="例如：本次问卷最值得关注的问题是什么？"
        />

        <div class="chat-actions">
          <label class="source-select">
            LLM 来源
            <select v-model="llmSource">
              <option value="api">API</option>
              <option value="local_lora">本地 LoRA</option>
            </select>
          </label>
          <button class="primary-btn" :disabled="loading || !question.trim()" @click="askQuestion">
            {{ loading ? "思考中..." : "发送问题" }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { marked } from "marked";
import { chatApi, getChatSessionDetailApi, getChatSessionsApi } from "../services/api";
import { getBatchIds } from "../utils/analysisSession";

const question = ref("");
const loading = ref(false);
const loadingSessions = ref(false);
const sessions = ref([]);
const activeSessionId = ref(null);
const messages = ref([]);
const activeBatchIds = ref([]);
const llmSource = ref("api");

// 格式化页面展示文本，驱动当前页面的数据流和交互流程。
function formatAssistant(text) {
  return marked.parse(String(text || ""));
}

// 加载后端数据，驱动当前页面的数据流和交互流程。
async function loadSessions(selectFirst = true) {
  loadingSessions.value = true;
  try {
    const { data } = await getChatSessionsApi();
    sessions.value = Array.isArray(data?.sessions) ? data.sessions : [];
    if (selectFirst && !activeSessionId.value && sessions.value.length) {
      await selectSession(sessions.value[0].id);
    }
  } finally {
    loadingSessions.value = false;
  }
}

// 切换当前会话或记录，驱动当前页面的数据流和交互流程。
async function selectSession(sessionId) {
  activeSessionId.value = Number(sessionId);
  const { data } = await getChatSessionDetailApi(sessionId);
  const detail = data?.session || {};
  messages.value = Array.isArray(data?.messages) ? data.messages : [];
  activeBatchIds.value = Array.isArray(detail?.batch_ids) ? detail.batch_ids : [];
}

// 启动页面轮询流程，驱动当前页面的数据流和交互流程。
function startNewSession() {
  activeSessionId.value = null;
  messages.value = [];
  activeBatchIds.value = [];
}

// 提交问答请求，驱动当前页面的数据流和交互流程。
async function askQuestion() {
  if (!question.value.trim() || loading.value) return;

  const text = question.value.trim();
  question.value = "";
  messages.value = [...messages.value, { role: "user", content: text, created_at: new Date().toISOString() }];
  loading.value = true;

  try {
    const batchIds = activeBatchIds.value.length ? activeBatchIds.value : getBatchIds();
    const { data } = await chatApi({
      question: text,
      session_id: activeSessionId.value || undefined,
      batch_ids: batchIds,
      llm_source: llmSource.value,
    });
    const answerText = data?.answer || data?.error || "暂无响应";
    messages.value = [...messages.value, { role: "assistant", content: answerText, created_at: new Date().toISOString() }];

    if (data?.session_id) activeSessionId.value = Number(data.session_id);
    if (Array.isArray(data?.batch_ids)) activeBatchIds.value = data.batch_ids;
    if (data?.llm_source) llmSource.value = String(data.llm_source);

    await loadSessions(false);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await loadSessions(true);
});
</script>

<style scoped>
.chat-page { display: grid; gap: 16px; }
.chat-layout { display: grid; grid-template-columns: 280px 1fr; gap: 16px; }
.chat-sidebar, .chat-main { border: 1px solid var(--line); border-radius: 20px; background: #fff; }
.chat-sidebar { padding: 14px; max-height: 72vh; overflow: auto; }
.sidebar-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.ghost-btn { border: 1px solid var(--line); background: #fff; border-radius: 10px; padding: 6px 10px; cursor: pointer; }
.sidebar-empty { color: var(--text-soft); font-size: 14px; padding: 8px 2px; }
.session-item { width: 100%; text-align: left; border: 1px solid var(--line); background: #fff; border-radius: 12px; padding: 10px 12px; margin-bottom: 8px; cursor: pointer; }
.session-item.active { border-color: #0f766e; background: #ecfeff; }
.session-title { margin: 0; color: var(--text-main); font-weight: 700; }
.session-meta { margin: 6px 0 0; color: var(--text-soft); font-size: 12px; }
.chat-main { padding: 14px; display: grid; gap: 12px; }
.conversation-box { border: 1px solid var(--line); border-radius: 16px; min-height: 380px; max-height: 54vh; overflow: auto; padding: 12px; background: #f8fafc; }
.empty-conversation { color: var(--text-soft); display: grid; place-items: center; min-height: 340px; }
.message-list { display: grid; gap: 10px; }
.message-row { display: flex; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant { justify-content: flex-start; }
.message-bubble { max-width: 82%; border-radius: 14px; padding: 10px 12px; border: 1px solid var(--line); background: #fff; }
.message-row.user .message-bubble { background: linear-gradient(135deg, #0f766e, #0ea5a4); color: #fff; border-color: transparent; }
.message-bubble p { margin: 0; line-height: 1.7; }
.chat-input { width: 100%; border: 1px solid var(--line); border-radius: 14px; padding: 10px 12px; resize: vertical; font: inherit; }
.chat-actions { display: flex; justify-content: flex-end; align-items: center; gap: 10px; }
.source-select { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; color: var(--text-soft); }
.source-select select { border: 1px solid var(--line); border-radius: 10px; padding: 6px 10px; background: #fff; }
.primary-btn { border: none; border-radius: 12px; background: linear-gradient(135deg, #0f766e, #0ea5a4); color: #fff; font-weight: 700; padding: 10px 18px; cursor: pointer; }
.primary-btn:disabled { opacity: 0.65; cursor: not-allowed; }
@media (max-width: 960px) { .chat-layout { grid-template-columns: 1fr; } }
</style>
