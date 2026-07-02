
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from .embedding import TextEmbedder


# 封装主题匹配逻辑，用于语义归类和相似度分析。
class TopicMatcher:

    # 初始化，服务于主观题语义分析流程。
    def __init__(self, similarity_threshold=0.65):

        print("🚀 初始化 TopicMatcher")

        self.embedder = TextEmbedder()
        self.similarity_threshold = similarity_threshold

        self.topic_vectors = []
        self.topic_texts = []

    # 处理，服务于主观题语义分析流程。
    def match_batch(self, texts):

        if not texts:
            return []

        embeddings = self.embedder.encode(texts)

        results = []

        for text, vec in zip(texts, embeddings):

            if not self.topic_vectors:

                self.topic_vectors.append(vec)
                self.topic_texts.append(text)

                results.append({
                    "text": text,
                    "topic_id": 0
                })
                continue

            sims = cosine_similarity([vec], self.topic_vectors)[0]

            best_index = np.argmax(sims)
            best_score = sims[best_index]

            if best_score < self.similarity_threshold:

                topic_id = len(self.topic_vectors)
                self.topic_vectors.append(vec)
                self.topic_texts.append(text)

            else:
                topic_id = best_index

            results.append({
                "text": text,
                "topic_id": topic_id
            })

        return results