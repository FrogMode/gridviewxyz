"""Shared utilities for GridView API endpoints.

Provides:
- Caching layer with TTL
- Retry logic with exponential backoff
- Error handling decorators
- Common response helpers
"""
import json
import urllib.request
import urllib.error
from datetime import datetime
from functools import wraps
import time
from typing import Optional, Dict, Any, Callable

# Global cache storage
_cache: Dict[str, tuple] = {}
_cache_stats = {
    "hits": 0,
    "misses": 0,
    "errors": 0
}


def cached_fetch(
    url: str,
    ttl: int = 300,
    timeout: int = 15,
    headers: Optional[Dict[str, str]] = None,
    retries: int = 2,
    backoff: float = 1.0
) -> Optional[dict]:
    """
    Fetch URL with caching and retry logic.
    
    Args:
        url: URL to fetch
        ttl: Cache time-to-live in seconds (default 5 minutes)
        timeout: Request timeout in seconds
        headers: Optional HTTP headers
        retries: Number of retry attempts
        backoff: Base backoff time in seconds (doubles each retry)
    
    Returns:
        Parsed JSON response or None on failure
    """
    global _cache_stats
    now = datetime.now().timestamp()
    
    # Check cache
    if url in _cache:
        data, timestamp = _cache[url]
        if now - timestamp < ttl:
            _cache_stats["hits"] += 1
            return data
    
    _cache_stats["misses"] += 1
    
    # Prepare request
    req_headers = {"User-Agent": "GridView/1.0"}
    if headers:
        req_headers.update(headers)
    
    req = urllib.request.Request(url, headers=req_headers)
    
    # Fetch with retries
    last_error = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
                _cache[url] = (data, now)
                return data
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code >= 500:
                # Server error, worth retrying
                time.sleep(backoff * (2 ** attempt))
                continue
            # Client error (4xx), don't retry
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = e
            time.sleep(backoff * (2 ** attempt))
            continue
    
    _cache_stats["errors"] += 1
    return None


def get_cache_stats() -> dict:
    """Get cache statistics."""
    return {
        "hits": _cache_stats["hits"],
        "misses": _cache_stats["misses"],
        "errors": _cache_stats["errors"],
        "cached_urls": len(_cache),
        "hit_rate": (_cache_stats["hits"] / max(1, _cache_stats["hits"] + _cache_stats["misses"])) * 100
    }


def clear_cache(pattern: Optional[str] = None) -> int:
    """Clear cache entries, optionally matching a pattern."""
    global _cache
    if pattern is None:
        count = len(_cache)
        _cache = {}
        return count
    
    keys_to_remove = [k for k in _cache if pattern in k]
    for k in keys_to_remove:
        del _cache[k]
    return len(keys_to_remove)


def send_json_response(handler, data: Any, status: int = 200, cache_seconds: int = 300):
    """Send a JSON response with standard headers."""
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Cache-Control', f'public, max-age={cache_seconds}')
    handler.end_headers()
    handler.wfile.write(json.dumps(data, indent=2).encode())


def send_error_response(handler, error: str, status: int = 500):
    """Send an error JSON response."""
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.end_headers()
    handler.wfile.write(json.dumps({"error": error}).encode())


def with_fallback(primary_fn: Callable, fallback_fn: Callable) -> Callable:
    """
    Decorator/wrapper that tries primary function, falls back on error.
    
    Usage:
        result = with_fallback(fetch_live_data, fetch_cached_data)()
    """
    def wrapper(*args, **kwargs):
        try:
            result = primary_fn(*args, **kwargs)
            if result is not None:
                return result
        except Exception:
            pass
        return fallback_fn(*args, **kwargs)
    return wrapper


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, max_calls: int = 10, period: float = 60.0):
        self.max_calls = max_calls
        self.period = period
        self.calls: list = []
    
    def acquire(self) -> bool:
        """Try to acquire a rate limit slot. Returns True if allowed."""
        now = time.time()
        # Remove old calls
        self.calls = [t for t in self.calls if now - t < self.period]
        
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        return False
    
    def wait_time(self) -> float:
        """Return seconds to wait before next call is allowed."""
        if len(self.calls) < self.max_calls:
            return 0
        oldest = min(self.calls)
        return max(0, self.period - (time.time() - oldest))


# Shared rate limiters for external APIs
RATE_LIMITERS = {
    "nascar": RateLimiter(max_calls=30, period=60),
    "sportsdb": RateLimiter(max_calls=20, period=60),
}
