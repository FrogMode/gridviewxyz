"""Enhanced Sentiment Monitor v2 - Better Twitter integration.

Improvements over v1:
- Better search queries (combined hashtags, filtered results)
- Engagement-weighted sentiment
- Race weekend spike detection
- Verified account boosting
- Series-specific searches with proper racing hashtags
"""
import subprocess
import json
import time
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple

from .analyzer import analyze_sentiment, score_to_dict, get_sentiment_label, detect_controversy_spike

# In-memory cache
_tweet_cache: Dict[str, Tuple[List, float]] = {}
CACHE_TTL = 180  # 3 minutes for fresher data

# Enhanced series search configurations
# Each series has primary hashtags, secondary terms, and accounts to boost
SERIES_CONFIG = {
    "f1": {
        "hashtags": ["#F1", "#Formula1"],
        "query": "(#F1 OR #Formula1) -filter:replies",
        "boosted_accounts": ["f1", "fia", "reaboradio", "chris_medland"],
        "race_hashtags": ["#MonacoGP", "#BritishGP", "#SingaporeGP"],
    },
    "imsa": {
        "hashtags": ["#IMSA", "#Rolex24", "#Daytona24", "#WeatherTech"],
        "query": "(#IMSA OR #Rolex24 OR #Daytona24) -filter:replies",
        "boosted_accounts": ["IMABORADING", "marshallpruett", "johndagys"],
        "race_hashtags": ["#Rolex24", "#Sebring12", "#PetitLeMans"],
    },
    "wec": {
        "hashtags": ["#WEC", "#LeMans24", "#Hypercar", "#24hLeMans"],
        "query": "(#WEC OR #LeMans24 OR #Hypercar) -filter:replies",
        "boosted_accounts": ["FIAWEC", "24hoursoflemans", "dailysportscar"],
        "race_hashtags": ["#24hLeMans", "#6HSpa", "#8HBahrain"],
    },
    "nascar": {
        "hashtags": ["#NASCAR", "#NASCARCup"],
        "query": "(#NASCAR OR #NASCARCup) -filter:replies",
        "boosted_accounts": ["NASCAR", "bobpockrass", "dustinlong"],
        "race_hashtags": ["#Daytona500", "#CokeZero400", "#Bristol"],
    },
    "indycar": {
        "hashtags": ["#IndyCar", "#Indy500", "#INDYCAR"],
        "query": "(#IndyCar OR #INDYCAR) -filter:replies",
        "boosted_accounts": ["IndyCar", "IndyCaronNBC", "jaborading"],
        "race_hashtags": ["#Indy500", "#GPSTPETE", "#DetroitGP"],
    },
    "wrc": {
        "hashtags": ["#WRC", "#WorldRally"],
        "query": "(#WRC OR #WorldRally) -filter:replies",
        "boosted_accounts": ["OfficialWRC", "WRCwings"],
        "race_hashtags": ["#RallyMonteCarlo", "#RallyFinland"],
    },
    "motogp": {
        "hashtags": ["#MotoGP"],
        "query": "#MotoGP -filter:replies",
        "boosted_accounts": ["MotoGP", "motaborading"],
        "race_hashtags": ["#QatarGP", "#ItalianGP", "#ValenciaGP"],
    },
}


def search_twitter_v2(
    query: str,
    count: int = 25,
    filter_replies: bool = True
) -> Optional[List[Dict]]:
    """
    Search Twitter with improved query handling.
    
    Args:
        query: Search query (use OR for multiple terms)
        count: Number of results
        filter_replies: Filter out replies for cleaner results
    
    Returns:
        List of tweet dicts with enhanced metadata
    """
    cache_key = f"v2:{query}:{count}"
    now = time.time()
    
    # Check cache
    if cache_key in _tweet_cache:
        data, timestamp = _tweet_cache[cache_key]
        if now - timestamp < CACHE_TTL:
            return data
    
    # Build search query
    search_query = query
    if filter_replies and "-filter:replies" not in query:
        search_query = f"{query} -filter:replies"
    
    try:
        result = subprocess.run(
            ["bird", "search", search_query, "-n", str(count), "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Parse JSON (skip any warning lines)
        output = result.stdout
        json_start = output.find('[')
        if json_start == -1:
            return None
        
        tweets = json.loads(output[json_start:])
        
        # Filter out obvious false positives
        filtered = _filter_tweets(tweets)
        
        _tweet_cache[cache_key] = (filtered, now)
        return filtered
        
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[Monitor] Error searching '{query}': {e}")
        return None


def _filter_tweets(tweets: List[Dict]) -> List[Dict]:
    """
    Filter out false positive tweets.
    
    Removes:
    - Tweets from accounts with IMSA/F1/etc in username but unrelated content
    - Spam patterns
    - Non-English tweets (optional, configurable)
    """
    filtered = []
    
    # Known motorsport keywords to validate relevance
    relevance_keywords = [
        "race", "racing", "lap", "podium", "win", "driver", "team", "car",
        "track", "pit", "qualifying", "grid", "p1", "p2", "p3", "dnf",
        "crash", "overtake", "championship", "series", "gp", "grand prix",
        "lemans", "daytona", "sebring", "spa", "monza", "silverstone",
        "porsche", "ferrari", "bmw", "cadillac", "toyota", "mercedes",
        "mclaren", "aston martin", "ford", "corvette", "acura", "lamborghini",
    ]
    
    for tweet in tweets:
        text = tweet.get("text", "").lower()
        
        # Skip if text is too short
        if len(text) < 20:
            continue
        
        # Check for motorsport relevance
        has_hashtag = any(tag in text for tag in ["#f1", "#imsa", "#wec", "#nascar", "#wrc", "#motogp", "#rolex24", "#lemans"])
        has_keyword = any(kw in text for kw in relevance_keywords)
        
        if has_hashtag or has_keyword:
            filtered.append(tweet)
    
    return filtered


def calculate_engagement_score(tweet: Dict, series: Optional[str] = None) -> float:
    """
    Calculate weighted engagement score.
    
    Weights:
    - Likes: 1x (baseline)
    - Retweets: 2x (amplification value)
    - Replies: 3x (engagement depth)
    - Quote tweets: 2.5x (commentary value)
    - Verified author boost: 1.5x
    - Boosted account: 2x
    """
    likes = tweet.get("likeCount", 0)
    retweets = tweet.get("retweetCount", 0)
    replies = tweet.get("replyCount", 0)
    
    base_score = (likes * 1) + (retweets * 2) + (replies * 3)
    
    # Verified boost (check if available in data)
    author = tweet.get("author", {})
    if author.get("verified") or author.get("isBlueVerified"):
        base_score *= 1.5
    
    # Boosted accounts for series
    if series and series in SERIES_CONFIG:
        username = author.get("username", "").lower()
        if username in SERIES_CONFIG[series]["boosted_accounts"]:
            base_score *= 2.0
    
    return base_score


def detect_race_weekend_spike(
    tweets: List[Dict],
    series: str
) -> Optional[Dict]:
    """
    Detect if we're in a race weekend based on tweet patterns.
    
    Indicators:
    - High volume of race-specific hashtags
    - Timing keywords (quali, race day, final lap)
    - Engagement spikes vs. baseline
    """
    if series not in SERIES_CONFIG:
        return None
    
    config = SERIES_CONFIG[series]
    race_hashtags = config.get("race_hashtags", [])
    
    # Count race-specific hashtag usage
    race_tag_count = 0
    timing_keywords = 0
    
    timing_terms = [
        "qualifying", "quali", "race day", "lights out", "green flag",
        "final lap", "last lap", "checkered flag", "podium", "p1",
        "live", "watching", "going green", "restart",
    ]
    
    for tweet in tweets:
        text = tweet.get("text", "").lower()
        
        # Check race hashtags
        for tag in race_hashtags:
            if tag.lower() in text:
                race_tag_count += 1
                break
        
        # Check timing keywords
        for term in timing_terms:
            if term in text:
                timing_keywords += 1
                break
    
    # Calculate metrics
    race_tag_ratio = race_tag_count / len(tweets) if tweets else 0
    timing_ratio = timing_keywords / len(tweets) if tweets else 0
    avg_engagement = sum(calculate_engagement_score(t, series) for t in tweets) / len(tweets) if tweets else 0
    
    # Determine if race weekend
    is_race_weekend = (
        race_tag_ratio > 0.15 or  # 15% have race-specific tags
        timing_ratio > 0.2 or     # 20% have timing keywords
        avg_engagement > 50       # High engagement baseline
    )
    
    if is_race_weekend:
        return {
            "detected": True,
            "raceTagRatio": round(race_tag_ratio * 100, 1),
            "timingKeywordRatio": round(timing_ratio * 100, 1),
            "avgEngagement": round(avg_engagement, 1),
            "confidence": "high" if (race_tag_ratio > 0.3 or timing_ratio > 0.3) else "moderate",
        }
    
    return None


def get_hot_tweets_v2(
    series: Optional[str] = None,
    count: int = 30
) -> List[Dict]:
    """
    Get hot tweets with enhanced analysis.
    
    Returns tweets with:
    - Multi-dimensional sentiment scores
    - Engagement weighting
    - Entity extraction
    """
    # Determine search queries
    if series and series in SERIES_CONFIG:
        queries = [SERIES_CONFIG[series]["query"]]
    else:
        # Search all series
        queries = [config["query"] for config in SERIES_CONFIG.values()]
    
    all_tweets = []
    seen_ids = set()
    
    for query in queries:
        tweets = search_twitter_v2(query, count=count)
        if not tweets:
            continue
        
        for tweet in tweets:
            tweet_id = tweet.get("id")
            if tweet_id in seen_ids:
                continue
            seen_ids.add(tweet_id)
            
            # Analyze sentiment
            text = tweet.get("text", "")
            sentiment_score = analyze_sentiment(text)
            
            # Calculate engagement
            engagement = calculate_engagement_score(tweet, series)
            
            # Extract hashtags
            hashtags = re.findall(r'#(\w+)', text)
            
            all_tweets.append({
                "id": tweet_id,
                "text": text,
                "author": tweet.get("author", {}).get("username", "unknown"),
                "authorName": tweet.get("author", {}).get("name", "Unknown"),
                "authorVerified": tweet.get("author", {}).get("verified", False),
                "createdAt": tweet.get("createdAt", ""),
                "engagement": engagement,
                "likes": tweet.get("likeCount", 0),
                "retweets": tweet.get("retweetCount", 0),
                "replies": tweet.get("replyCount", 0),
                # Enhanced sentiment
                "sentiment": sentiment_score.overall,
                "sentimentDimensions": sentiment_score.dimensions,
                "sentimentDominant": sentiment_score.dominant,
                "sentimentLabel": get_sentiment_label(sentiment_score),
                "sentimentConfidence": sentiment_score.confidence,
                "keywordsFound": sentiment_score.keywords_found,
                # Metadata
                "hashtags": hashtags,
                "media": tweet.get("media", []),
                "hasMedia": len(tweet.get("media", [])) > 0,
                "quotedTweet": tweet.get("quotedTweet"),
            })
    
    # Sort by engagement
    all_tweets.sort(key=lambda t: t["engagement"], reverse=True)
    
    return all_tweets


def get_sentiment_summary_v2(tweets: List[Dict]) -> Dict:
    """
    Generate enhanced sentiment summary with dimension breakdown.
    """
    if not tweets:
        return {
            "total": 0,
            "overall": "neutral",
            "dimensions": {},
            "topKeywords": [],
            "raceWeekend": None,
            "controversy": None,
        }
    
    # Aggregate dimensions
    dim_totals = {
        "excitement": 0.0,
        "controversy": 0.0,
        "disappointment": 0.0,
        "celebration": 0.0,
        "informational": 0.0,
    }
    
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
    all_keywords = []
    
    for tweet in tweets:
        # Overall sentiment
        sentiment_counts[tweet.get("sentiment", "neutral")] += 1
        
        # Dimension scores
        dims = tweet.get("sentimentDimensions", {})
        for dim, score in dims.items():
            dim_totals[dim] = dim_totals.get(dim, 0) + score
        
        # Keywords
        all_keywords.extend(tweet.get("keywordsFound", []))
    
    # Average dimensions
    n = len(tweets)
    dim_averages = {k: round(v / n, 3) for k, v in dim_totals.items()}
    
    # Dominant dimension
    dominant = max(dim_averages, key=dim_averages.get)
    
    # Top keywords
    from collections import Counter
    keyword_counts = Counter(all_keywords)
    top_keywords = [kw for kw, _ in keyword_counts.most_common(10)]
    
    # Overall sentiment
    if sentiment_counts["positive"] > sentiment_counts["negative"]:
        overall = "positive"
    elif sentiment_counts["negative"] > sentiment_counts["positive"]:
        overall = "negative"
    else:
        overall = "neutral"
    
    # Calculate sentiment score (-100 to 100)
    sentiment_score = round(
        (sentiment_counts["positive"] - sentiment_counts["negative"]) / n * 100,
        1
    )
    
    # Average engagement
    avg_engagement = sum(t.get("engagement", 0) for t in tweets) / n
    
    # Detect spikes
    controversy = detect_controversy_spike(tweets)
    
    return {
        "total": n,
        "overall": overall,
        "sentimentScore": sentiment_score,
        "sentimentCounts": sentiment_counts,
        "dimensions": dim_averages,
        "dominantDimension": dominant,
        "topKeywords": top_keywords,
        "avgEngagement": round(avg_engagement, 1),
        "controversy": controversy,
        "highEngagementCount": sum(1 for t in tweets if t.get("engagement", 0) > 50),
    }


# Compatibility functions (drop-in replacements)
def get_hot_tweets(series: Optional[str] = None, count: int = 20) -> List[Dict]:
    """Backward-compatible wrapper."""
    return get_hot_tweets_v2(series, count)


def get_sentiment_summary(tweets: List[Dict]) -> Dict:
    """Backward-compatible wrapper."""
    return get_sentiment_summary_v2(tweets)
