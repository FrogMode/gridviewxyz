"""Trending API v2 - Enhanced sentiment-driven recommendations.

GET /api/sentiment/trending?series=imsa&limit=10

Returns:
- Hot topics with multi-dimensional sentiment scores
- Matched news articles
- Race weekend detection
- Controversy alerts
- Overall sentiment summary with dimension breakdown
"""
from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

# Use enhanced v2 modules
from .monitor_v2 import (
    get_hot_tweets_v2,
    get_sentiment_summary_v2,
    detect_race_weekend_spike,
    SERIES_CONFIG,
)
from .topics_v2 import extract_topics_v2
from .articles import match_articles_to_topics, get_top_articles_for_series
from .analyzer import detect_controversy_spike


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            
            # Parameters
            series = query.get('series', [None])[0]
            limit = min(int(query.get('limit', ['10'])[0]), 20)
            include_tweets = query.get('tweets', ['false'])[0].lower() == 'true'
            include_dimensions = query.get('dimensions', ['true'])[0].lower() == 'true'
            
            # Get hot tweets with enhanced analysis
            tweets = get_hot_tweets_v2(series=series, count=40)
            
            # Extract trending topics with entity detection
            topics = extract_topics_v2(tweets)[:limit]
            
            # Match articles to topics
            topics_with_articles = match_articles_to_topics(topics)
            
            # Get enhanced sentiment summary
            summary = get_sentiment_summary_v2(tweets)
            
            # Detect race weekend activity
            race_weekend = None
            if series:
                race_weekend = detect_race_weekend_spike(tweets, series)
            
            # Detect controversy spike
            controversy = detect_controversy_spike(tweets)
            
            # Get top articles for series (if specified)
            series_articles = []
            if series:
                series_articles = get_top_articles_for_series(series, limit=5)
            
            # Build response
            response = {
                "series": series or "all",
                "generatedAt": self._get_timestamp(),
                "apiVersion": "2.0",
                "summary": summary,
                "topics": topics_with_articles,
                "featuredArticles": series_articles,
                # New in v2
                "alerts": {
                    "raceWeekend": race_weekend,
                    "controversy": controversy,
                },
            }
            
            # Add sentiment dimension breakdown if requested
            if include_dimensions:
                response["sentimentDimensions"] = summary.get("dimensions", {})
                response["dominantSentiment"] = summary.get("dominantDimension", "informational")
            
            # Optionally include raw tweets (with enhanced data)
            if include_tweets:
                # Return enriched tweet data
                response["tweets"] = [
                    {
                        "id": t["id"],
                        "text": t["text"],
                        "author": t["author"],
                        "authorName": t["authorName"],
                        "createdAt": t["createdAt"],
                        "engagement": t["engagement"],
                        "likes": t["likes"],
                        "retweets": t["retweets"],
                        "replies": t["replies"],
                        "sentiment": t["sentiment"],
                        "sentimentLabel": t.get("sentimentLabel", ""),
                        "sentimentDimensions": t.get("sentimentDimensions", {}) if include_dimensions else None,
                        "hashtags": t.get("hashtags", []),
                        "hasMedia": t.get("hasMedia", False),
                    }
                    for t in tweets[:25]
                ]
            
            self._send_json(response)
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": str(e),
                "series": query.get('series', [None])[0] if 'query' in dir() else None,
            }).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=180')  # Cache 3 min
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def _get_timestamp(self):
        from datetime import datetime
        return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
