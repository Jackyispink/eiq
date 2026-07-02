<template>
  <section class="stats-page">
    <div class="page-card header-row">
      <div>
        <h2 class="page-title">题目统计页</h2>
        <p class="page-subtitle">按题型查看每道题统计结果，可切换图表，并查看可解释文本分析。</p>
      </div>
      <router-link to="/report" class="back-link">返回分析报告</router-link>
    </div>

    <nav class="page-card top-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <div v-if="!allRows.length" class="page-card empty-note">当前没有可展示的题目统计数据。</div>
    <div v-else-if="!filteredRows.length" class="page-card empty-note">当前栏目暂无题目数据。</div>

    <article v-for="row in filteredRows" :key="row.question_id" class="page-card row-card">
      <div class="left-col">
        <p class="q-meta">{{ mapType(row.question_type) }} · {{ row.question_id }}</p>
        <h3 class="q-title">{{ row.question_text || "未命名题目" }}</h3>

        <template v-if="isChoiceType(row.question_type)">
          <div class="option-table">
            <div class="th">选项</div>
            <div class="th">人数</div>
            <template v-for="item in row.option_rows" :key="`${row.question_id}-${item.option}`">
              <div class="td option">{{ item.option }}</div>
              <div class="td count">{{ item.count }}</div>
            </template>
          </div>
        </template>

        <template v-else-if="row.question_type === 'numeric'">
          <div class="stats-grid">
            <div class="stat-item">均值：{{ toFixed(row.features?.mean) }}</div>
            <div class="stat-item">标准差：{{ toFixed(row.features?.std) }}</div>
            <div class="stat-item">最小值：{{ toFixed(row.features?.min) }}</div>
            <div class="stat-item">最大值：{{ toFixed(row.features?.max) }}</div>
            <div class="stat-item">离群比例：{{ toPct(row.features?.outlier) }}</div>
          </div>
        </template>

        <template v-else-if="row.question_type === 'text'">
          <div class="stats-grid">
            <div class="stat-item">回答数：{{ row.text_analysis?.response_count || 0 }}</div>
            <div class="stat-item">
              情绪分布：正向 {{ toPct(row.text_analysis?.sentiment?.positive) }} / 中性
              {{ toPct(row.text_analysis?.sentiment?.neutral) }} / 负向
              {{ toPct(row.text_analysis?.sentiment?.negative) }}
            </div>
          </div>

          <div class="insight-panels">
            <section class="insight-card">
              <h4>Top关键词统计</h4>
              <div v-if="(row.text_analysis?.keyword_stats || []).length" class="insight-table keyword-table">
                <div class="th">关键词</div>
                <div class="th">频次</div>
                <div class="th">覆盖率</div>
                <div class="th">情绪倾向</div>
                <template
                  v-for="item in (row.text_analysis?.keyword_stats || []).slice(0, 12)"
                  :key="`${row.question_id}-kw-${item.keyword}`"
                >
                  <div class="td">{{ item.keyword }}</div>
                  <div class="td">{{ item.count }}</div>
                  <div class="td">{{ toPct(item.coverage) }}</div>
                  <div class="td">{{ sentimentBrief(item.sentiment) }}</div>
                </template>
              </div>
              <div v-else class="mini-empty">暂无关键词统计</div>
            </section>

            <section class="insight-card">
              <h4>主题-情绪交叉</h4>
              <div v-if="(row.text_analysis?.topic_sentiment || []).length" class="insight-table topic-table">
                <div class="th">主题</div>
                <div class="th">样本数</div>
                <div class="th">正向</div>
                <div class="th">中性</div>
                <div class="th">负向</div>
                <template
                  v-for="item in (row.text_analysis?.topic_sentiment || []).slice(0, 10)"
                  :key="`${row.question_id}-topic-${item.topic}`"
                >
                  <div class="td">{{ item.topic }}</div>
                  <div class="td">{{ item.count }}</div>
                  <div class="td">{{ toPct(item.sentiment?.positive) }}</div>
                  <div class="td">{{ toPct(item.sentiment?.neutral) }}</div>
                  <div class="td">{{ toPct(item.sentiment?.negative) }}</div>
                </template>
              </div>
              <div v-else class="mini-empty">暂无主题情绪交叉数据</div>
            </section>

            <section class="insight-card">
              <h4>代表性原句</h4>
              <div v-if="(row.text_analysis?.representative_quotes || []).length" class="quote-groups">
                <div
                  v-for="topic in (row.text_analysis?.representative_quotes || []).slice(0, 6)"
                  :key="`${row.question_id}-quote-${topic.topic}`"
                  class="quote-group"
                >
                  <p class="quote-topic">{{ topic.topic }}</p>
                  <p
                    v-for="(q, idx) in topic.quotes"
                    :key="`${row.question_id}-quote-${topic.topic}-${idx}`"
                    class="quote-line"
                  >
                    {{ q.text }}
                  </p>
                </div>
              </div>
              <div v-else class="mini-empty">暂无可展示的代表性原句</div>
            </section>
          </div>
        </template>
      </div>

      <div class="right-col">
        <template v-if="isChoiceType(row.question_type)">
          <div class="chart-tools">
            <label>
              选择绘图
              <select v-model="chartTypeMap[row.question_id]">
                <option value="bar">柱状图</option>
                <option value="pie">饼图</option>
                <option value="line">折线图</option>
                <option value="radar">雷达图</option>
                <option value="funnel">漏斗图</option>
              </select>
            </label>
          </div>
          <AnalysisChart :chart="buildChoiceChart(row)" />
        </template>

        <template v-else-if="row.question_type === 'numeric'">
          <div class="chart-tools">
            <label>
              选择绘图
              <select v-model="chartTypeMap[row.question_id]">
                <option value="histogram">直方图</option>
                <option value="boxplot">箱线图</option>
              </select>
            </label>
          </div>
          <AnalysisChart :chart="buildNumericChart(row)" />
        </template>

        <template v-else-if="row.question_type === 'text'">
          <div class="text-charts">
            <AnalysisChart :chart="buildKeywordChart(row)" />
            <AnalysisChart :chart="buildTopicChart(row)" />
            <AnalysisChart :chart="buildTextSentimentChart(row)" />
          </div>
        </template>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import AnalysisChart from "../components/AnalysisChart.vue";
import { getAnalysisResult } from "../utils/analysisSession";

const analysis = ref(getAnalysisResult() || {});
const activeTab = ref("choice");
const chartTypeMap = ref({});

const tabs = [
  { key: "choice", label: "选择题" },
  { key: "likert", label: "量表题" },
  { key: "numeric", label: "填空题" },
  { key: "text", label: "主观题" },
];

const allRows = computed(() => {
  const q = Array.isArray(analysis.value?.question_results) ? analysis.value.question_results : [];
  if (q.length) return q;

  const scores = analysis.value?.scores || {};
  return Object.values(scores).map((s) => {
    const features = s.features || {};
    const distribution = features.distribution || {};
    return {
      question_id: s.question_id,
      question_text: s.question_text || "",
      question_type: s.question_type || s.type || "unknown",
      features,
      raw_values: [],
      option_rows: Object.entries(distribution)
        .map(([option, count]) => ({ option, count: Number(count || 0) }))
        .sort((a, b) => b.count - a.count),
      text_analysis: {},
    };
  });
});

const filteredRows = computed(() => {
  if (activeTab.value === "choice") {
    return allRows.value.filter((r) => ["single_choice", "multiple_choice"].includes(r.question_type));
  }
  if (activeTab.value === "likert") {
    return allRows.value.filter((r) => r.question_type === "likert");
  }
  if (activeTab.value === "numeric") {
    return allRows.value.filter((r) => r.question_type === "numeric");
  }
  if (activeTab.value === "text") {
    return allRows.value.filter((r) => r.question_type === "text");
  }
  return [];
});

watch(
  allRows,
  (list) => {
    const next = { ...chartTypeMap.value };
    list.forEach((row) => {
      if (!next[row.question_id]) next[row.question_id] = row.question_type === "numeric" ? "histogram" : "bar";
    });
    chartTypeMap.value = next;
  },
  { immediate: true }
);

// 判断当前数据类型，驱动当前页面的数据流和交互流程。
function isChoiceType(type) {
  return ["single_choice", "multiple_choice", "likert"].includes(type);
}

// 映射展示类型，驱动当前页面的数据流和交互流程。
function mapType(type) {
  if (type === "single_choice") return "单选题";
  if (type === "multiple_choice") return "多选题";
  if (type === "likert") return "量表题";
  if (type === "numeric") return "填空题（数值）";
  if (type === "text") return "主观题";
  return type || "题目";
}

// 转换数值展示格式，驱动当前页面的数据流和交互流程。
function toFixed(v) {
  return Number(v || 0).toFixed(2);
}

// 转换数值展示格式，驱动当前页面的数据流和交互流程。
function toPct(v) {
  return `${(Number(v || 0) * 100).toFixed(2)}%`;
}

// 生成情感摘要文本，驱动当前页面的数据流和交互流程。
function sentimentBrief(s) {
  const positive = Number(s?.positive || 0);
  const neutral = Number(s?.neutral || 0);
  const negative = Number(s?.negative || 0);
  if (negative >= positive && negative >= neutral) return "偏负向";
  if (neutral >= positive && neutral >= negative) return "偏中性";
  return "偏正向";
}

// 构建接口请求参数，驱动当前页面的数据流和交互流程。
function buildChoiceChart(row) {
  const selected = chartTypeMap.value[row.question_id] || "bar";
  const labels = (row.option_rows || []).map((i) => i.option);
  const data = (row.option_rows || []).map((i) => i.count);
  return {
    question_id: row.question_id,
    question_text: row.question_text,
    question_type: row.question_type,
    chart: {
      chart_type: selected,
      orientation: row.question_type === "multiple_choice" && selected === "bar" ? "horizontal" : "vertical",
    },
    labels,
    series: [{ name: "count", data }],
  };
}

// 构建接口请求参数，驱动当前页面的数据流和交互流程。
function buildNumericChart(row) {
  const selected = chartTypeMap.value[row.question_id] || "histogram";
  return {
    question_id: row.question_id,
    question_text: row.question_text,
    question_type: "numeric",
    chart: { chart_type: selected, orientation: "vertical" },
    values: Array.isArray(row.raw_values) ? row.raw_values : [],
    stats: {
      mean: row.features?.mean || 0,
      std: row.features?.std || 0,
      min: row.features?.min || 0,
      max: row.features?.max || 0,
      outlier: row.features?.outlier || 0,
    },
  };
}

// 构建接口请求参数，驱动当前页面的数据流和交互流程。
function buildTopicChart(row) {
  const topics = row.text_analysis?.topics || [];
  return {
    question_id: `${row.question_id}__topics`,
    question_text: `${row.question_text}（主题分布）`,
    question_type: "text",
    chart: { chart_type: "pie" },
    labels: topics.map((t) => t.topic),
    series: [{ name: "topics", data: topics.map((t) => t.count) }],
  };
}

// 构建接口请求参数，驱动当前页面的数据流和交互流程。
function buildKeywordChart(row) {
  return {
    question_id: `${row.question_id}__keywords`,
    question_text: `${row.question_text}（关键词）`,
    question_type: "text",
    chart: { chart_type: "wordcloud" },
    words: row.text_analysis?.keywords || [],
  };
}

// 构建接口请求参数，驱动当前页面的数据流和交互流程。
function buildTextSentimentChart(row) {
  const s = row.text_analysis?.sentiment || {};
  return {
    question_id: `${row.question_id}__sentiment`,
    question_text: `${row.question_text}（情绪分布）`,
    question_type: "text",
    chart: { chart_type: "pie" },
    labels: ["positive", "neutral", "negative"],
    series: [{ name: "sentiment", data: [s.positive || 0, s.neutral || 0, s.negative || 0] }],
    has_data: (s.positive || 0) + (s.neutral || 0) + (s.negative || 0) > 0,
  };
}
</script>

<style scoped>
.stats-page { display: grid; gap: 16px; }
.header-row { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.back-link { padding: 9px 12px; border: 1px solid var(--line); border-radius: 10px; text-decoration: none; color: var(--text-main); background: #fff; }

.top-tabs { display: flex; align-items: center; gap: 10px; padding: 10px 12px; }
.tab-btn { border: none; background: transparent; padding: 10px 14px; border-radius: 10px; color: #334155; cursor: pointer; font-weight: 600; }
.tab-btn:hover { background: #f1f5f9; }
.tab-btn.active { background: #e0f2fe; color: #0c4a6e; }

.empty-note { color: var(--text-soft); }
.row-card { display: grid; grid-template-columns: 1.08fr 1.42fr; gap: 16px; }
.q-meta { margin: 0; font-size: 13px; color: var(--text-soft); }
.q-title { margin: 6px 0 12px; }

.option-table { display: grid; grid-template-columns: 1fr 90px; border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
.th { background: #f8fafc; font-weight: 700; padding: 10px 12px; border-bottom: 1px solid var(--line); }
.td { padding: 10px 12px; border-bottom: 1px solid #eef2f7; }
.td.count { text-align: right; font-weight: 700; color: #0f766e; }
.option-table .td:nth-last-child(-n + 2) { border-bottom: none; }

.stats-grid { display: grid; gap: 8px; }
.stat-item { padding: 8px 10px; border-radius: 10px; background: #f8fafc; color: #334155; }

.insight-panels { margin-top: 12px; display: grid; gap: 12px; }
.insight-card { border: 1px solid var(--line); border-radius: 12px; padding: 10px; background: #fff; }
.insight-card h4 { margin: 0 0 8px; font-size: 14px; color: #0f172a; }
.mini-empty { padding: 8px; color: var(--text-soft); font-size: 13px; background: #f8fafc; border-radius: 8px; }

.insight-table { display: grid; gap: 0; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.keyword-table { grid-template-columns: 1.2fr 72px 92px 96px; }
.topic-table { grid-template-columns: 1.3fr 68px 76px 76px 76px; }
.insight-table .th { background: #f8fafc; font-weight: 700; padding: 8px 10px; border-bottom: 1px solid #e2e8f0; font-size: 13px; }
.insight-table .td { padding: 8px 10px; border-bottom: 1px solid #f1f5f9; font-size: 13px; color: #334155; }

.quote-groups { display: grid; gap: 8px; }
.quote-group { padding: 8px; border-radius: 10px; background: #f8fafc; }
.quote-topic { margin: 0 0 6px; font-weight: 700; color: #0f172a; font-size: 13px; }
.quote-line { margin: 0 0 4px; color: #334155; line-height: 1.6; font-size: 13px; }

.chart-tools { display: flex; justify-content: flex-end; margin-bottom: 8px; }
.chart-tools select { margin-left: 8px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 10px; }

.text-charts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.text-charts :deep(.chart-card:last-child) { grid-column: 1 / -1; }

@media (max-width: 1200px) {
  .row-card { grid-template-columns: 1fr; }
  .text-charts { grid-template-columns: 1fr; }
  .header-row { flex-direction: column; align-items: stretch; }
}
</style>
