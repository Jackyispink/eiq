<template>
  <div class="sidebar">
    <h2 class="logo">Survey AI</h2>

    <router-link to="/">首页</router-link>
    <router-link to="/upload">数据上传</router-link>
    <router-link to="/analysis">数据分析</router-link>
    <router-link to="/report">分析报告</router-link>
    <router-link to="/chat">智能问答</router-link>
    <router-link to="/history">历史记录</router-link>
  </div>
</template>

<style>
.sidebar {
  width: 240px;
  background: #1e293b;
  color: white;
  padding: 30px 20px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.logo {
  margin-bottom: 30px;
}

.sidebar a {
  color: #cbd5e1;
  text-decoration: none;
  padding: 10px 15px;
  border-radius: 8px;
  transition: 0.3s;
}

.sidebar a:hover {
  background: #334155;
  color: white;
}
</style>