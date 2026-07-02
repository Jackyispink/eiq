import { createRouter, createWebHistory } from "vue-router";

const routes = [
  { path: "/login", component: () => import("../views/Login.vue"), meta: { public: true } },
  { path: "/", component: () => import("../views/Home.vue") },
  { path: "/upload", component: () => import("../views/Upload.vue") },
  { path: "/analysis", component: () => import("../views/Analysis.vue") },
  { path: "/question-stats", component: () => import("../views/QuestionStats.vue") },
  { path: "/report", component: () => import("../views/Report.vue") },
  { path: "/chat", component: () => import("../views/Chat.vue") },
  { path: "/history", component: () => import("../views/History.vue") },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem("eiq.auth.token");
  if (to.meta.public) {
    if (to.path === "/login" && token) {
      next("/");
      return;
    }
    next();
    return;
  }
  if (!token) {
    next("/login");
    return;
  }
  next();
});

export default router;
