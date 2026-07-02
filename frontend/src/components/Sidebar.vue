<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-mark">E</span>
      <div>
        <h2>EIQ</h2>
        <p>Survey Analytics</p>
      </div>
    </div>

    <nav class="nav-links">
      <router-link to="/">首页</router-link>
      <router-link to="/upload">上传数据</router-link>
      <router-link to="/analysis">数据分析</router-link>
      <router-link to="/question-stats">题目统计</router-link>
      <router-link to="/report">分析报告</router-link>
      <router-link to="/chat">智能问答</router-link>
      <router-link to="/history">历史记录</router-link>
    </nav>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 254px;
  min-height: 100vh;
  padding: 24px 16px;
  background:
    linear-gradient(180deg, rgba(9, 53, 70, 0.96), rgba(24, 76, 63, 0.97)),
    #0b2d3a;
  color: #eff6ff;
  position: sticky;
  top: 0;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 22px;
  padding: 12px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.1);
}
.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #f59e0b, #fb7185);
  color: #fff;
  font-weight: 800;
  font-size: 20px;
}
.brand h2 { margin: 0; font-size: 20px; font-weight: 800; }
.brand p { margin: 2px 0 0; color: rgba(239, 246, 255, 0.72); font-size: 12px; }

.nav-links {
  display: grid;
  gap: 8px;
}
.nav-links a {
  color: rgba(255, 255, 255, 0.78);
  text-decoration: none;
  padding: 11px 12px;
  border-radius: 12px;
  transition: 0.2s ease;
  font-weight: 600;
}
.nav-links a:hover,
.nav-links a.router-link-active {
  background: rgba(255, 255, 255, 0.13);
  color: #fff;
}

@media (max-width: 960px) {
  .sidebar {
    width: 100%;
    min-height: auto;
    position: static;
  }
  .nav-links { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
</style>
