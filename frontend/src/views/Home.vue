<template>
  <section class="home-grid">
    <article class="page-card hero-card">
      <p class="hero-kicker">Start Smarter</p>
      <h2 class="page-title">从上传到报告，一条流完成问卷洞察</h2>
      <p class="page-subtitle">
        支持多批次、题型识别、评分排序、NLP 主题与情绪分析，并将结果统一生成可解释报告。
      </p>
      <div class="hero-actions">
        <router-link class="hero-button primary" to="/upload">上传问卷</router-link>
        <router-link class="hero-button" to="/analysis">开始分析</router-link>
      </div>
    </article>

    <div class="stats-column">
      <article class="page-card stat-tile">
        <span>批次</span>
        <h3>{{ summary.batchCount }}</h3>
        <p>当前会话已记录的批次数</p>
      </article>
      <article class="page-card stat-tile">
        <span>题目</span>
        <h3>{{ summary.questionCount }}</h3>
        <p>最近一次分析包含的题目数</p>
      </article>
      <article class="page-card stat-tile">
        <span>样本</span>
        <h3>{{ summary.sampleSize }}</h3>
        <p>最近一次分析的受访者样本量</p>
      </article>
    </div>

    <article class="page-card quick-card">
      <h3>推荐操作</h3>
      <div class="quick-list">
        <router-link to="/analysis">1. 进入分析页，选择性能模式并生成分析</router-link>
        <router-link to="/question-stats">2. 在题目统计页切换图表并核对结果</router-link>
        <router-link to="/report">3. 生成报告并导出结论</router-link>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed } from "vue";

const summary = computed(() => {
  const batchRaw = localStorage.getItem("eiq.analysis.batchIds");
  const resultRaw = localStorage.getItem("eiq.analysis.result");
  let batchCount = 0;
  let questionCount = 0;
  let sampleSize = 0;
  try {
    const batchIds = batchRaw ? JSON.parse(batchRaw) : [];
    batchCount = Array.isArray(batchIds) ? batchIds.length : 0;
  } catch {
    batchCount = 0;
  }
  try {
    const result = resultRaw ? JSON.parse(resultRaw) : {};
    questionCount = Number(result?.question_count || 0);
    sampleSize = Number(result?.sample_size || 0);
  } catch {
    questionCount = 0;
    sampleSize = 0;
  }
  return { batchCount, questionCount, sampleSize };
});
</script>

<style scoped>
.home-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 18px;
}
.hero-card {
  min-height: 320px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background:
    linear-gradient(135deg, rgba(15, 118, 110, 0.1), rgba(14, 165, 233, 0.12)),
    var(--bg-panel);
}
.hero-kicker {
  margin: 0 0 14px;
  color: #0f766e;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 12px;
}
.hero-actions {
  display: flex;
  gap: 10px;
  margin-top: 22px;
}
.hero-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 11px 14px;
  border-radius: 12px;
  text-decoration: none;
  color: var(--text-main);
  border: 1px solid var(--line);
  background: #fff;
  font-weight: 700;
}
.hero-button.primary {
  background: linear-gradient(135deg, #0f766e, #0ea5e9);
  color: #fff;
  border-color: transparent;
}
.stats-column {
  display: grid;
  gap: 18px;
}
.stat-tile span {
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
}
.stat-tile h3 {
  margin: 6px 0;
  font-size: 30px;
  font-weight: 800;
}
.stat-tile p {
  margin: 0;
  color: var(--text-soft);
}
.quick-card {
  grid-column: 1 / -1;
}
.quick-card h3 {
  margin: 0 0 12px;
  font-size: 20px;
  font-weight: 800;
}
.quick-list {
  display: grid;
  gap: 8px;
}
.quick-list a {
  display: block;
  text-decoration: none;
  color: #0f172a;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 11px 12px;
  background: #fff;
  font-weight: 600;
}
@media (max-width: 960px) {
  .home-grid { grid-template-columns: 1fr; }
}
</style>
