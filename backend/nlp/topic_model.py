
from bertopic import BERTopic
from .model_manager import NLPModelManager


# 封装主题抽取能力，生成主观题主题摘要。
class TopicExtractor:

    # 初始化，服务于主观题语义分析流程。
    def __init__(self):

        embedding_model = NLPModelManager.get_embedding_model()

        self.model = BERTopic(
            embedding_model=embedding_model,
            language="multilingual",
            calculate_probabilities=False,
            verbose=False
        )

    # 提取，服务于主观题语义分析流程。
    def extract_topics(self, texts):

        if not texts or len(texts) < 5:
            return []

        texts = texts[:300]

        topics, _ = self.model.fit_transform(texts)

        topic_info = self.model.get_topic_info()

        results = []

        for _, row in topic_info.iterrows():

            topic_id = row["Topic"]

            if topic_id == -1:
                continue

            words = self.model.get_topic(topic_id)

            keywords = [w[0] for w in words[:5]]

            results.append({
                "topic": f"主题{topic_id}",
                "keywords": keywords,
                "count": int(row["Count"])
            })

        return results