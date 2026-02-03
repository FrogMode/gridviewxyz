"""GridView Sentiment Analysis Module v2.

Enhanced sentiment-driven recommendations with:
1. Multi-dimensional sentiment analysis (excitement, controversy, etc.)
2. Improved entity detection (drivers, teams, events)
3. Race weekend spike detection
4. Controversy alerts
5. Better Twitter/X integration via bird CLI

v2 Modules:
- analyzer: Multi-dimensional sentiment scoring
- monitor_v2: Enhanced Twitter search with filtering
- topics_v2: Improved entity extraction
"""
# v2 modules (enhanced)
from .analyzer import analyze_sentiment, SentimentScore, detect_controversy_spike
from .monitor_v2 import get_hot_tweets_v2, get_sentiment_summary_v2, detect_race_weekend_spike
from .topics_v2 import extract_topics_v2, find_entities

# Backward compatibility (v1 APIs still work)
from .monitor import get_hot_tweets, get_sentiment_summary
from .topics import extract_topics
from .articles import match_articles_to_topics

__all__ = [
    # v2 (preferred)
    "analyze_sentiment",
    "SentimentScore",
    "get_hot_tweets_v2",
    "get_sentiment_summary_v2",
    "extract_topics_v2",
    "find_entities",
    "detect_controversy_spike",
    "detect_race_weekend_spike",
    # v1 (backward compatible)
    "get_hot_tweets",
    "get_sentiment_summary",
    "extract_topics",
    "match_articles_to_topics",
]
