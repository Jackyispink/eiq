import os
from pathlib import Path


EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "model"))

GPU_MODE = os.getenv("GPU_MODE", "AUTO").upper()

PERFORMANCE_MODE = os.getenv("PERFORMANCE_MODE", "fast").lower()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

USE_LOCAL_LLM = os.getenv("USE_LOCAL_LLM", "1").strip() in {"1", "true", "True", "YES", "yes"}
LOCAL_LLM_PATH = os.getenv("LOCAL_LLM_PATH", str(BASE_DIR / "model" / "model2"))
LOCAL_LLM_MAX_NEW_TOKENS = int(os.getenv("LOCAL_LLM_MAX_NEW_TOKENS", "512"))
DEFAULT_LLM_SOURCE = os.getenv("DEFAULT_LLM_SOURCE", "api").strip().lower()
