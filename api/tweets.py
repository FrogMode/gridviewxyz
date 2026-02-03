"""Motorsport Tweets API - fetches live tweets from racing accounts and hashtags via bird CLI."""
from http.server import BaseHTTPRequestHandler
import json
import subprocess
import time
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import re

# In-memory cache with TTL
_tweet_cache: Dict[str, Tuple[List, float]] = {}
CACHE_TTL = 60  # 1 minute cache

# Motorsport search queries (hashtags and accounts)
# These are searched via bird CLI (cookie-based Twitter access)
SEARCH_QUERIES = {
    "all": "(#F1 OR #NASCAR OR #IndyCar OR #IMSA OR #WEC OR #MotoGP) -filter:replies",
    "f1": "(#F1 OR #Formula1) -filter:replies",
    "nascar": "(#NASCAR OR #NASCARCup) -filter:replies",
    "indycar": "(#IndyCar OR #INDYCAR) -filter:replies",
    "imsa": "(#IMSA OR #Rolex24 OR #WeatherTech) -filter:replies",
    "wec": "(#WEC OR #LeMans24 OR #Hypercar) -filter:replies",
    "motogp": "(#MotoGP) -filter:replies",
}

# Featured accounts to track
FEATURED_ACCOUNTS = [
    "F1", "NASCAR", "IndyCar", "IMABORACING", "FIAWEC", "MotoGP",
    "ChrisMedlandF1", "ScarbsTech", "JennaFryer"
]


def run_bird_search(query: str, limit: int = 10) -> list:
    """Execute bird search command and return tweets with caching."""
    cache_key = f"search:{query}:{limit}"
    now = time.time()
    
    # Check cache
    if cache_key in _tweet_cache:
        data, timestamp = _tweet_cache[cache_key]
        if now - timestamp < CACHE_TTL:
            return data
    
    try:
        cmd = [
            "bird", "search", query,
            "-n", str(limit),
            "--json"
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Parse JSON output (skip any warning lines)
        output = result.stdout.strip()
        if not output:
            return []
        
        # Find JSON array start
        json_start = output.find('[')
        if json_start == -1:
            return []
        
        tweets = json.loads(output[json_start:])
        result_tweets = tweets if isinstance(tweets, list) else []
        
        # Cache result
        _tweet_cache[cache_key] = (result_tweets, now)
        return result_tweets
        
    except subprocess.TimeoutExpired:
        return []
    except json.JSONDecodeError:
        return []
    except Exception as e:
        print(f"[tweets.py] Bird error: {e}")
        return []


def run_bird_user_tweets(username: str, limit: int = 5) -> list:
    """Fetch recent tweets from a specific user."""
    try:
        cmd = [
            "bird", "user-tweets", f"@{username}",
            "-n", str(limit),
            "--json"
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = result.stdout.strip()
        if not output:
            return []
        
        tweets = json.loads(output)
        return tweets if isinstance(tweets, list) else []
        
    except Exception as e:
        print(f"[tweets.py] User tweets error for @{username}: {e}")
        return []


def format_tweet(tweet: dict) -> dict:
    """Format tweet data for frontend consumption."""
    author = tweet.get("author", {})
    
    # Parse created date
    created_at = tweet.get("createdAt", "")
    try:
        # Twitter format: "Tue Feb 03 18:57:43 +0000 2026"
        dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
        iso_date = dt.isoformat()
        relative_time = get_relative_time(dt)
    except:
        iso_date = created_at
        relative_time = ""
    
    # Get media (first image if available)
    media = tweet.get("media", [])
    image_url = None
    for m in media:
        if m.get("type") in ["photo", "image"]:
            image_url = m.get("previewUrl") or m.get("url")
            break
        elif m.get("type") == "video":
            image_url = m.get("previewUrl") or m.get("url")
            break
    
    # Build avatar URL from author ID
    author_id = tweet.get("authorId", "")
    avatar_url = f"https://unavatar.io/twitter/{author.get('username', '')}"
    
    return {
        "id": tweet.get("id"),
        "text": clean_text(tweet.get("text", "")),
        "author": {
            "username": author.get("username", ""),
            "name": author.get("name", ""),
            "avatar": avatar_url,
        },
        "createdAt": iso_date,
        "relativeTime": relative_time,
        "metrics": {
            "likes": tweet.get("likeCount", 0),
            "retweets": tweet.get("retweetCount", 0),
            "replies": tweet.get("replyCount", 0),
        },
        "media": image_url,
        "url": f"https://x.com/{author.get('username')}/status/{tweet.get('id')}"
    }


def clean_text(text: str) -> str:
    """Clean tweet text, truncate if needed."""
    # Remove t.co URLs at end
    text = re.sub(r'\s*https://t\.co/\S+$', '', text)
    # Truncate long tweets
    if len(text) > 280:
        text = text[:277] + "..."
    return text.strip()


def get_relative_time(dt: datetime) -> str:
    """Get relative time string like '2h ago'."""
    try:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        diff = now - dt
        
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = seconds // 60
            return f"{mins}m ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h ago"
        elif seconds < 604800:
            days = seconds // 86400
            return f"{days}d ago"
        else:
            return dt.strftime("%b %d")
    except:
        return ""


def dedupe_tweets(tweets: list) -> list:
    """Remove duplicate tweets by ID."""
    seen = set()
    unique = []
    for tweet in tweets:
        tid = tweet.get("id")
        if tid and tid not in seen:
            seen.add(tid)
            unique.append(tweet)
    return unique


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            
            # Get parameters
            series = query.get('series', ['all'])[0].lower()
            limit = min(int(query.get('limit', ['15'])[0]), 50)
            mode = query.get('mode', ['search'])[0]  # search or accounts
            
            # Validate series
            if series not in SEARCH_QUERIES:
                series = "all"
            
            tweets = []
            
            if mode == "accounts":
                # Fetch from featured accounts
                for account in FEATURED_ACCOUNTS[:5]:  # Limit to prevent timeout
                    user_tweets = run_bird_user_tweets(account, limit=3)
                    tweets.extend(user_tweets)
            else:
                # Search mode (default)
                search_query = SEARCH_QUERIES[series]
                tweets = run_bird_search(search_query, limit=limit)
            
            # Dedupe and format
            tweets = dedupe_tweets(tweets)
            formatted = [format_tweet(t) for t in tweets[:limit]]
            
            # Sort by date (newest first)
            formatted.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
            
            response = {
                "series": series,
                "count": len(formatted),
                "tweets": formatted,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            self._send_json(response)
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            error_response = {"error": str(e), "tweets": []}
            self.wfile.write(json.dumps(error_response).encode())
    
    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=60')  # Cache 1 min
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
