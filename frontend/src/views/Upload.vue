<template>
  <section class="page-card upload-page">
    <div class="heading-row">
      <div>
        <h2 class="page-title">上传问卷文件</h2>
        <p class="page-subtitle">
          支持 `.csv`、`.xlsx`、`.xls`。上传成功后会记录批次号，并可直接跳到分析页生成动态报告。
        </p>
      </div>
      <router-link class="link-button" to="/analysis">前往分析页</router-link>
    </div>

    <label class="upload-dropzone">
      <input
        type="file"
        multiple
        accept=".csv,.xlsx,.xls"
        @change="handleFileSelect"
      />
      <span>点击或拖入文件到这里</span>
      <small>当前已选择 {{ selectedFiles.length }} 个文件</small>
    </label>

    <div v-if="selectedFiles.length" class="file-list">
      <div v-for="file in selectedFiles" :key="file.name" class="file-item">
        <strong>{{ file.name }}</strong>
        <span>{{ formatFileSize(file.size) }}</span>
      </div>
    </div>

    <div class="action-row">
      <button class="primary-btn" :disabled="!selectedFiles.length || uploading" @click="uploadFiles">
        {{ uploading ? "上传中..." : "开始上传" }}
      </button>
      <p v-if="uploadStatus" class="status-text">{{ uploadStatus }}</p>
    </div>

    <div v-if="latestBatchId" class="batch-note">
      最新批次号：<strong :title="latestBatchId">{{ formatBatchId(latestBatchId) }}</strong>
      <span v-if="latestAnalysisId">，已完成快速分析缓存</span>
    </div>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { uploadFilesApi } from "../services/api";
import { saveBatchIds } from "../utils/analysisSession";

const router = useRouter();
const selectedFiles = ref([]);
const latestBatchId = ref("");
const latestAnalysisId = ref(null);
const uploadStatus = ref("");
const uploading = ref(false);

// 切换当前会话或记录，驱动当前页面的数据流和交互流程。
function handleFileSelect(event) {
  selectedFiles.value = Array.from(event.target.files || []);
}

// 处理页面交互逻辑，驱动当前页面的数据流和交互流程。
async function uploadFiles() {
  if (!selectedFiles.value.length) {
    return;
  }

  const formData = new FormData();
  selectedFiles.value.forEach((file) => formData.append("files", file));

  uploading.value = true;
  uploadStatus.value = "";

  try {
    const { data } = await uploadFilesApi(formData);
    latestBatchId.value = data.batch_id;
    latestAnalysisId.value = data.analysis_id || null;
    saveBatchIds([data.batch_id]);
    uploadStatus.value = data.cache_status === "building"
      ? `${data.message || "上传成功"}，后台正在生成快速分析缓存`
      : (data.message || "上传成功");
    selectedFiles.value = [];
    setTimeout(() => router.push("/analysis"), 600);
  } catch (error) {
    uploadStatus.value =
      error?.response?.data?.error || "上传失败，请确认后端服务已启动";
  } finally {
    uploading.value = false;
  }
}

// 格式化页面展示文本，驱动当前页面的数据流和交互流程。
function formatFileSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

// 格式化页面展示文本，驱动当前页面的数据流和交互流程。
function formatBatchId(batchId) {
  const text = String(batchId || "");
  if (text.length <= 6) {
    return text;
  }
  return text.slice(-6);
}
</script>

<style scoped>
.upload-page {
  display: grid;
  gap: 22px;
}

.heading-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.link-button {
  padding: 11px 16px;
  border-radius: 14px;
  border: 1px solid var(--line);
  text-decoration: none;
  color: var(--text-main);
  background: #fff;
}

.upload-dropzone {
  min-height: 220px;
  border: 2px dashed #b7c7d9;
  border-radius: 28px;
  display: grid;
  place-items: center;
  text-align: center;
  background:
    linear-gradient(135deg, rgba(15, 118, 110, 0.05), rgba(37, 99, 235, 0.04)),
    #fff;
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.upload-dropzone input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.upload-dropzone span {
  display: block;
  font-size: 22px;
  font-weight: 700;
}

.upload-dropzone small {
  display: block;
  margin-top: 10px;
  color: var(--text-soft);
}

.file-list {
  display: grid;
  gap: 10px;
}

.file-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid var(--line);
}

.action-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.primary-btn {
  padding: 12px 18px;
  border: none;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--brand), #2563eb);
  color: white;
  font-weight: 700;
  cursor: pointer;
}

.primary-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.status-text,
.batch-note {
  color: var(--text-soft);
}

@media (max-width: 960px) {
  .heading-row,
  .action-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
