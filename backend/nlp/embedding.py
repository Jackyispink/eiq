from __future__ import annotations

from .model_manager import NLPModelManager


# 封装文本向量化能力，用于语义相似度计算。
class TextEmbedder:
    # 初始化，服务于主观题语义分析流程。
    def __init__(self):
        self.model = NLPModelManager.get_embedding_model()

    # 处理，服务于主观题语义分析流程。
    def encode(self, texts, batch_size: int = 128):
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(
            texts,
            show_progress_bar=False,
            batch_size=max(8, int(batch_size)),
            normalize_embeddings=True,
        )
