
from keybert import KeyBERT
from .model_manager import NLPModelManager


# 封装关键词提取能力，供主观题分析流程复用。
class KeywordExtractor:

    _model = None

    # 初始化，服务于主观题语义分析流程。
    def __init__(self):

        if KeywordExtractor._model is None:

            print("🚀 初始化 KeyBERT")

            embedding_model = NLPModelManager.get_embedding_model()

            KeywordExtractor._model = KeyBERT(model=embedding_model)

        self.model = KeywordExtractor._model

    # 提取，服务于主观题语义分析流程。
    def extract_keywords(self, text, top_n=5):

        if not text or len(text.strip()) < 5:
            return []

        keywords = self.model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 2),
            stop_words=None,
            top_n=top_n
        )

        return [kw[0] for kw in keywords]