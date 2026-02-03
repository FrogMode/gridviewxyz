"""Trending API - Main endpoint for sentiment-driven recommendations.

GET /api/sentiment/trending?series=imsa&limit=10

Returns:
- Hot topics with sentiment scores
- Matched news articles
- Overall sentiment summary
"""
from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

from .monitor import get_hot_tweets, get_sentiment_summary
from .topics import extract_topics
from .articles import match_articles_to_topics, get_top_articles_for_series


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            
            # Parameters
            series = query.get('series', [None])[0]
            limit = min(int(query.get('limit', ['10'])[0]), 20)
            include_tweets = query.get('tweets', ['false'])[0].lower() == 'true'
            
            # Get hot tweets
            tweets = get_hot_tweets(series=series, count=30)
            
            # Extract trending topics
            topics = extract_topics(tweets)[:limit]
            
            # Match articles to topics
            topics_with_articles = match_articles_to_topics(topics)
            
            # Get sentiment summary
            summary = get_sentiment_summary(tweets)
            
            # Get top articles for series (if specified)
            series_articles = []
            if series:
                series_articles = get_top_articles_for_series(series, limit=5)
            
            # Build response
            response = {
                "series": series or "all",
                "generatedAt": self._get_timestamp(),
                "summary": summary,
                "topics": topics_with_articles,
                "featuredArticles": series_articles,
            }
            
            # Optionally include raw tweets
            if include_tweets:
                response["tweets"] = tweets[:20]
            
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
