from __future__ import annotations

import os
from typing import Any

from sentence_transformers import SentenceTransformer

from backend.config import EMBEDDING_MODEL, GPU_MODE, MODEL_PATH


# 识别，服务于主观题语义分析流程。
def _detect_device() -> str:
    if GPU_MODE == "FORCE_CPU":
        return "cpu"
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


# 处理主观题语义分析中的模型、关键词、主题或情感流程。
class NLPModelManager:
    _embedding_model: SentenceTransformer | None = None
    _runtime: dict[str, Any] = {"device": "cpu", "gpu_available": False}

    # 处理主观题语义分析中的模型、关键词、主题或情感流程。
    @classmethod
    def get_embedding_model(cls) -> SentenceTransformer:
        if cls._embedding_model is None:
            device = _detect_device()
            cls._embedding_model = SentenceTransformer(
                EMBEDDING_MODEL,
                cache_folder=MODEL_PATH,
                device=device,
            )
            cls._runtime = {
                "device": device,
                "gpu_available": device == "cuda",
                "model": EMBEDDING_MODEL,
                "cache_folder": os.path.abspath(MODEL_PATH),
            }
        return cls._embedding_model

    # 处理主观题语义分析中的模型、关键词、主题或情感流程。
    @classmethod
    def get_runtime_info(cls) -> dict[str, Any]:
        if cls._embedding_model is None:
            device = _detect_device()
            return {
                "device": device,
                "gpu_available": device == "cuda",
                "model": EMBEDDING_MODEL,
                "cache_folder": os.path.abspath(MODEL_PATH),
                "loaded": False,
            }
        return dict(cls._runtime)
