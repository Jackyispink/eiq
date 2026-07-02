<template>
  <section class="analysis-page">
    <div class="page-card toolbar">
      <div>
        <h2 class="page-title">数据分析</h2>
        <p class="page-subtitle">选择批次与分析参数后，系统将后台异步执行并实时返回进度。</p>
      </div>

      <div class="toolbar-actions">
        <details class="batch-dropdown">
          <summary class="batch-summary">{{ batchSummaryText }}</summary>
          <div class="batch-menu">
            <label v-for="item in batchOptions" :key="item.value" class="batch-option">
              <input
                type="checkbox"
                :checked="selectedBatchIds.includes(item.value)"
                @change="toggleBatch(item.value)"
              />
              <span>{{ item.label }}</span>
            </label>
          </div>
        </details>

        <div class="selected-chips">
          <span v-for="id in selectedBatchIds" :key="id" class="chip">
            {{ formatBatchId(id) }}
            <button class="chip-close" @click="removeBatch(id)">x</button>
          </span>
        </div>

        <div class="toggle-wrap">
          <label class="toggle-item">
            <input v-model="includeNlp" type="checkbox" />
            <span>启用文本 NLP</span>
          </label>
          <label v-if="llmAvailable" class="toggle-item">
            <input v-model="includeLlm" type="checkbox" />
            <span>包含 LLM 报告</span>
          </label>
        </div>

        <label class="mode-select">
          分析模式
          <select v-model="performanceMode">
            <option value="fast">极速</option>
            <option value="balanced">平衡</option>
            <option value="accurate">精确</option>
          </select>
        </label>

        <label class="mode-select">
          LLM 来源
          <select v-model="llmSource">
            <option value="api">API</option>
            <option value="local_lora">本地 LoRA</option>
          </select>
        </label>

        <button class="primary-btn" :disabled="loading" @click="runAnalysis">
          {{ loading ? "分析中..." : "生成分析" }}
        </button>
        <router-link to="/question-stats" class="ghost-link">查看题目统计</router-link>
      </div>
    </div>

    <div v-if="taskStatus" class="page-card info-note">
      <p>任务状态：{{ taskStatus }} <span v-if="activeTaskId">({{ activeTaskId }})</span></p>
      <div v-if="loading || taskStatus === 'running' || taskStatus === 'queued'" class="progress-wrap">
        <div class="progress-bar">
          <div class="progress-inner" :style="{ width: `${taskProgress}%` }"></div>
        </div>
        <p class="progress-text">{{ stageText }} · {{ taskProgress.toFixed(0) }}%</p>
      </div>
    </div>

    <div v-if="errorMessage" class="page-card error-note">
      {{ errorMessage }}
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { createAnalysisTaskApi, getAnalysisTaskApi, getHistoryApi } from "../services/api";
import { getBatchIds, saveAnalysisResult, saveBatchIds } from "../utils/analysisSession";

const loading = ref(false);
const history = ref([]);
const selectedBatchIds = ref([]);
const includeNlp = ref(false);
const includeLlm = ref(false);
const llmSource = ref("api");
const errorMessage = ref("");
const taskStatus = ref("");
const activeTaskId = ref("");
const chartOverrides = ref({});
const performanceMode = ref("fast");
const taskProgress = ref(0);
const taskStage = ref("queued");
let pollingTimer = null;

const llmAvailable = computed(() => performanceMode.value !== "fast");

const STAGE_TEXT_MAP = {
  queued: "任务排队中",
  loading_data: "加载数据",
  detecting_question_types: "识别题型",
  extracting_features: "提取特征",
  scoring_questions: "题目打分",
  selecting_top_insights: "筛选 TopN",
  running_nlp: "执行 NLP",
  nlp_completed: "NLP 完成",
  skipping_nlp: "跳过 NLP",
  building_charts: "构建图表",
  generating_llm_report: "生成 LLM 报告",
  finalizing_result: "整理结果",
  completed: "任务完成",
  failed: "任务失败",
};

const stageText = computed(() => STAGE_TEXT_MAP[taskStage.value] || taskStage.value || "分析中");

const batchOptions = computed(() => {
  const savedBatchIds = normalizeArray(getBatchIds());
  const optionMap = new Map();
  savedBatchIds.forEach((batchId) => {
    if (!batchId) return;
    optionMap.set(batchId, { value: batchId, label: `${formatBatchId(batchId)} · 本地缓存` });
  });
  normalizeArray(history.value).forEach((item) => {
    normalizeArray(item?.batch_ids).forEach((batchId) => {
      if (!batchId) return;
      optionMap.set(batchId, {
        value: batchId,
        label: `${formatBatchId(batchId)} · ${item?.created_at || "历史记录"}`,
      });
    });
  });
  return Array.from(optionMap.values());
});

const batchSummaryText = computed(() => {
  if (!selectedBatchIds.value.length) return "选择历史批次";
  if (selectedBatchIds.value.length === 1) return `已选：${formatBatchId(selectedBatchIds.value[0])}`;
  return `已选 ${selectedBatchIds.value.length} 个批次`;
});

watch(performanceMode, (mode) => {
  if (mode === "fast") includeLlm.value = false;
});

onMounted(async () => {
  const batchIds = normalizeArray(getBatchIds());
  if (batchIds.length) selectedBatchIds.value = [...batchIds];
  await loadHistory();
});

onBeforeUnmount(() => stopPolling());

// 标准化数组输入，驱动当前页面的数据流和交互流程。
function normalizeArray(value) {
  return Array.isArray(value) ? value : [];
}

// 格式化页面展示文本，驱动当前页面的数据流和交互流程。
function formatBatchId(batchId) {
  const text = String(batchId || "");
  const parts = text.split("_");
  const timePart = parts.length >= 3 ? parts[1].slice(-6) : text.slice(-6);
  const tail = parts.length >= 3 ? parts[2] : text.slice(-4);
  return `${timePart}-${tail}`;
}

// 切换界面选中状态，驱动当前页面的数据流和交互流程。
function toggleBatch(batchId) {
  if (!batchId) return;
  if (selectedBatchIds.value.includes(batchId)) {
    selectedBatchIds.value = selectedBatchIds.value.filter((id) => id !== batchId);
  } else {
    selectedBatchIds.value = [...selectedBatchIds.value, batchId];
  }
}

// 移除界面选中项，驱动当前页面的数据流和交互流程。
function removeBatch(batchId) {
  selectedBatchIds.value = selectedBatchIds.value.filter((id) => id !== batchId);
}

// 加载后端数据，驱动当前页面的数据流和交互流程。
async function loadHistory() {
  try {
    const { data } = await getHistoryApi();
    history.value = data?.error ? [] : normalizeArray(data);
  } catch {
    history.value = [];
  }
}

// 构建接口请求参数，驱动当前页面的数据流和交互流程。
function buildAnalyzePayload() {
  const selected = normalizeArray(selectedBatchIds.value).filter(Boolean);
  const batchIds = selected.length ? selected : normalizeArray(getBatchIds()).filter(Boolean);
  return {
    batch_ids: batchIds,
    include_nlp: includeNlp.value,
    include_llm: llmAvailable.value ? includeLlm.value : false,
    llm_source: llmSource.value,
    performance_mode: performanceMode.value,
    chart_overrides: { ...chartOverrides.value },
  };
}

// 发起分析任务并处理结果，驱动当前页面的数据流和交互流程。
async function runAnalysis() {
  loading.value = true;
  errorMessage.value = "";
  taskStatus.value = "";
  taskProgress.value = 0;
  taskStage.value = "queued";

  try {
    const payload = buildAnalyzePayload();
    if (!payload.batch_ids.length) {
      window.alert("请先上传问卷数据或选择一个历史批次");
      return;
    }

    const { data } = await createAnalysisTaskApi(payload);
    if (data?.status === "completed" && data?.result) {
      taskStatus.value = "completed";
      taskProgress.value = 100;
      taskStage.value = "completed";
      saveAnalysisResult(data.result);
      saveBatchIds(normalizeArray(data.result?.batch_ids));
      return;
    }
    if (data?.error) {
      errorMessage.value = data.error;
      return;
    }

    activeTaskId.value = String(data?.task_id || "");
    taskStatus.value = String(data?.status || "queued");
    taskProgress.value = Number(data?.progress || 1);
    taskStage.value = String(data?.stage || "queued");

    if (!activeTaskId.value) {
      errorMessage.value = "创建任务失败";
      return;
    }
    startPollingTask(activeTaskId.value);
  } catch (error) {
    errorMessage.value = error?.response?.data?.error || error?.message || "分析请求失败";
  } finally {
    if (!pollingTimer) loading.value = false;
  }
}

// 启动页面轮询流程，驱动当前页面的数据流和交互流程。
function startPollingTask(taskId) {
  stopPolling();
  loading.value = true;
  pollingTimer = window.setInterval(async () => {
    try {
      const { data } = await getAnalysisTaskApi(taskId);
      if (data?.error) {
        stopPolling();
        loading.value = false;
        errorMessage.value = data.error;
        taskStatus.value = "failed";
        taskStage.value = "failed";
        return;
      }

      taskStatus.value = String(data?.status || "running");
      taskProgress.value = Number(data?.progress || taskProgress.value || 0);
      taskStage.value = String(data?.stage || taskStage.value || "running");

      if (data?.status === "completed" && data?.result) {
        stopPolling();
        loading.value = false;
        taskProgress.value = 100;
        taskStage.value = "completed";
        saveAnalysisResult(data.result);
        saveBatchIds(normalizeArray(data.result?.batch_ids));
        return;
      }
      if (data?.status === "failed") {
        stopPolling();
        loading.value = false;
        taskStage.value = "failed";
        errorMessage.value = data?.error || "分析任务执行失败";
      }
    } catch (error) {
      stopPolling();
      loading.value = false;
      taskStage.value = "failed";
      errorMessage.value = error?.response?.data?.error || error?.message || "轮询任务失败";
    }
  }, 3000);
}

// 停止页面轮询流程，驱动当前页面的数据流和交互流程。
function stopPolling() {
  if (pollingTimer) {
    window.clearInterval(pollingTimer);
    pollingTimer = null;
  }
}
</script>

<style scoped>
.analysis-page { display: grid; gap: 18px; }
.toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.toolbar-actions { display: grid; gap: 10px; justify-items: start; }
.batch-dropdown { position: relative; width: 360px; }
.batch-summary { list-style: none; cursor: pointer; padding: 11px 12px; border: 1px solid var(--line); border-radius: 12px; background: #fff; font-weight: 600; }
.batch-summary::-webkit-details-marker { display: none; }
.batch-menu { margin-top: 8px; padding: 10px; border: 1px solid var(--line); border-radius: 12px; background: #fff; width: 100%; max-height: 220px; overflow: auto; }
.batch-option { display: flex; gap: 8px; align-items: center; padding: 6px 0; font-size: 14px; }
.selected-chips { display: flex; flex-wrap: wrap; gap: 6px; max-width: 420px; }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 9px; border: 1px solid var(--line); border-radius: 999px; background: #f8fafc; font-size: 12px; }
.chip-close { border: none; background: transparent; cursor: pointer; color: var(--text-soft); }
.toggle-wrap { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 999px; background: #fff; }
.toggle-item { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; color: var(--text-main); }
.mode-select { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; }
.mode-select select { padding: 8px 10px; border: 1px solid var(--line); border-radius: 10px; background: #fff; }
.primary-btn { padding: 10px 16px; border: none; border-radius: 12px; background: linear-gradient(135deg, #0f766e, #0ea5a4); color: #fff; font-weight: 700; cursor: pointer; }
.primary-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.ghost-link { text-decoration: none; color: #0f766e; border: 1px solid #99f6e4; padding: 8px 12px; border-radius: 12px; background: #ecfeff; }
.info-note { font-size: 14px; color: var(--text-main); }
.progress-wrap { margin-top: 8px; }
.progress-bar { width: 100%; height: 10px; border-radius: 999px; background: #e2e8f0; overflow: hidden; }
.progress-inner { height: 100%; background: linear-gradient(90deg, #0f766e, #14b8a6); transition: width 0.3s ease; }
.progress-text { margin: 8px 0 0; color: var(--text-soft); }
.error-note { color: #b91c1c; border: 1px solid #fecaca; background: #fef2f2; }
@media (max-width: 960px) {
  .toolbar { flex-direction: column; }
  .batch-dropdown { width: 100%; }
  .selected-chips { max-width: 100%; }
}
</style>
