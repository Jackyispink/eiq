<template>
  <div class="layout">
    <Sidebar />

    <div class="main">
      <header class="header">
        EIQ 智能问卷分析系统
      </header>

      <div class="content">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script>
import Sidebar from "./components/Sidebar.vue"

export default {
  components: { Sidebar }
}
</script>

<style>
.layout {
  display: flex;
  height: 100vh;
  background: #f5f7fb;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.header {
  background: white;
  padding: 20px 30px;
  border-bottom: 1px solid #e5e7eb;
  font-size: 20px;
  font-weight: 600;
}

.content {
  flex: 1;
  padding: 40px;
  overflow-y: auto;
}
</style>