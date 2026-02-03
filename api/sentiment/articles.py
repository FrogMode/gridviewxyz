"""Article Matcher - Match news articles to trending topics.

Scores articles against hot topics using keyword matching and recency.
"""
import urllib.request
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import time

from .topics import get_topic_keywords

# Cache for news articles
_article_cache: Dict[str, tuple] = {}
CACHE_TTL = 300  # 5 minutes


def fetch_news(category: str = "all", limit: int = 20) -> Optional[List[Dict]]:
    """
    Fetch news from the GridView news API.
    
    Args:
        category: News category (all, f1, wrc, nascar, etc.)
        limit: Max articles to fetch
    
    Returns:
        List of article dicts or None on error
    """
    cache_key = f"{category}:{limit}"
    now = time.time()
    
    # Check cache
    if cache_key in _article_cache:
        data, timestamp = _article_cache[cache_key]
        if now - timestamp < CACHE_TTL:
            return data
    
    try:
        # Use localhost in dev, relative path in production
        base_url = "http://localhost:3000"  # Vercel dev server
        url = f"{base_url}/api/news?category={category}&limit={limit}"
        
        req = urllib.request.Request(url, headers={
            "User-Agent": "GridView-Sentiment/1.0"
        })
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            articles = data.get("articles", [])
            _article_cache[cache_key] = (articles, now)
            return articles
            
    except Exception as e:
        print(f"[Articles] Error fetching news: {e}")
        # Try to return stale cache
        if cache_key in _article_cache:
            return _article_cache[cache_key][0]
        return None


def score_article(article: Dict, topic: Dict) -> float:
    """
    Score an article against a topic.
    
    Higher score = better match.
    Factors: keyword matches, title matches (weighted more), recency
    """
    keywords = get_topic_keywords(topic["topic"])
    
    title = article.get("title", "").lower()
    description = article.get("description", "").lower()
    categories = [c.lower() for c in article.get("categories", [])]
    
    score = 0.0
    
    # Title matches (high weight)
    for keyword in keywords:
        if keyword in title:
            score += 10.0
    
    # Description matches
    for keyword in keywords:
        if keyword in description:
            score += 3.0
    
    # Category matches
    for keyword in keywords:
        for cat in categories:
            if keyword in cat:
                score += 5.0
    
    # Recency bonus (articles from today get boost)
    pub_date = article.get("published", "")
    if pub_date:
        try:
            # Parse various date formats
            for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"]:
                try:
                    dt = datetime.strptime(pub_date.replace("GMT", "+0000"), fmt)
                    age_hours = (datetime.now(dt.tzinfo) - dt).total_seconds() / 3600
                    if age_hours < 6:
                        score *= 1.5
                    elif age_hours < 24:
                        score *= 1.2
                    break
                except ValueError:
                    continue
        except Exception:
            pass
    
    # Topic engagement boost (hot topics boost article score)
    if topic.get("count", 0) > 5:
        score *= 1.2
    
    return score


def match_articles_to_topics(
    topics: List[Dict],
    max_articles_per_topic: int = 3
) -> List[Dict]:
    """
    Find best matching articles for each topic.
    
    Args:
        topics: List of trending topics from extract_topics()
        max_articles_per_topic: Max articles to return per topic
    
    Returns:
        Topics enriched with matched articles
    """
    # Fetch all news (we'll match across categories)
    all_articles = fetch_news("all", limit=50)
    
    if not all_articles:
        return topics
    
    enriched_topics = []
    
    for topic in topics:
        # Score all articles against this topic
        scored = []
        for article in all_articles:
            score = score_article(article, topic)
            if score > 0:
                scored.append((article, score))
        
        # Sort by score and take top matches
        scored.sort(key=lambda x: x[1], reverse=True)
        matched = [
            {
                "id": article.get("id", ""),
                "title": article.get("title", ""),
                "link": article.get("link", ""),
                "image": article.get("image"),
                "published": article.get("published", ""),
                "score": round(score, 1),
            }
            for article, score in scored[:max_articles_per_topic]
        ]
        
        topic_copy = topic.copy()
        topic_copy["articles"] = matched
        topic_copy["hasArticles"] = len(matched) > 0
        enriched_topics.append(topic_copy)
    
    return enriched_topics


def get_top_articles_for_series(series: str, limit: int = 5) -> List[Dict]:
    """Get top trending articles for a specific series."""
    # Map series to news category
    series_to_category = {
        "f1": "f1",
        "wrc": "wrc",
        "nascar": "nascar",
        "indycar": "indycar",
        "imsa": "wec",  # IMSA uses WEC category
        "wec": "wec",
        "motogp": "motogp",
    }
    
    category = series_to_category.get(series, "all")
    articles = fetch_news(category, limit=limit)
    
    if not articles:
        return []
    
    return [
        {
            "id": a.get("id", ""),
            "title": a.get("title", ""),
            "link": a.get("link", ""),
            "image": a.get("image"),
            "description": a.get("description", ""),
            "published": a.get("published", ""),
        }
        for a in articles
    ]
