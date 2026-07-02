<template>
  <section class="page-card report-page">
    <div class="panel-head">
      <div>
        <h2 class="page-title">分析报告</h2>
        <p class="page-subtitle">展示 TopN 洞察图表与 LLM 总结。</p>
      </div>
      <router-link class="link-button" to="/analysis">返回分析页</router-link>
    </div>

    <div v-if="analysis" class="report-layout">
      <aside class="report-summary">
        <div class="summary-box"><span>样本数</span><strong>{{ analysis.sample_size || 0 }}</strong></div>
        <div class="summary-box"><span>客观题</span><strong>{{ analysis.question_breakdown?.objective || 0 }}</strong></div>
        <div class="summary-box"><span>主观题</span><strong>{{ analysis.question_breakdown?.subjective || 0 }}</strong></div>
        <div class="summary-box"><span>TopN</span><strong>{{ topNIds.length }}</strong></div>
        <div class="summary-box"><span>LLM 来源</span><strong>{{ displayLlmSource }}</strong></div>
      </aside>

      <div class="report-content">
        <section v-if="filteredTopnCharts.length" class="report-block">
          <h3>TopN 图表</h3>
          <div class="chart-grid">
            <div v-for="chart in filteredTopnCharts" :key="chartKey(chart)" class="report-chart-item">
              <AnalysisChart :chart="chart" />
            </div>
          </div>
        </section>

        <section class="report-block">
          <h3>LLM 总结</h3>
          <div v-if="analysis.llm_analysis" v-html="formattedReport"></div>
          <p v-else class="muted-note">当前无 LLM 总结。请在分析页启用 NLP 与 LLM 后重新生成分析。</p>
        </section>
      </div>
    </div>

    <div v-else class="empty-state">
      <p>暂无分析结果，请先在分析页运行任务。</p>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { marked } from "marked";
import AnalysisChart from "../components/AnalysisChart.vue";
import { getAnalysisResult } from "../utils/analysisSession";

const analysis = ref(getAnalysisResult());

const formattedReport = computed(() => marked.parse(String(analysis.value?.llm_analysis || "")));
const topNIds = computed(() =>
  (Array.isArray(analysis.value?.top_insights) ? analysis.value.top_insights : []).map((i) => i.question_id)
);

const displayLlmSource = computed(() => {
  const src = String(analysis.value?.llm_source || "api").toLowerCase();
  return src === "local_lora" ? "LOCAL LORA" : "API";
});

const filteredTopnCharts = computed(() => {
  const charts = Array.isArray(analysis.value?.report_charts)
    ? analysis.value.report_charts
    : Array.isArray(analysis.value?.charts)
      ? analysis.value.charts
      : [];
  const ids = new Set(topNIds.value);
  return charts.filter((chart) => ids.has(chart.question_id) || String(chart.question_id || "").startsWith("__"));
});

// 处理页面交互逻辑，驱动当前页面的数据流和交互流程。
function chartKey(chart) {
  return `${chart.question_id || chart.title || "chart"}-${chart.chart?.chart_type || "bar"}`;
}
</script>

<style scoped>
.panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
.link-button { padding: 11px 16px; border-radius: 14px; border: 1px solid var(--line); text-decoration: none; color: var(--text-main); background: #fff; }
.report-layout { display: grid; grid-template-columns: 260px 1fr; gap: 20px; }
.report-summary { display: grid; gap: 14px; align-content: start; }
.summary-box, .report-block { background: #fff; border: 1px solid var(--line); border-radius: 20px; padding: 18px; }
.summary-box span { display: block; color: var(--text-soft); margin-bottom: 8px; }
.summary-box strong { font-size: 28px; }
.report-content { display: grid; gap: 16px; }
.report-block h3 { margin-top: 0; }
.chart-grid { display: grid; gap: 14px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.muted-note { color: var(--text-soft); }
.empty-state { color: var(--text-soft); padding: 10px; }
@media (max-width: 960px) { .report-layout { grid-template-columns: 1fr; } .chart-grid { grid-template-columns: 1fr; } }
</style>
