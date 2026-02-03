"""GridView Health Check & Dashboard API.

Provides system status, endpoint health, and cache statistics.
"""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
from datetime import datetime


def check_endpoint(url: str, timeout: int = 5) -> dict:
    """Check if an external data source is reachable."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
        start = datetime.now()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = (datetime.now() - start).total_seconds() * 1000
            return {
                "status": "ok",
                "latency_ms": round(latency, 1),
                "code": resp.status
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)[:100]
        }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(self.path).query)
        
        # Deep health check with external API checks
        if 'deep' in query or 'full' in query:
            external_checks = {
                "nascar": check_endpoint("https://cf.nascar.com/cacher/2025/race_list_basic.json"),
                "sportsdb_motogp": check_endpoint("https://www.thesportsdb.com/api/v1/json/3/eventsseason.php?id=4407&s=2025"),
                "sportsdb_wec": check_endpoint("https://www.thesportsdb.com/api/v1/json/3/eventsseason.php?id=4413&s=2025"),
                "openf1": check_endpoint("https://api.openf1.org/v1/meetings?year=2025"),
            }
            
            # Check cache stats if available
            try:
                from api._utils import get_cache_stats
                cache_stats = get_cache_stats()
            except ImportError:
                cache_stats = {"note": "Cache module not loaded"}
            
            all_ok = all(c.get("status") == "ok" for c in external_checks.values())
            
            response = {
                "status": "healthy" if all_ok else "degraded",
                "app": "GridView",
                "version": "0.3.0",
                "timestamp": datetime.now().isoformat(),
                "endpoints": {
                    "/api/health": "ok",
                    "/api/f1": "ok",
                    "/api/wrc": "ok",
                    "/api/wec": "ok",
                    "/api/imsa": "ok",
                    "/api/nascar": "ok",
                    "/api/motogp": "ok",
                    "/api/indycar": "ok"
                },
                "data_sources": external_checks,
                "cache": cache_stats
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
            return
        
        # Simple health check (default)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {
            "status": "healthy",
            "app": "GridView",
            "version": "0.3.0",
            "timestamp": datetime.now().isoformat(),
            "endpoints": [
                "/api/health",
                "/api/f1",
                "/api/wrc",
                "/api/wec",
                "/api/imsa",
                "/api/nascar",
                "/api/motogp",
                "/api/indycar"
            ],
            "docs": {
                "nascar": "?series=cup|xfinity|truck&upcoming&results",
                "motogp": "?upcoming&results&year=2025",
                "indycar": "?upcoming&featured",
                "health": "?deep for full diagnostics"
            }
        }
        self.wfile.write(json.dumps(response, indent=2).encode())
        return
