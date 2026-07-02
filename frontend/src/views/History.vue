<template>
  <section class="page-card history-page">
    <div class="panel-head">
      <div>
        <h2 class="page-title">历史记录</h2>
        <p class="page-subtitle">仅展示当前登录用户自己的分析历史。</p>
      </div>
      <button class="ghost-btn" @click="loadHistory">刷新</button>
    </div>

    <div v-if="errorMessage" class="empty-state">{{ errorMessage }}</div>

    <div v-else-if="history.length" class="history-list">
      <article v-for="item in history" :key="item.id" class="history-item">
        <div>
          <p class="history-batch" :title="item.batch_ids.join(', ')">
            {{ item.batch_ids.map(formatBatchId).join(", ") }}
          </p>
          <p class="history-time">{{ item.created_at }}</p>
        </div>
        <div class="actions">
          <button class="primary-btn" @click="openAnalysis(item.id)">打开</button>
          <button
            v-if="item.id > 0"
            class="danger-btn"
            :disabled="deletingId === item.id"
            @click="removeHistory(item.id)"
          >
            {{ deletingId === item.id ? "删除中..." : "删除" }}
          </button>
        </div>
      </article>
    </div>

    <div v-else class="empty-state">暂无历史记录</div>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { deleteHistoryApi, getAnalysisById, getHistoryApi } from "../services/api";
import { saveAnalysisResult, saveBatchIds } from "../utils/analysisSession";

const router = useRouter();
const history = ref([]);
const errorMessage = ref("");
const deletingId = ref(null);

onMounted(loadHistory);

// 格式化页面展示文本，驱动当前页面的数据流和交互流程。
function formatBatchId(batchId) {
  const text = String(batchId || "");
  if (text.length <= 6) return text;
  return text.slice(-6);
}

// 加载后端数据，驱动当前页面的数据流和交互流程。
async function loadHistory() {
  try {
    errorMessage.value = "";
    const { data } = await getHistoryApi();
    if (data?.error) {
      history.value = [];
      errorMessage.value = data.error;
      return;
    }
    history.value = Array.isArray(data) ? data : [];
  } catch (error) {
    history.value = [];
    errorMessage.value = error?.response?.data?.error || error?.message || "历史记录加载失败";
  }
}

// 打开历史分析记录，驱动当前页面的数据流和交互流程。
async function openAnalysis(id) {
  if (id < 0) {
    const item = history.value.find((entry) => entry.id === id);
    if (item?.batch_ids) {
      saveBatchIds(item.batch_ids);
      router.push("/analysis");
    }
    return;
  }

  try {
    const { data } = await getAnalysisById(id);
    if (data?.batch_ids) saveBatchIds(data.batch_ids);
    if (!data?.error) {
      saveAnalysisResult(data);
      router.push("/analysis");
    } else {
      errorMessage.value = data.error;
    }
  } catch (error) {
    errorMessage.value = error?.response?.data?.error || error?.message || "打开记录失败";
  }
}

// 移除界面选中项，驱动当前页面的数据流和交互流程。
async function removeHistory(id) {
  const ok = window.confirm("确认删除这条分析记录吗？删除后不可恢复。");
  if (!ok) return;
  deletingId.value = id;
  try {
    const { data } = await deleteHistoryApi(id);
    if (data?.error) {
      errorMessage.value = data.error;
      return;
    }
    await loadHistory();
  } catch (error) {
    errorMessage.value = error?.response?.data?.error || error?.message || "删除失败";
  } finally {
    deletingId.value = null;
  }
}
</script>

<style scoped>
.history-page { display: grid; gap: 20px; }
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.ghost-btn,
.primary-btn,
.danger-btn {
  padding: 10px 16px;
  border-radius: 14px;
  cursor: pointer;
  font-weight: 700;
  border: none;
}
.ghost-btn {
  border: 1px solid var(--line);
  background: #fff;
}
.primary-btn {
  background: var(--brand);
  color: #fff;
}
.danger-btn {
  background: #ef4444;
  color: #fff;
}
.danger-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.actions { display: flex; gap: 8px; }
.history-list { display: grid; gap: 14px; }
.history-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 18px;
  border-radius: 20px;
  border: 1px solid var(--line);
  background: #fff;
}
.history-batch { margin: 0 0 6px; font-weight: 700; }
.history-time { margin: 0; color: var(--text-soft); }
.empty-state {
  text-align: center;
  color: var(--text-soft);
  padding: 30px 0;
}
@media (max-width: 960px) {
  .panel-head,
  .history-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
