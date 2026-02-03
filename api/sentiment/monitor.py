"""Sentiment Monitor - Search Twitter for motorsport buzz via bird CLI.

Tracks engagement metrics and detects spikes in conversation.
"""
import subprocess
import json
import time
from datetime import datetime
from typing import Optional, Dict, List, Any

# In-memory cache for tweet data
_tweet_cache: Dict[str, tuple] = {}
CACHE_TTL = 300  # 5 minutes

# Series search terms
SERIES_SEARCHES = {
    "f1": ["F1", "#F1", "Formula 1"],
    "wrc": ["WRC", "#WRC", "World Rally"],
    "nascar": ["NASCAR", "#NASCAR"],
    "indycar": ["IndyCar", "#IndyCar", "Indy500"],
    "imsa": ["IMSA", "#IMSA", "#Daytona24", "WeatherTech"],
    "wec": ["WEC", "#WEC", "#LeMans24", "Hypercar"],
    "motogp": ["MotoGP", "#MotoGP"],
}

# Baseline engagement thresholds (tweets above these are "hot")
BASELINE_ENGAGEMENT = {
    "likes": 10,
    "retweets": 5,
    "replies": 3,
}


def search_twitter(query: str, count: int = 20) -> Optional[List[Dict]]:
    """
    Search Twitter using bird CLI.
    
    Args:
        query: Search query (e.g., "IMSA" or "#Daytona24")
        count: Number of tweets to fetch
    
    Returns:
        List of tweet dicts or None on error
    """
    cache_key = f"{query}:{count}"
    now = time.time()
    
    # Check cache
    if cache_key in _tweet_cache:
        data, timestamp = _tweet_cache[cache_key]
        if now - timestamp < CACHE_TTL:
            return data
    
    try:
        result = subprocess.run(
            ["bird", "search", query, "-n", str(count), "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            # Check if it's just a warning (bird still outputs JSON)
            pass
        
        # Parse JSON output (skip warning lines)
        output = result.stdout
        json_start = output.find('[')
        if json_start == -1:
            return None
        
        tweets = json.loads(output[json_start:])
        _tweet_cache[cache_key] = (tweets, now)
        return tweets
        
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[Sentiment] Error searching '{query}': {e}")
        return None


def calculate_engagement(tweet: Dict) -> int:
    """Calculate total engagement score for a tweet."""
    return (
        tweet.get("likeCount", 0) * 1 +
        tweet.get("retweetCount", 0) * 2 +
        tweet.get("replyCount", 0) * 3
    )


def is_spike(tweet: Dict) -> bool:
    """Determine if a tweet represents an engagement spike."""
    likes = tweet.get("likeCount", 0)
    retweets = tweet.get("retweetCount", 0)
    replies = tweet.get("replyCount", 0)
    
    return (
        likes >= BASELINE_ENGAGEMENT["likes"] or
        retweets >= BASELINE_ENGAGEMENT["retweets"] or
        replies >= BASELINE_ENGAGEMENT["replies"]
    )


def analyze_sentiment(text: str) -> str:
    """
    Simple keyword-based sentiment analysis.
    Returns: 'positive', 'negative', or 'neutral'
    """
    text_lower = text.lower()
    
    positive_words = [
        "amazing", "incredible", "beautiful", "win", "winner", "champion",
        "perfect", "brilliant", "great", "awesome", "congratulations",
        "congrats", "love", "best", "dominant", "masterclass", "🔥", "🏆",
        "thrilling", "exciting", "epic"
    ]
    
    negative_words = [
        "crash", "disaster", "terrible", "awful", "worst", "dnf", "failure",
        "disappointed", "robbed", "unfair", "controversy", "penalty",
        "joke", "rigged", "boring", "embarrassing", "shameful", "💔", "😡"
    ]
    
    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)
    
    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"


def get_hot_tweets(series: Optional[str] = None, count: int = 20) -> List[Dict]:
    """
    Get hot tweets for specified series or all series.
    
    Args:
        series: Optional series filter (e.g., 'f1', 'imsa')
        count: Max tweets to return per search term
    
    Returns:
        List of hot tweets with engagement and sentiment data
    """
    searches = SERIES_SEARCHES.get(series, []) if series else []
    
    # If no series specified, search all
    if not searches:
        searches = []
        for s, terms in SERIES_SEARCHES.items():
            searches.extend(terms[:1])  # Just the main term per series
    
    all_tweets = []
    seen_ids = set()
    
    for query in searches:
        tweets = search_twitter(query, count)
        if not tweets:
            continue
        
        for tweet in tweets:
            tweet_id = tweet.get("id")
            if tweet_id in seen_ids:
                continue
            seen_ids.add(tweet_id)
            
            engagement = calculate_engagement(tweet)
            sentiment = analyze_sentiment(tweet.get("text", ""))
            
            all_tweets.append({
                "id": tweet_id,
                "text": tweet.get("text", ""),
                "author": tweet.get("author", {}).get("username", "unknown"),
                "authorName": tweet.get("author", {}).get("name", "Unknown"),
                "createdAt": tweet.get("createdAt", ""),
                "engagement": engagement,
                "likes": tweet.get("likeCount", 0),
                "retweets": tweet.get("retweetCount", 0),
                "replies": tweet.get("replyCount", 0),
                "sentiment": sentiment,
                "isSpike": is_spike(tweet),
                "media": tweet.get("media", []),
            })
    
    # Sort by engagement
    all_tweets.sort(key=lambda t: t["engagement"], reverse=True)
    
    return all_tweets


def get_sentiment_summary(tweets: List[Dict]) -> Dict:
    """Generate sentiment summary from tweets."""
    if not tweets:
        return {
            "total": 0,
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "avgEngagement": 0,
            "spikes": 0,
        }
    
    positive = sum(1 for t in tweets if t["sentiment"] == "positive")
    negative = sum(1 for t in tweets if t["sentiment"] == "negative")
    neutral = sum(1 for t in tweets if t["sentiment"] == "neutral")
    spikes = sum(1 for t in tweets if t["isSpike"])
    avg_engagement = sum(t["engagement"] for t in tweets) / len(tweets)
    
    return {
        "total": len(tweets),
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "avgEngagement": round(avg_engagement, 1),
        "spikes": spikes,
        "sentimentScore": round((positive - negative) / len(tweets) * 100, 1) if tweets else 0,
    }
