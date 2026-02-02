"""Motorsport News API - aggregates RSS feeds from Motorsport.com."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
import re

FEEDS = {
    "all": "https://www.motorsport.com/rss/all/news/",
    "f1": "https://www.motorsport.com/rss/f1/news/",
    "wrc": "https://www.motorsport.com/rss/wrc/news/",
    "motogp": "https://www.motorsport.com/rss/motogp/news/",
    "indycar": "https://www.motorsport.com/rss/indycar/news/",
    "nascar": "https://www.motorsport.com/rss/nascar-cup/news/",
    "wec": "https://www.motorsport.com/rss/wec/news/",
}

def clean_description(desc: str) -> str:
    """Clean HTML from description."""
    if not desc:
        return ""
    # Remove CDATA wrapper
    desc = desc.replace("<![CDATA[", "").replace("]]>", "")
    # Remove HTML tags
    desc = re.sub(r'<[^>]+>', '', desc)
    # Unescape HTML entities
    desc = unescape(desc)
    # Truncate
    if len(desc) > 280:
        desc = desc[:277] + "..."
    return desc.strip()

def fetch_feed(category: str = "all", limit: int = 20) -> list:
    """Fetch and parse RSS feed."""
    url = FEEDS.get(category, FEEDS["all"])
    req = urllib.request.Request(url, headers={
        "User-Agent": "GridView/1.0",
        "Accept": "application/rss+xml, application/xml, text/xml"
    })
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_data = resp.read()
    
    root = ET.fromstring(xml_data)
    items = []
    
    for item in root.findall(".//item")[:limit]:
        # Get enclosure (image)
        enclosure = item.find("enclosure")
        image_url = enclosure.get("url") if enclosure is not None else None
        
        # Get categories
        categories = [cat.text for cat in item.findall("category") if cat.text]
        
        # Parse date
        pub_date = item.findtext("pubDate", "")
        
        items.append({
            "id": item.findtext("guid", ""),
            "title": item.findtext("title", "").strip(),
            "link": item.findtext("link", ""),
            "description": clean_description(item.findtext("description", "")),
            "image": image_url,
            "categories": categories,
            "published": pub_date,
        })
    
    return items

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            
            # Get parameters
            category = query.get('category', ['all'])[0]
            limit = min(int(query.get('limit', ['20'])[0]), 50)
            
            # Validate category
            if category not in FEEDS:
                category = "all"
            
            # Return available categories
            if 'categories' in query:
                response = {
                    "categories": list(FEEDS.keys()),
                    "labels": {
                        "all": "All Motorsport",
                        "f1": "Formula 1",
                        "wrc": "WRC",
                        "motogp": "MotoGP",
                        "indycar": "IndyCar",
                        "nascar": "NASCAR",
                        "wec": "WEC / Endurance"
                    }
                }
                self._send_json(response)
                return
            
            # Fetch news
            articles = fetch_feed(category, limit)
            
            response = {
                "category": category,
                "count": len(articles),
                "articles": articles
            }
            
            self._send_json(response)
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=300')  # Cache 5 min
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
