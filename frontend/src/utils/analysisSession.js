const ANALYSIS_RESULT_KEY = "eiq.analysis.result";
const ANALYSIS_BATCH_KEY = "eiq.analysis.batchIds";

// 保存分析会话数据，保持分析结果在页面间可复用。
export function saveAnalysisResult(result) {
  localStorage.setItem(ANALYSIS_RESULT_KEY, JSON.stringify(result));
  if (result?.batch_ids) {
    localStorage.setItem(ANALYSIS_BATCH_KEY, JSON.stringify(result.batch_ids));
  }
}

// 读取分析会话数据，保持分析结果在页面间可复用。
export function getAnalysisResult() {
  const raw = localStorage.getItem(ANALYSIS_RESULT_KEY);
  return raw ? JSON.parse(raw) : null;
}

// 保存分析会话数据，保持分析结果在页面间可复用。
export function saveBatchIds(batchIds) {
  localStorage.setItem(ANALYSIS_BATCH_KEY, JSON.stringify(batchIds));
}

// 读取分析会话数据，保持分析结果在页面间可复用。
export function getBatchIds() {
  const raw = localStorage.getItem(ANALYSIS_BATCH_KEY);
  return raw ? JSON.parse(raw) : [];
}
