"""Topic Extractor - Extract trending topics from tweets.

Identifies drivers, teams, events, and controversies from tweet text.
"""
import re
from collections import Counter
from typing import List, Dict, Tuple

# Known motorsport entities
DRIVERS = {
    # F1
    "verstappen", "hamilton", "leclerc", "sainz", "norris", "piastri",
    "russell", "alonso", "stroll", "ocon", "gasly", "tsunoda", "bottas",
    "zhou", "magnussen", "hulkenberg", "albon", "sargeant", "ricciardo",
    "perez", "lawson", "colapinto", "bearman", "antonelli", "doohan",
    # IndyCar
    "palou", "newgarden", "power", "herta", "mclaughlin", "o'ward",
    "dixon", "ericsson", "grosjean", "rossi",
    # NASCAR
    "larson", "elliott", "busch", "hamlin", "blaney", "logano", "byron",
    "chastain", "reddick", "bell", "keselowski",
    # IMSA/WEC
    "tandy", "bamber", "vanthoor", "christensen", "bourdais", "estre",
    "nasr", "derani", "spengler", "jarvis", "mazda",
    # MotoGP
    "bagnaia", "martin", "marquez", "bastianini", "vinales", "espargaro",
    "quartararo", "binder", "miller",
}

TEAMS = {
    # F1
    "redbull", "red bull", "mercedes", "ferrari", "mclaren", "aston martin",
    "alpine", "williams", "alphatauri", "rb", "haas", "alfa romeo", "kick sauber",
    # NASCAR
    "hendrick", "joe gibbs", "penske", "trackhouse", "stewart-haas",
    # IMSA
    "chip ganassi", "action express", "wayne taylor", "cadillac", "porsche",
    "bmw", "acura", "lamborghini", "corvette", "aston martin", "ford",
    # WEC
    "toyota", "peugeot", "ferrari", "porsche penske",
}

EVENTS = {
    "daytona", "daytona 24", "rolex 24", "le mans", "24h", "sebring",
    "monaco", "monza", "spa", "silverstone", "suzuka", "cota", "austin",
    "indy 500", "indianapolis", "talladega", "daytona 500", "bathurst",
    "nurburgring", "nordschleife", "petit le mans", "road atlanta",
}

CONTROVERSIES = {
    "bop", "balance of performance", "penalty", "protest", "appeal",
    "controversy", "unfair", "rigged", "investigation", "stewards",
    "collision", "crash", "contact", "incident", "safety car", "red flag",
    "yellow flag", "fog", "rain delay", "weather",
}


def extract_hashtags(text: str) -> List[str]:
    """Extract hashtags from text."""
    return [tag.lower() for tag in re.findall(r'#(\w+)', text)]


def extract_mentions(text: str) -> List[str]:
    """Extract @mentions from text."""
    return [mention.lower() for mention in re.findall(r'@(\w+)', text)]


def find_known_entities(text: str) -> Dict[str, List[str]]:
    """Find known motorsport entities in text."""
    text_lower = text.lower()
    
    found = {
        "drivers": [],
        "teams": [],
        "events": [],
        "controversies": [],
    }
    
    for driver in DRIVERS:
        if driver in text_lower:
            found["drivers"].append(driver.title())
    
    for team in TEAMS:
        if team in text_lower:
            found["teams"].append(team.title())
    
    for event in EVENTS:
        if event in text_lower:
            found["events"].append(event.title())
    
    for controversy in CONTROVERSIES:
        if controversy in text_lower:
            found["controversies"].append(controversy.title())
    
    return found


def extract_topics(tweets: List[Dict]) -> List[Dict]:
    """
    Extract and rank trending topics from tweets.
    
    Args:
        tweets: List of tweet dicts with 'text' field
    
    Returns:
        Ranked list of topics with counts and sentiment
    """
    hashtag_counter = Counter()
    entity_counter = Counter()
    topic_sentiments: Dict[str, List[str]] = {}
    topic_tweets: Dict[str, List[str]] = {}
    
    for tweet in tweets:
        text = tweet.get("text", "")
        sentiment = tweet.get("sentiment", "neutral")
        tweet_id = tweet.get("id", "")
        
        # Extract hashtags
        hashtags = extract_hashtags(text)
        for tag in hashtags:
            hashtag_counter[f"#{tag}"] += 1
            if f"#{tag}" not in topic_sentiments:
                topic_sentiments[f"#{tag}"] = []
                topic_tweets[f"#{tag}"] = []
            topic_sentiments[f"#{tag}"].append(sentiment)
            topic_tweets[f"#{tag}"].append(tweet_id)
        
        # Extract known entities
        entities = find_known_entities(text)
        for category, items in entities.items():
            for item in items:
                entity_counter[item] += 1
                if item not in topic_sentiments:
                    topic_sentiments[item] = []
                    topic_tweets[item] = []
                topic_sentiments[item].append(sentiment)
                topic_tweets[item].append(tweet_id)
    
    # Combine and rank
    all_topics = []
    
    for topic, count in hashtag_counter.most_common(20):
        sentiments = topic_sentiments.get(topic, [])
        pos = sentiments.count("positive")
        neg = sentiments.count("negative")
        
        all_topics.append({
            "topic": topic,
            "type": "hashtag",
            "count": count,
            "sentiment": "positive" if pos > neg else ("negative" if neg > pos else "neutral"),
            "sentimentScore": round((pos - neg) / len(sentiments) * 100) if sentiments else 0,
            "tweetIds": topic_tweets.get(topic, [])[:5],
        })
    
    for topic, count in entity_counter.most_common(20):
        sentiments = topic_sentiments.get(topic, [])
        pos = sentiments.count("positive")
        neg = sentiments.count("negative")
        
        # Determine entity type
        topic_lower = topic.lower()
        if topic_lower in DRIVERS:
            entity_type = "driver"
        elif topic_lower in TEAMS:
            entity_type = "team"
        elif topic_lower in EVENTS:
            entity_type = "event"
        else:
            entity_type = "controversy"
        
        all_topics.append({
            "topic": topic,
            "type": entity_type,
            "count": count,
            "sentiment": "positive" if pos > neg else ("negative" if neg > pos else "neutral"),
            "sentimentScore": round((pos - neg) / len(sentiments) * 100) if sentiments else 0,
            "tweetIds": topic_tweets.get(topic, [])[:5],
        })
    
    # Sort by count
    all_topics.sort(key=lambda t: t["count"], reverse=True)
    
    # Deduplicate (remove hashtags if entity exists)
    seen = set()
    unique_topics = []
    for topic in all_topics:
        key = topic["topic"].lower().replace("#", "")
        if key not in seen:
            seen.add(key)
            unique_topics.append(topic)
    
    return unique_topics[:15]


def get_topic_keywords(topic: str) -> List[str]:
    """Get related keywords for a topic (for article matching)."""
    topic_lower = topic.lower().replace("#", "")
    
    keywords = [topic_lower]
    
    # Add variations
    if topic_lower == "daytona24" or topic_lower == "daytona 24":
        keywords.extend(["rolex 24", "daytona", "24 hours", "imsa"])
    elif topic_lower in ["f1", "formula1", "formula 1"]:
        keywords.extend(["formula 1", "formula one", "grand prix"])
    elif topic_lower == "bop":
        keywords.extend(["balance of performance", "performance balance"])
    elif topic_lower in DRIVERS:
        keywords.append(topic_lower)
    elif topic_lower in ["fog", "rain", "weather"]:
        keywords.extend(["delay", "conditions", "visibility"])
    
    return keywords
