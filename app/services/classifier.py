from typing import Optional
import re
from collections import Counter
import logging

from app.schemas.models import PageMetadata, TopicClassification

logger = logging.getLogger(__name__)

# keyword dictionaries for topic classification
TOPIC_KEYWORDS = {
    "Technology": [
        "software", "technology", "computer", "digital", "app", "programming", "code",
        "developer", "tech", "gadget", "smartphone", "ai", "machine learning", "data",
        "cloud", "internet", "cyber", "hardware", "electronics"
    ],
    "Politics": [
        "politics", "government", "election", "president", "congress", "senate", "democrat",
        "republican", "policy", "vote", "political", "legislation", "law", "candidate",
        "campaign", "party", "administration"
    ],
    "Business": [
        "business", "company", "market", "stock", "finance", "economy", "investment",
        "startup", "entrepreneur", "revenue", "profit", "trade", "commerce", "retail",
        "sales", "corporate", "industry"
    ],
    "Sports": [
        "sports", "game", "team", "player", "score", "championship", "football",
        "basketball", "baseball", "soccer", "athlete", "coach", "tournament", "league"
    ],
    "Entertainment": [
        "entertainment", "movie", "film", "music", "celebrity", "actor", "actress",
        "show", "tv", "television", "streaming", "netflix", "concert", "album", "artist"
    ],
    "Health": [
        "health", "medical", "doctor", "hospital", "disease", "treatment", "medicine",
        "patient", "wellness", "fitness", "nutrition", "diet", "exercise", "healthcare"
    ],
    "Science": [
        "science", "research", "study", "scientist", "discovery", "experiment", "biology",
        "physics", "chemistry", "space", "nasa", "climate", "environment", "nature"
    ],
    "Lifestyle": [
        "lifestyle", "fashion", "travel", "food", "recipe", "cooking", "home", "garden",
        "decor", "beauty", "style", "trend", "vacation", "destination"
    ],
    "E-commerce": [
        "buy", "price", "product", "shop", "cart", "order", "shipping", "customer",
        "review", "rating", "deal", "discount", "amazon", "store", "purchase", "checkout"
    ],
    "Outdoor": [
        "outdoor", "camping", "hiking", "nature", "adventure", "trail", "backpack",
        "gear", "wilderness", "park", "mountain", "forest", "fishing", "climbing"
    ],
}


class ClassifierService:
    def __init__(self):
        self.topic_patterns = {}
        for topic, keywords in TOPIC_KEYWORDS.items():
            pattern = re.compile(r'\b(' + '|'.join(re.escape(k) for k in keywords) + r')\b', re.IGNORECASE)
            self.topic_patterns[topic] = pattern
    
    def classify(self, metadata: PageMetadata, html: Optional[str] = None) -> TopicClassification:
        # combine text from different fields with weighting
        text_parts = []
        if metadata.title:
            text_parts.extend([metadata.title] * 3)  # title weighted higher
        if metadata.description:
            text_parts.extend([metadata.description] * 2)
        if metadata.keywords:
            text_parts.extend(metadata.keywords)
        for h1 in metadata.h1_tags:
            text_parts.extend([h1] * 2)
        for h2 in metadata.h2_tags:
            text_parts.append(h2)
        
        combined_text = " ".join(text_parts)
        
        # count keyword matches per topic
        topic_scores = Counter()
        total_matches = 0
        for topic, pattern in self.topic_patterns.items():
            matches = pattern.findall(combined_text)
            if matches:
                topic_scores[topic] = len(matches)
                total_matches += len(matches)
        
        if not topic_scores:
            return TopicClassification(primary_topic=None, topics=[], confidence=0.0)
        
        top_topics = topic_scores.most_common(5)
        primary_topic = top_topics[0][0]
        primary_score = top_topics[0][1]
        
        # calculate confidence score
        confidence = min(primary_score / max(total_matches, 1) + 0.3, 1.0)
        threshold = max(1, primary_score * 0.3)
        relevant_topics = [t for t, s in top_topics if s >= threshold]
        
        logger.info(f"Classified as: {primary_topic} (confidence: {confidence:.2f})")
        return TopicClassification(
            primary_topic=primary_topic,
            topics=relevant_topics,
            confidence=round(confidence, 2)
        )


_classifier_instance: Optional[ClassifierService] = None

def get_classifier() -> ClassifierService:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = ClassifierService()
    return _classifier_instance
