import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 300000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("eiq.auth.token");
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 封装后端接口调用，供页面流程复用。
export const registerApi = (payload = {}) => api.post("/auth/register", payload);
// 封装后端接口调用，供页面流程复用。
export const loginApi = (payload = {}) => api.post("/auth/login", payload);
// 封装后端接口调用，供页面流程复用。
export const getMeApi = () => api.get("/auth/me");

// 封装后端接口调用，供页面流程复用。
export const uploadFilesApi = (formData) =>
  api.post("/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

// 封装后端接口调用，供页面流程复用。
export const analyzeApi = (payload = {}) => api.post("/analyze", payload);
// 封装后端接口调用，供页面流程复用。
export const createAnalysisTaskApi = (payload = {}) => api.post("/analyze", payload);
// 封装后端接口调用，供页面流程复用。
export const getAnalysisTaskApi = (taskId) => api.get(`/analyze/tasks/${taskId}`);

// 封装后端接口调用，供页面流程复用。
export const getAnalysisById = (id) => api.get(`/analysis/${id}`);

// 封装后端接口调用，供页面流程复用。
export const chatApi = (data) => api.post("/chat", data);
// 封装后端接口调用，供页面流程复用。
export const getChatSessionsApi = () => api.get("/chat/sessions");
// 封装后端接口调用，供页面流程复用。
export const getChatSessionDetailApi = (sessionId) => api.get(`/chat/sessions/${sessionId}`);

// 封装后端接口调用，供页面流程复用。
export const getHistoryApi = () => api.get("/history");
// 封装后端接口调用，供页面流程复用。
export const deleteHistoryApi = (analysisId) => api.delete(`/history/${analysisId}`);

export default api;
