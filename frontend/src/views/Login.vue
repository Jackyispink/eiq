<template>
  <section class="login-page">
    <article class="login-card">
      <p class="kicker">EIQ Survey Intelligence</p>
      <h1>欢迎登录问卷分析平台</h1>
      <p class="desc">登录后可保存你的分析历史与配置偏好。</p>

      <div class="tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <label>
        用户名
        <input v-model.trim="username" type="text" placeholder="请输入用户名" />
      </label>
      <label>
        密码
        <input v-model="password" type="password" placeholder="请输入密码" />
      </label>

      <button class="submit-btn" :disabled="loading" @click="submit">
        {{ loading ? "处理中..." : mode === "login" ? "立即登录" : "注册并登录" }}
      </button>

      <p v-if="message" class="msg">{{ message }}</p>
    </article>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { loginApi, registerApi } from "../services/api";

const router = useRouter();
const mode = ref("login");
const username = ref("");
const password = ref("");
const loading = ref(false);
const message = ref("");

// 提交表单并处理响应，驱动当前页面的数据流和交互流程。
async function submit() {
  if (!username.value || !password.value) {
    message.value = "请输入用户名和密码";
    return;
  }
  loading.value = true;
  message.value = "";
  try {
    const apiCall = mode.value === "login" ? loginApi : registerApi;
    const { data } = await apiCall({
      username: username.value,
      password: password.value,
    });
    if (data?.error) {
      message.value = data.error;
      return;
    }
    if (!data?.token) {
      message.value = "登录失败，请重试";
      return;
    }
    localStorage.setItem("eiq.auth.token", data.token);
    if (data?.user) {
      localStorage.setItem("eiq.auth.user", JSON.stringify(data.user));
    }
    router.push("/");
  } catch (error) {
    message.value = error?.response?.data?.error || error?.message || "请求失败";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 10% 10%, rgba(8, 145, 178, 0.25), transparent 45%),
    radial-gradient(circle at 90% 90%, rgba(217, 119, 6, 0.2), transparent 42%),
    #f4f7f9;
}
.login-card {
  width: min(92vw, 440px);
  background: #ffffff;
  border: 1px solid #dbe7ee;
  border-radius: 24px;
  padding: 28px;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.14);
  display: grid;
  gap: 14px;
}
.kicker {
  margin: 0;
  color: #0f766e;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 12px;
  font-weight: 800;
}
h1 { margin: 0; font-size: 26px; }
.desc { margin: 0; color: #64748b; }
.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  background: #f1f5f9;
  border-radius: 12px;
  padding: 4px;
}
.tabs button {
  border: none;
  border-radius: 10px;
  padding: 9px 10px;
  cursor: pointer;
  background: transparent;
  font-weight: 700;
  color: #475569;
}
.tabs button.active {
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08);
}
label {
  display: grid;
  gap: 7px;
  font-size: 14px;
  color: #334155;
}
input {
  border: 1px solid #d5e0e8;
  border-radius: 12px;
  padding: 12px 13px;
  font: inherit;
  background: #fff;
}
.submit-btn {
  border: none;
  border-radius: 14px;
  padding: 12px 14px;
  color: #fff;
  font-weight: 800;
  cursor: pointer;
  background: linear-gradient(135deg, #0ea5e9, #0f766e);
}
.submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.msg { margin: 0; color: #dc2626; }
</style>
