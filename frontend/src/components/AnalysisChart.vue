<template>
  <article class="chart-card" :class="cardClass">
    <div class="chart-head">
      <div>
        <p class="eyebrow">{{ chartTitle }}</p>
        <h3>{{ chartLabel }}</h3>
      </div>
      <span class="chart-badge">{{ chartTypeLabel }}</span>
    </div>

    <div v-if="echartsOption && !showEmptyState">
      <v-chart
        :key="renderKey"
        class="chart-view"
        autoresize
        :option="echartsOption"
        :update-options="{ notMerge: true, replaceMerge: ['xAxis', 'yAxis', 'series', 'legend', 'radar'] }"
      />
      <div v-if="isTopicChart && topicItems.length" class="topic-summary">
        <div v-for="item in topicItems" :key="item.name" class="topic-item">
          <div class="topic-label">
            <span class="topic-dot" :style="{ backgroundColor: item.color }"></span>
            <strong>{{ item.name }}</strong>
          </div>
          <span>{{ item.value }}</span>
        </div>
      </div>
    </div>

    <div v-else-if="isWordCloud" class="word-cloud">
      <span
        v-for="word in chart.words || []"
        :key="word.name"
        class="word-pill"
        :style="wordStyle(word.value)"
      >
        {{ word.name }}
      </span>
    </div>

    <div v-else class="empty-chart">{{ emptyMessage }}</div>
  </article>
</template>

<script setup>
import { computed, provide } from "vue";
import VChart, { THEME_KEY } from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { BarChart, FunnelChart, LineChart, PieChart, RadarChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, LegendComponent, RadarComponent, TooltipComponent } from "echarts/components";

use([
  CanvasRenderer,
  BarChart,
  PieChart,
  LineChart,
  RadarChart,
  FunnelChart,
  DataZoomComponent,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  RadarComponent,
]);
provide(THEME_KEY, "light");

const props = defineProps({
  chart: { type: Object, required: true },
});

const PIE_COLORS = ["#0f766e", "#f59e0b", "#dc2626", "#2563eb", "#7c3aed", "#9333ea", "#0ea5e9", "#94a3b8"];
const CHART_NAME_MAP = {
  bar: "柱状图",
  pie: "饼图",
  line: "折线图",
  radar: "雷达图",
  funnel: "漏斗图",
  histogram: "直方图",
  boxplot: "箱线图",
  wordcloud: "词云图",
};
const QUESTION_LABEL_MAP = { __topics__: "文本主题分布", __keywords__: "关键词词云", __sentiment__: "情绪分布" };
const QUESTION_TYPE_MAP = {
  single_choice: "单选题",
  multiple_choice: "多选题",
  numeric: "数值题",
  likert: "量表题",
  text: "主观题",
};

const isWordCloud = computed(() => props.chart?.chart?.chart_type === "wordcloud");
const chartId = computed(() => String(props.chart?.question_id || ""));
const isSentiment = computed(() => chartId.value.endsWith("__sentiment") || chartId.value === "__sentiment__");
const isTopicChart = computed(() => chartId.value.endsWith("__topics") || chartId.value === "__topics__");
const isHorizontalBar = computed(
  () => props.chart?.chart?.chart_type === "bar" && props.chart?.chart?.orientation === "horizontal"
);
const dataCount = computed(() => props.chart?.labels?.length || props.chart?.values?.length || 0);

const cardClass = computed(() => ({
  "chart-card--wide": isHorizontalBar.value,
  "chart-card--tall": isHorizontalBar.value && dataCount.value <= 4,
  "chart-card--medium": isHorizontalBar.value && dataCount.value > 4 && dataCount.value <= 8,
  "chart-card--topic": isTopicChart.value,
}));

const chartLabel = computed(() => {
  const questionId = props.chart?.question_id || "";
  const questionText = String(props.chart?.question_text || "").trim();
  if (QUESTION_LABEL_MAP[questionId]) return QUESTION_LABEL_MAP[questionId];
  if (questionText) return `${questionId} · ${questionText}`;
  return questionId || "统计图";
});
const chartTitle = computed(() => QUESTION_TYPE_MAP[props.chart?.question_type] || "统计");
const chartTypeLabel = computed(() => CHART_NAME_MAP[props.chart?.chart?.chart_type] || "图表");
const renderKey = computed(
  () => `${props.chart?.question_id || "chart"}:${props.chart?.chart?.chart_type || "unknown"}`
);
const emptyMessage = computed(() => props.chart?.empty_message || "当前没有可绘制的数据");
const showEmptyState = computed(() => isSentiment.value && props.chart?.has_data === false);

const topicItems = computed(() => {
  const labels = props.chart?.labels || [];
  const values = props.chart?.series?.[0]?.data || [];
  const base = labels.map((name, index) => ({
    name,
    value: values[index] || 0,
    color: PIE_COLORS[index % PIE_COLORS.length],
  }));
  if (!isTopicChart.value || base.length <= 6) return base;
  const sorted = [...base].sort((a, b) => b.value - a.value);
  const head = sorted.slice(0, 6);
  const otherValue = sorted.slice(6).reduce((sum, item) => sum + Number(item.value || 0), 0);
  return otherValue > 0 ? [...head, { name: "其他", value: otherValue, color: "#94a3b8" }] : head;
});

// 截断图表标签文本，驱动当前页面的数据流和交互流程。
function truncateLabel(label, max = 12) {
  if (typeof label !== "string") return label;
  return label.length > max ? `${label.slice(0, max)}...` : label;
}

const baseAnimation = {
  animation: true,
  animationDuration: 900,
  animationDurationUpdate: 600,
  animationEasing: "cubicOut",
  animationDelay: (idx) => idx * 40,
};

const echartsOption = computed(() => {
  const chartType = props.chart?.chart?.chart_type;
  const labels = props.chart?.labels || [];
  const values = props.chart?.series?.[0]?.data || [];
  const maxValue = values.length ? Math.max(...values) : 0;

  if (chartType === "bar") {
    const horizontal = props.chart?.chart?.orientation === "horizontal";
    const truncatedLabels = labels.map((label) => (horizontal ? truncateLabel(label, 18) : truncateLabel(label, 10)));
    return {
      ...baseAnimation,
      color: ["#0f766e"],
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, confine: true },
      grid: {
        left: horizontal ? 130 : 56,
        right: horizontal ? 36 : 24,
        top: 28,
        bottom: horizontal ? 40 : 86,
        outerBoundsMode: "same",
      },
      xAxis: horizontal
        ? { type: "value", max: maxValue > 0 ? maxValue + 0.5 : null, axisLabel: { margin: 12 } }
        : {
            type: "category",
            data: truncatedLabels,
            axisLabel: { interval: 0, rotate: labels.length > 6 ? 35 : 15, width: 90, overflow: "truncate", margin: 14 },
          },
      yAxis: horizontal
        ? { type: "category", data: truncatedLabels, axisLabel: { width: 120, overflow: "truncate", margin: 12 } }
        : { type: "value" },
      dataZoom: horizontal && labels.length > 8
        ? [{ type: "inside", yAxisIndex: 0 }, { type: "slider", yAxisIndex: 0, width: 12, right: 6 }]
        : [],
      series: [
        {
          type: "bar",
          data: values,
          barWidth: horizontal && labels.length <= 4 ? 38 : "52%",
          barCategoryGap: horizontal && labels.length <= 4 ? "26%" : "20%",
          label: { show: true, position: horizontal ? "right" : "top", distance: horizontal ? 8 : 6 },
        },
      ],
    };
  }

  if (chartType === "line") {
    return {
      ...baseAnimation,
      color: ["#0ea5e9"],
      tooltip: { trigger: "axis" },
      grid: { left: 56, right: 24, top: 28, bottom: 54, outerBoundsMode: "same" },
      xAxis: {
        type: "category",
        data: labels.map((v) => truncateLabel(v, 10)),
        axisLabel: { interval: 0, rotate: labels.length > 6 ? 35 : 15, margin: 14 },
      },
      yAxis: { type: "value" },
      series: [{ type: "line", smooth: true, data: values, symbolSize: 8, lineStyle: { width: 3 } }],
    };
  }

  if (chartType === "radar") {
    const ceiling = maxValue > 0 ? Math.ceil(maxValue * 1.25) : 1;
    return {
      ...baseAnimation,
      color: ["#7c3aed"],
      tooltip: {},
      radar: {
        radius: "64%",
        indicator: labels.map((name) => ({ name: truncateLabel(name, 12), max: ceiling })),
      },
      series: [{ type: "radar", data: [{ value: values, name: "分布" }], areaStyle: { opacity: 0.16 } }],
    };
  }

  if (chartType === "funnel") {
    const funnelData = labels.map((name, idx) => ({ name, value: values[idx] || 0 }))
      .sort((a, b) => b.value - a.value);
    return {
      ...baseAnimation,
      tooltip: { trigger: "item", formatter: "{b}: {c}" },
      series: [
        {
          type: "funnel",
          left: "8%",
          top: 26,
          bottom: 10,
          width: "82%",
          minSize: "12%",
          maxSize: "90%",
          sort: "descending",
          gap: 4,
          label: { show: true, position: "inside", formatter: "{b}: {c}" },
          itemStyle: { borderColor: "#fff", borderWidth: 2 },
          data: funnelData,
        },
      ],
    };
  }

  if (chartType === "pie") {
    const pieDataRaw = labels.map((name, index) => ({ name, value: values[index] || 0 }));
    const pieDataSource = isTopicChart.value
      ? [...pieDataRaw].sort((a, b) => Number(b.value || 0) - Number(a.value || 0))
      : pieDataRaw;
    const pieTop = isTopicChart.value ? pieDataSource.slice(0, 6) : pieDataSource;
    const pieOtherValue = isTopicChart.value
      ? pieDataSource.slice(6).reduce((sum, item) => sum + Number(item.value || 0), 0)
      : 0;
    const pieData = isTopicChart.value && pieOtherValue > 0
      ? [...pieTop, { name: "其他", value: pieOtherValue }]
      : pieTop;

    return {
      ...baseAnimation,
      tooltip: {
        trigger: "item",
        formatter: (params) => {
          const rawName = params?.data?.rawName || params?.name || "";
          return `${rawName}<br/>${params?.value || 0} (${params?.percent || 0}%)`;
        },
      },
      legend: {
        show: true,
        type: "scroll",
        orient: "vertical",
        right: 0,
        top: "middle",
        bottom: 16,
        width: isTopicChart.value ? 130 : 110,
        formatter: (name) => truncateLabel(String(name || ""), isTopicChart.value ? 8 : 12),
      },
      color: PIE_COLORS,
      series: [
        {
          type: "pie",
          radius: isTopicChart.value ? ["40%", "72%"] : ["36%", "68%"],
          center: isTopicChart.value ? ["36%", "48%"] : ["50%", "46%"],
          minShowLabelAngle: 8,
          label: isTopicChart.value
            ? { show: true, formatter: "{d}%", fontSize: 12 }
            : { show: true, formatter: "{b}\n{d}%", overflow: "truncate" },
          labelLine: { show: !isTopicChart.value },
          data: pieData.map((item) => ({
            name: truncateLabel(item.name, isTopicChart.value ? 8 : 20),
            rawName: item.name,
            value: item.value,
          })),
        },
      ],
    };
  }

  if (chartType === "histogram") {
    const bucketValues = Array.isArray(props.chart?.values) ? props.chart.values : [];
    if (!bucketValues.length) return null;
    const bins = 8;
    const min = Math.min(...bucketValues);
    const max = Math.max(...bucketValues);
    const step = Math.max((max - min) / bins, 1);
    const bucketCounts = Array.from({ length: bins }, () => 0);
    bucketValues.forEach((value) => {
      const index = Math.min(Math.floor((value - min) / step), bins - 1);
      bucketCounts[index] += 1;
    });
    return {
      ...baseAnimation,
      color: ["#2563eb"],
      tooltip: { trigger: "axis" },
      grid: { left: 56, right: 26, top: 24, bottom: 54, outerBoundsMode: "same" },
      xAxis: {
        type: "category",
        axisLabel: { margin: 14 },
        data: bucketCounts.map((_, index) => {
          const start = min + step * index;
          const end = start + step;
          return `${start.toFixed(1)}-${end.toFixed(1)}`;
        }),
      },
      yAxis: { type: "value" },
      series: [{ type: "bar", data: bucketCounts, barWidth: "70%" }],
    };
  }

  if (chartType === "boxplot") {
    const stats = props.chart?.stats || {};
    return {
      ...baseAnimation,
      color: ["#7c3aed", "#0f766e", "#ea580c"],
      tooltip: { trigger: "axis" },
      grid: { left: 56, right: 24, top: 28, bottom: 48, outerBoundsMode: "same" },
      xAxis: { type: "category", data: ["最小值", "均值", "最大值"], axisLabel: { margin: 14 } },
      yAxis: { type: "value" },
      series: [
        {
          type: "bar",
          data: [stats.min || 0, stats.mean || 0, stats.max || 0],
          barWidth: "52%",
          label: { show: true, position: "top" },
        },
      ],
    };
  }

  return null;
});

// 计算词云词条样式，驱动当前页面的数据流和交互流程。
function wordStyle(value) {
  const size = Math.max(14, Math.min(34, 14 + value * 2));
  return { fontSize: `${size}px` };
}
</script>

<style scoped>
.chart-card {
  background: #ffffff;
  border-radius: 24px;
  border: 1px solid #dbe4ef;
  padding: 22px;
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.08);
}
.chart-card--wide { grid-column: 1 / -1; }
.chart-card--medium .chart-view { height: 360px; }
.chart-card--tall .chart-view { height: 390px; }
.chart-card--topic .chart-view { height: 360px; }
@media (max-width: 960px) { .chart-card--wide { grid-column: 1 / -1; } }
.chart-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.eyebrow { margin: 0 0 4px; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #64748b; }
.chart-head h3 { margin: 0; font-size: 18px; color: #0f172a; }
.chart-badge { padding: 6px 10px; border-radius: 999px; background: #ecfeff; color: #0f766e; font-size: 12px; }
.chart-view { height: 300px; }
.word-cloud { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; min-height: 140px; }
.topic-summary { display: grid; gap: 10px; margin-top: 16px; }
.topic-item { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 12px; background: #f8fafc; color: #334155; }
.topic-label { display: flex; align-items: center; gap: 10px; }
.topic-dot { width: 12px; height: 12px; border-radius: 999px; flex: 0 0 auto; }
.word-pill { display: inline-flex; align-items: center; padding: 10px 16px; border-radius: 999px; background: linear-gradient(135deg, #fef3c7, #dbeafe); color: #1e293b; font-weight: 600; }
.empty-chart { min-height: 140px; display: grid; place-items: center; color: #64748b; background: #f8fafc; border-radius: 18px; }
</style>
