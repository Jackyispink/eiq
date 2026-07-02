<template>
  <div v-if="isAuthPage">
    <router-view />
  </div>
  <div v-else class="app-shell">
    <Sidebar />
    <main class="app-main">
      <header class="app-header">
        <div>
          <p class="app-kicker">EIQ</p>
          <h1>问卷分析工作台</h1>
        </div>
        <div class="user-box">
          <span class="user-name">{{ currentUser?.username || "访客" }}</span>
          <button class="logout-btn" @click="logout">退出</button>
        </div>
      </header>

      <section class="app-content">
        <router-view />
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import Sidebar from "./components/Sidebar.vue";

const route = useRoute();
const router = useRouter();

const isAuthPage = computed(() => route.path === "/login");
const currentUser = computed(() => {
  try {
    return JSON.parse(localStorage.getItem("eiq.auth.user") || "null");
  } catch {
    return null;
  }
});

function logout() {
  localStorage.removeItem("eiq.auth.token");
  localStorage.removeItem("eiq.auth.user");
  router.push("/login");
}
</script>

<style>
:root {
  color-scheme: light;
  --bg-main: #ecf2f4;
  --bg-panel: #fffdfa;
  --line: #d7e2e6;
  --text-main: #132338;
  --text-soft: #5f6c80;
  --brand: #0f766e;
  --brand-2: #0ea5e9;
  --shadow: 0 20px 70px rgba(15, 23, 42, 0.12);
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Manrope", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: var(--text-main);
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.15), transparent 32%),
    radial-gradient(circle at bottom right, rgba(14, 165, 233, 0.12), transparent 30%),
    var(--bg-main);
}
#app { min-height: 100vh; }

.app-shell { min-height: 100vh; display: flex; }
.app-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.app-header {
  padding: 24px 32px 10px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.app-header h1 { margin: 0; font-size: 34px; line-height: 1.2; }
.app-kicker {
  margin: 0 0 8px;
  color: var(--brand);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 12px;
  font-weight: 800;
}
.user-box {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 8px 10px;
}
.user-name { font-weight: 700; color: #334155; }
.logout-btn {
  border: none;
  border-radius: 10px;
  padding: 8px 10px;
  background: #f1f5f9;
  cursor: pointer;
  font-weight: 700;
}
.app-content { padding: 0 32px 32px; }

.page-card {
  background: rgba(255, 253, 248, 0.9);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  border-radius: 24px;
  padding: 24px;
}
.page-title { margin: 0 0 10px; font-size: 28px; font-weight: 800; }
.page-subtitle { margin: 0; color: var(--text-soft); line-height: 1.7; }

@media (max-width: 960px) {
  .app-shell { flex-direction: column; }
  .app-header { padding: 16px 16px 8px; flex-direction: column; }
  .app-content { padding: 0 16px 16px; }
}
</style>
