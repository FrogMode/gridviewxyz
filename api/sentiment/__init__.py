"""GridView Sentiment Analysis Module.

Provides sentiment-driven article recommendations by:
1. Monitoring Twitter/X for motorsport buzz
2. Extracting trending topics
3. Matching topics to news articles
"""
from .monitor import get_hot_tweets, get_sentiment_summary
from .topics import extract_topics
from .articles import match_articles_to_topics

__all__ = [
    "get_hot_tweets",
    "get_sentiment_summary", 
    "extract_topics",
    "match_articles_to_topics",
]
