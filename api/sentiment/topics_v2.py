"""Enhanced Topic Extractor v2.

Improvements:
- More comprehensive driver/team databases
- Real-time event detection
- Controversy topic clustering
- Trending velocity calculation
"""
import re
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

# Expanded driver database with common variations
DRIVERS = {
    # F1 2024-2025 (with variations)
    "verstappen": {"full": "Max Verstappen", "team": "Red Bull", "series": "f1"},
    "max": {"full": "Max Verstappen", "team": "Red Bull", "series": "f1"},
    "hamilton": {"full": "Lewis Hamilton", "team": "Ferrari", "series": "f1"},
    "lewis": {"full": "Lewis Hamilton", "team": "Ferrari", "series": "f1"},
    "leclerc": {"full": "Charles Leclerc", "team": "Ferrari", "series": "f1"},
    "charles": {"full": "Charles Leclerc", "team": "Ferrari", "series": "f1"},
    "sainz": {"full": "Carlos Sainz", "team": "Williams", "series": "f1"},
    "carlos": {"full": "Carlos Sainz", "team": "Williams", "series": "f1"},
    "norris": {"full": "Lando Norris", "team": "McLaren", "series": "f1"},
    "lando": {"full": "Lando Norris", "team": "McLaren", "series": "f1"},
    "piastri": {"full": "Oscar Piastri", "team": "McLaren", "series": "f1"},
    "oscar": {"full": "Oscar Piastri", "team": "McLaren", "series": "f1"},
    "russell": {"full": "George Russell", "team": "Mercedes", "series": "f1"},
    "george": {"full": "George Russell", "team": "Mercedes", "series": "f1"},
    "alonso": {"full": "Fernando Alonso", "team": "Aston Martin", "series": "f1"},
    "fernando": {"full": "Fernando Alonso", "team": "Aston Martin", "series": "f1"},
    "antonelli": {"full": "Andrea Kimi Antonelli", "team": "Mercedes", "series": "f1"},
    "bearman": {"full": "Ollie Bearman", "team": "Haas", "series": "f1"},
    
    # IMSA Notable Drivers
    "tandy": {"full": "Nick Tandy", "team": "Porsche Penske", "series": "imsa"},
    "cameron": {"full": "Dane Cameron", "team": "Porsche Penske", "series": "imsa"},
    "estre": {"full": "Kevin Estre", "team": "Porsche Penske", "series": "imsa"},
    "nasr": {"full": "Felipe Nasr", "team": "Porsche Penske", "series": "imsa"},
    "vanthoor": {"full": "Laurens Vanthoor", "team": "BMW", "series": "imsa"},
    "wittmer": {"full": "Kuno Wittmer", "team": "BMW", "series": "imsa"},
    "bamber": {"full": "Earl Bamber", "team": "Cadillac", "series": "imsa"},
    "lynn": {"full": "Alex Lynn", "team": "Cadillac", "series": "imsa"},
    "bourdais": {"full": "Sébastien Bourdais", "team": "Cadillac", "series": "imsa"},
    "derani": {"full": "Pipo Derani", "team": "Acura", "series": "imsa"},
    "pagenaud": {"full": "Simon Pagenaud", "team": "Acura", "series": "imsa"},
    
    # WEC
    "buemi": {"full": "Sébastien Buemi", "team": "Toyota", "series": "wec"},
    "hartley": {"full": "Brendon Hartley", "team": "Toyota", "series": "wec"},
    "hirakawa": {"full": "Ryo Hirakawa", "team": "Toyota", "series": "wec"},
    "kobayashi": {"full": "Kamui Kobayashi", "team": "Toyota", "series": "wec"},
    "vergne": {"full": "Jean-Éric Vergne", "team": "Peugeot", "series": "wec"},
    "di resta": {"full": "Paul di Resta", "team": "Peugeot", "series": "wec"},
    
    # NASCAR
    "larson": {"full": "Kyle Larson", "team": "Hendrick", "series": "nascar"},
    "elliott": {"full": "Chase Elliott", "team": "Hendrick", "series": "nascar"},
    "hamlin": {"full": "Denny Hamlin", "team": "Joe Gibbs", "series": "nascar"},
    "busch": {"full": "Kyle Busch", "team": "RCR", "series": "nascar"},
    "blaney": {"full": "Ryan Blaney", "team": "Penske", "series": "nascar"},
    "logano": {"full": "Joey Logano", "team": "Penske", "series": "nascar"},
    "chastain": {"full": "Ross Chastain", "team": "Trackhouse", "series": "nascar"},
    
    # IndyCar
    "palou": {"full": "Álex Palou", "team": "Chip Ganassi", "series": "indycar"},
    "newgarden": {"full": "Josef Newgarden", "team": "Penske", "series": "indycar"},
    "power": {"full": "Will Power", "team": "Penske", "series": "indycar"},
    "herta": {"full": "Colton Herta", "team": "Andretti", "series": "indycar"},
    "mclaughlin": {"full": "Scott McLaughlin", "team": "Penske", "series": "indycar"},
    "o'ward": {"full": "Pato O'Ward", "team": "Arrow McLaren", "series": "indycar"},
    "dixon": {"full": "Scott Dixon", "team": "Chip Ganassi", "series": "indycar"},
}

# Teams with variations
TEAMS = {
    # F1
    "red bull": {"full": "Red Bull Racing", "series": "f1"},
    "redbull": {"full": "Red Bull Racing", "series": "f1"},
    "ferrari": {"full": "Scuderia Ferrari", "series": "f1"},
    "mercedes": {"full": "Mercedes-AMG", "series": "f1"},
    "mclaren": {"full": "McLaren", "series": "f1"},
    "aston martin": {"full": "Aston Martin Aramco", "series": "f1"},
    "alpine": {"full": "Alpine", "series": "f1"},
    "williams": {"full": "Williams Racing", "series": "f1"},
    "haas": {"full": "Haas F1", "series": "f1"},
    "kick sauber": {"full": "Kick Sauber", "series": "f1"},
    "sauber": {"full": "Kick Sauber", "series": "f1"},
    "rb": {"full": "Visa Cash App RB", "series": "f1"},
    "alphatauri": {"full": "Visa Cash App RB", "series": "f1"},
    
    # IMSA/WEC Manufacturers
    "porsche": {"full": "Porsche", "series": "imsa"},
    "porsche penske": {"full": "Porsche Penske Motorsport", "series": "imsa"},
    "cadillac": {"full": "Cadillac Racing", "series": "imsa"},
    "action express": {"full": "Action Express Racing", "series": "imsa"},
    "wayne taylor": {"full": "Wayne Taylor Racing", "series": "imsa"},
    "bmw": {"full": "BMW M Team RLL", "series": "imsa"},
    "acura": {"full": "Acura Meyer Shank", "series": "imsa"},
    "corvette": {"full": "Corvette Racing", "series": "imsa"},
    "lamborghini": {"full": "Lamborghini", "series": "imsa"},
    "toyota": {"full": "Toyota Gazoo Racing", "series": "wec"},
    "peugeot": {"full": "Peugeot TotalEnergies", "series": "wec"},
    
    # NASCAR
    "hendrick": {"full": "Hendrick Motorsports", "series": "nascar"},
    "joe gibbs": {"full": "Joe Gibbs Racing", "series": "nascar"},
    "penske": {"full": "Team Penske", "series": "nascar"},
    "trackhouse": {"full": "Trackhouse Racing", "series": "nascar"},
    
    # IndyCar
    "chip ganassi": {"full": "Chip Ganassi Racing", "series": "indycar"},
    "andretti": {"full": "Andretti Global", "series": "indycar"},
    "arrow mclaren": {"full": "Arrow McLaren", "series": "indycar"},
}

# Events/Races
EVENTS = {
    # IMSA
    "daytona": {"full": "Rolex 24 at Daytona", "series": "imsa"},
    "daytona 24": {"full": "Rolex 24 at Daytona", "series": "imsa"},
    "rolex 24": {"full": "Rolex 24 at Daytona", "series": "imsa"},
    "sebring": {"full": "12 Hours of Sebring", "series": "imsa"},
    "sebring 12": {"full": "12 Hours of Sebring", "series": "imsa"},
    "petit le mans": {"full": "Petit Le Mans", "series": "imsa"},
    "road atlanta": {"full": "Petit Le Mans", "series": "imsa"},
    "watkins glen": {"full": "Watkins Glen", "series": "imsa"},
    
    # WEC
    "le mans": {"full": "24 Hours of Le Mans", "series": "wec"},
    "24h le mans": {"full": "24 Hours of Le Mans", "series": "wec"},
    "spa": {"full": "6 Hours of Spa", "series": "wec"},
    "bahrain": {"full": "8 Hours of Bahrain", "series": "wec"},
    
    # F1
    "monaco": {"full": "Monaco Grand Prix", "series": "f1"},
    "silverstone": {"full": "British Grand Prix", "series": "f1"},
    "monza": {"full": "Italian Grand Prix", "series": "f1"},
    "suzuka": {"full": "Japanese Grand Prix", "series": "f1"},
    "spa": {"full": "Belgian Grand Prix", "series": "f1"},
    "singapore": {"full": "Singapore Grand Prix", "series": "f1"},
    "cota": {"full": "US Grand Prix", "series": "f1"},
    "austin": {"full": "US Grand Prix", "series": "f1"},
    
    # NASCAR
    "daytona 500": {"full": "Daytona 500", "series": "nascar"},
    "talladega": {"full": "Talladega", "series": "nascar"},
    "bristol": {"full": "Bristol", "series": "nascar"},
    
    # IndyCar
    "indy 500": {"full": "Indianapolis 500", "series": "indycar"},
    "indianapolis": {"full": "Indianapolis 500", "series": "indycar"},
}

# Controversy topics
CONTROVERSY_KEYWORDS = {
    "bop": "Balance of Performance",
    "balance of performance": "Balance of Performance",
    "penalty": "Race Penalty",
    "penalties": "Race Penalty",
    "stewards": "Stewards Decision",
    "protest": "Team Protest",
    "appeal": "Team Appeal",
    "collision": "On-Track Incident",
    "contact": "On-Track Incident",
    "crash": "Racing Incident",
    "safety car": "Safety Car Period",
    "red flag": "Red Flag",
    "fog": "Weather Delay",
    "rain delay": "Weather Delay",
    "delayed": "Race Delay",
}


@dataclass
class Topic:
    """Represents a trending topic."""
    name: str
    type: str  # driver, team, event, hashtag, controversy
    count: int
    sentiment_score: float
    sentiment_breakdown: Dict[str, int]
    tweet_ids: List[str]
    related_entities: List[str]
    series: Optional[str]


def extract_hashtags(text: str) -> List[str]:
    """Extract and normalize hashtags."""
    return [tag.lower() for tag in re.findall(r'#(\w+)', text)]


def extract_mentions(text: str) -> List[str]:
    """Extract @mentions."""
    return [m.lower() for m in re.findall(r'@(\w+)', text)]


def find_entities(text: str) -> Dict[str, List[Dict]]:
    """
    Find all motorsport entities in text.
    
    Returns categorized matches with metadata.
    """
    text_lower = text.lower()
    found = {
        "drivers": [],
        "teams": [],
        "events": [],
        "controversies": [],
    }
    
    # Check drivers
    for key, info in DRIVERS.items():
        # Use word boundaries to avoid partial matches
        if re.search(rf'\b{re.escape(key)}\b', text_lower):
            found["drivers"].append({
                "key": key,
                "full": info["full"],
                "team": info.get("team"),
                "series": info["series"],
            })
    
    # Check teams
    for key, info in TEAMS.items():
        if key in text_lower:
            found["teams"].append({
                "key": key,
                "full": info["full"],
                "series": info["series"],
            })
    
    # Check events
    for key, info in EVENTS.items():
        if key in text_lower:
            found["events"].append({
                "key": key,
                "full": info["full"],
                "series": info["series"],
            })
    
    # Check controversies
    for key, label in CONTROVERSY_KEYWORDS.items():
        if key in text_lower:
            found["controversies"].append({
                "key": key,
                "label": label,
            })
    
    return found


def extract_topics_v2(tweets: List[Dict]) -> List[Dict]:
    """
    Extract and rank trending topics with enhanced analysis.
    
    Returns comprehensive topic data including:
    - Sentiment breakdown per dimension
    - Related entities
    - Tweet samples
    """
    # Counters
    hashtag_data = defaultdict(lambda: {
        "count": 0,
        "sentiments": [],
        "tweet_ids": [],
        "engagements": [],
    })
    
    entity_data = defaultdict(lambda: {
        "count": 0,
        "sentiments": [],
        "tweet_ids": [],
        "engagements": [],
        "type": None,
        "full_name": None,
        "series": None,
    })
    
    for tweet in tweets:
        text = tweet.get("text", "")
        tweet_id = tweet.get("id", "")
        sentiment = tweet.get("sentiment", "neutral")
        engagement = tweet.get("engagement", 0)
        
        # Extract hashtags
        for tag in extract_hashtags(text):
            key = f"#{tag}"
            hashtag_data[key]["count"] += 1
            hashtag_data[key]["sentiments"].append(sentiment)
            hashtag_data[key]["tweet_ids"].append(tweet_id)
            hashtag_data[key]["engagements"].append(engagement)
        
        # Extract entities
        entities = find_entities(text)
        
        for driver in entities["drivers"]:
            key = driver["full"]
            entity_data[key]["count"] += 1
            entity_data[key]["sentiments"].append(sentiment)
            entity_data[key]["tweet_ids"].append(tweet_id)
            entity_data[key]["engagements"].append(engagement)
            entity_data[key]["type"] = "driver"
            entity_data[key]["full_name"] = driver["full"]
            entity_data[key]["series"] = driver["series"]
        
        for team in entities["teams"]:
            key = team["full"]
            entity_data[key]["count"] += 1
            entity_data[key]["sentiments"].append(sentiment)
            entity_data[key]["tweet_ids"].append(tweet_id)
            entity_data[key]["engagements"].append(engagement)
            entity_data[key]["type"] = "team"
            entity_data[key]["full_name"] = team["full"]
            entity_data[key]["series"] = team["series"]
        
        for event in entities["events"]:
            key = event["full"]
            entity_data[key]["count"] += 1
            entity_data[key]["sentiments"].append(sentiment)
            entity_data[key]["tweet_ids"].append(tweet_id)
            entity_data[key]["engagements"].append(engagement)
            entity_data[key]["type"] = "event"
            entity_data[key]["full_name"] = event["full"]
            entity_data[key]["series"] = event["series"]
        
        for controversy in entities["controversies"]:
            key = controversy["label"]
            entity_data[key]["count"] += 1
            entity_data[key]["sentiments"].append(sentiment)
            entity_data[key]["tweet_ids"].append(tweet_id)
            entity_data[key]["engagements"].append(engagement)
            entity_data[key]["type"] = "controversy"
            entity_data[key]["full_name"] = controversy["label"]
    
    # Build topic list
    topics = []
    
    # Add hashtags
    for tag, data in hashtag_data.items():
        if data["count"] < 2:  # Filter low-count
            continue
        
        sentiments = data["sentiments"]
        pos = sentiments.count("positive")
        neg = sentiments.count("negative")
        
        topics.append({
            "topic": tag,
            "type": "hashtag",
            "count": data["count"],
            "sentiment": "positive" if pos > neg else ("negative" if neg > pos else "neutral"),
            "sentimentScore": round((pos - neg) / len(sentiments) * 100) if sentiments else 0,
            "sentimentBreakdown": {
                "positive": pos,
                "negative": neg,
                "neutral": sentiments.count("neutral"),
            },
            "avgEngagement": round(sum(data["engagements"]) / len(data["engagements"]), 1) if data["engagements"] else 0,
            "tweetIds": data["tweet_ids"][:5],
            "series": None,
        })
    
    # Add entities
    for name, data in entity_data.items():
        if data["count"] < 2:
            continue
        
        sentiments = data["sentiments"]
        pos = sentiments.count("positive")
        neg = sentiments.count("negative")
        
        topics.append({
            "topic": name,
            "type": data["type"],
            "count": data["count"],
            "sentiment": "positive" if pos > neg else ("negative" if neg > pos else "neutral"),
            "sentimentScore": round((pos - neg) / len(sentiments) * 100) if sentiments else 0,
            "sentimentBreakdown": {
                "positive": pos,
                "negative": neg,
                "neutral": sentiments.count("neutral"),
            },
            "avgEngagement": round(sum(data["engagements"]) / len(data["engagements"]), 1) if data["engagements"] else 0,
            "tweetIds": data["tweet_ids"][:5],
            "series": data["series"],
        })
    
    # Sort by count * engagement factor
    topics.sort(key=lambda t: t["count"] * (1 + t["avgEngagement"] / 100), reverse=True)
    
    # Deduplicate similar topics
    seen = set()
    unique_topics = []
    for topic in topics:
        # Normalize for dedup
        key = topic["topic"].lower().replace("#", "").replace(" ", "")
        if key not in seen:
            seen.add(key)
            unique_topics.append(topic)
    
    return unique_topics[:20]


# Backward compatibility
def extract_topics(tweets: List[Dict]) -> List[Dict]:
    """Wrapper for backward compatibility."""
    return extract_topics_v2(tweets)


def get_topic_keywords(topic: str) -> List[str]:
    """Get related keywords for article matching."""
    topic_lower = topic.lower().replace("#", "")
    keywords = [topic_lower]
    
    # Driver variations
    for key, info in DRIVERS.items():
        if key == topic_lower or info["full"].lower() == topic_lower:
            keywords.append(key)
            keywords.append(info["full"].lower())
            if info.get("team"):
                keywords.append(info["team"].lower())
    
    # Event variations
    if "daytona" in topic_lower:
        keywords.extend(["rolex 24", "daytona", "24 hours", "imsa"])
    elif "le mans" in topic_lower or "lemans" in topic_lower:
        keywords.extend(["le mans", "24h", "wec", "endurance"])
    elif "bop" in topic_lower:
        keywords.extend(["balance of performance", "performance balance", "sandbagging"])
    
    return list(set(keywords))
