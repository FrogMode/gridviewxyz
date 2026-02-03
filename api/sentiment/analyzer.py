"""Advanced Sentiment Analyzer for Motorsport.

Multi-dimensional sentiment scoring with motorsport-specific lexicons.
Detects: excitement, controversy, disappointment, celebration.
"""
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
from enum import Enum


class SentimentDimension(Enum):
    """Multi-dimensional sentiment categories."""
    EXCITEMENT = "excitement"      # Thrilling moments, close racing
    CONTROVERSY = "controversy"    # BoP debates, penalties, protests  
    DISAPPOINTMENT = "disappointment"  # DNFs, crashes, poor results
    CELEBRATION = "celebration"    # Wins, podiums, records
    INFORMATIONAL = "informational"  # News, facts, neutral reporting


@dataclass
class SentimentScore:
    """Detailed sentiment breakdown for a piece of text."""
    overall: str  # positive, negative, neutral
    confidence: float  # 0.0 - 1.0
    dimensions: Dict[str, float]  # scores per dimension (0.0 - 1.0)
    dominant: str  # highest scoring dimension
    keywords_found: List[str]  # matched keywords
    emoji_sentiment: float  # -1.0 to 1.0


# Motorsport-specific lexicons
EXCITEMENT_LEXICON = {
    # High excitement
    "incredible": 1.0, "unbelievable": 1.0, "amazing": 0.9, "insane": 0.9,
    "thrilling": 0.9, "edge of seat": 1.0, "battle": 0.7, "wheel to wheel": 1.0,
    "side by side": 0.8, "photo finish": 1.0, "last lap": 0.8, "final lap": 0.8,
    "nail biter": 0.9, "epic": 0.8, "legendary": 0.9, "historic": 0.8,
    "drama": 0.7, "crazy": 0.7, "wild": 0.7, "chaos": 0.8, "madness": 0.8,
    "wow": 0.7, "omg": 0.7, "holy": 0.6, "goosebumps": 0.9,
    "passing": 0.5, "overtake": 0.6, "dive bomb": 0.7, "send it": 0.7,
    "full send": 0.8, "sideways": 0.6, "drifting": 0.5, "save": 0.6,
    # Emoji
    "🔥": 0.8, "💨": 0.6, "😱": 0.8, "🤯": 0.9, "⚡": 0.6,
}

CONTROVERSY_LEXICON = {
    # Balance of Performance
    "bop": 0.8, "balance of performance": 0.9, "sandbagging": 0.9,
    "unfair": 0.9, "rigged": 1.0, "fixed": 0.9, "bs": 0.7, "bullshit": 0.8,
    # Penalties/Stewards
    "penalty": 0.6, "stewards": 0.6, "investigation": 0.6, "protest": 0.8,
    "appeal": 0.7, "decision": 0.4, "ruling": 0.5, "controversial": 0.9,
    "questionable": 0.7, "inconsistent": 0.8,
    # Conflicts
    "collision": 0.6, "contact": 0.5, "incident": 0.5, "pushed off": 0.7,
    "dirty": 0.8, "unsportsmanlike": 0.9, "dangerous": 0.7,
    "blame": 0.6, "fault": 0.5, "robbed": 0.9,
    # Criticism
    "joke": 0.7, "embarrassing": 0.7, "disgrace": 0.9, "farce": 0.9,
    "shameful": 0.9, "unacceptable": 0.8, "outrageous": 0.9,
    # Emoji
    "😡": 0.8, "🤬": 0.9, "💢": 0.7, "🙄": 0.6, "🤡": 0.8,
}

DISAPPOINTMENT_LEXICON = {
    # Mechanical
    "dnf": 0.8, "retired": 0.6, "out": 0.4, "mechanical": 0.5,
    "engine failure": 0.8, "gearbox": 0.6, "problem": 0.4, "issue": 0.3,
    "broke": 0.6, "broken": 0.6, "retired": 0.6,
    # Crashes
    "crash": 0.7, "wreck": 0.8, "accident": 0.6, "totaled": 0.8,
    "destroyed": 0.7, "in the wall": 0.8, "off track": 0.5, "barrier": 0.6,
    # Performance
    "slow": 0.4, "struggled": 0.5, "poor": 0.5, "terrible": 0.7,
    "disaster": 0.8, "nightmare": 0.8, "disappointing": 0.7,
    "heartbreaking": 0.9, "gutted": 0.8, "devastated": 0.9,
    # Weather delays
    "delay": 0.4, "red flag": 0.3, "yellow": 0.2, "safety car": 0.3,
    "fog": 0.4, "rain delay": 0.5, "suspended": 0.5, "stopped": 0.4,
    # Emoji
    "😢": 0.7, "😭": 0.8, "💔": 0.8, "😔": 0.6, "😞": 0.6,
}

CELEBRATION_LEXICON = {
    # Victory
    "win": 0.8, "winner": 0.9, "victory": 0.9, "won": 0.8, "wins": 0.8,
    "champion": 1.0, "championship": 0.9, "title": 0.7,
    # Podium
    "podium": 0.8, "p1": 0.9, "p2": 0.7, "p3": 0.6, "first": 0.6,
    "1st": 0.9, "2nd": 0.7, "3rd": 0.6,
    # Achievement
    "record": 0.8, "historic": 0.7, "milestone": 0.7, "debut": 0.6,
    "pole": 0.7, "pole position": 0.8, "fastest lap": 0.7,
    # Praise
    "congrats": 0.8, "congratulations": 0.9, "bravo": 0.8, "well done": 0.8,
    "incredible": 0.7, "amazing": 0.7, "brilliant": 0.8, "masterclass": 0.9,
    "dominant": 0.7, "flawless": 0.9, "perfect": 0.8,
    "legend": 0.8, "goat": 0.9, "best": 0.6, "king": 0.7,
    # Emoji
    "🏆": 1.0, "🥇": 1.0, "🥈": 0.8, "🥉": 0.7, "🎉": 0.8,
    "🙌": 0.7, "👏": 0.7, "💪": 0.6, "❤️": 0.5, "🔥": 0.5,
    "✅": 0.5, "🏁": 0.6,
}

INFORMATIONAL_MARKERS = {
    "report": 0.7, "news": 0.7, "update": 0.6, "announced": 0.6,
    "confirmed": 0.6, "official": 0.7, "press release": 0.8,
    "according to": 0.7, "sources say": 0.7, "breaking": 0.6,
    "entry list": 0.7, "schedule": 0.6, "lineup": 0.6,
    "📰": 0.6, "📢": 0.5, "ℹ️": 0.7,
}


def _calculate_dimension_score(
    text: str,
    lexicon: Dict[str, float]
) -> Tuple[float, List[str]]:
    """
    Calculate score for a single dimension.
    
    Returns:
        (score between 0-1, list of matched keywords)
    """
    text_lower = text.lower()
    total_score = 0.0
    matches = []
    
    for term, weight in lexicon.items():
        # Check for term in text
        if term in text_lower:
            total_score += weight
            matches.append(term)
    
    # Normalize score (cap at 1.0)
    normalized = min(total_score / 3.0, 1.0)  # 3 strong matches = max
    
    return normalized, matches


def _calculate_emoji_sentiment(text: str) -> float:
    """
    Calculate sentiment from emoji alone.
    
    Returns:
        Score from -1.0 (negative) to 1.0 (positive)
    """
    positive_emoji = ["🔥", "🏆", "🥇", "🎉", "🙌", "👏", "💪", "❤️", "✅", "🏁", "💨", "⚡"]
    negative_emoji = ["😢", "😭", "💔", "😔", "😞", "😡", "🤬", "💢", "🙄", "🤡"]
    neutral_emoji = ["😱", "🤯", "📰", "📢", "ℹ️"]
    
    pos = sum(1 for e in positive_emoji if e in text)
    neg = sum(1 for e in negative_emoji if e in text)
    
    if pos + neg == 0:
        return 0.0
    
    return (pos - neg) / (pos + neg)


def analyze_sentiment(text: str) -> SentimentScore:
    """
    Perform multi-dimensional sentiment analysis.
    
    Args:
        text: Tweet text or any text content
    
    Returns:
        SentimentScore with detailed breakdown
    """
    # Calculate each dimension
    excitement, exc_matches = _calculate_dimension_score(text, EXCITEMENT_LEXICON)
    controversy, con_matches = _calculate_dimension_score(text, CONTROVERSY_LEXICON)
    disappointment, dis_matches = _calculate_dimension_score(text, DISAPPOINTMENT_LEXICON)
    celebration, cel_matches = _calculate_dimension_score(text, CELEBRATION_LEXICON)
    informational, inf_matches = _calculate_dimension_score(text, INFORMATIONAL_MARKERS)
    
    dimensions = {
        SentimentDimension.EXCITEMENT.value: round(excitement, 3),
        SentimentDimension.CONTROVERSY.value: round(controversy, 3),
        SentimentDimension.DISAPPOINTMENT.value: round(disappointment, 3),
        SentimentDimension.CELEBRATION.value: round(celebration, 3),
        SentimentDimension.INFORMATIONAL.value: round(informational, 3),
    }
    
    # Find dominant dimension
    if max(dimensions.values()) == 0:
        dominant = SentimentDimension.INFORMATIONAL.value
    else:
        dominant = max(dimensions, key=dimensions.get)
    
    # Calculate overall sentiment
    positive_score = excitement * 0.3 + celebration * 0.7
    negative_score = controversy * 0.5 + disappointment * 0.5
    
    if positive_score > negative_score + 0.1:
        overall = "positive"
    elif negative_score > positive_score + 0.1:
        overall = "negative"
    else:
        overall = "neutral"
    
    # Confidence based on total matches
    all_matches = exc_matches + con_matches + dis_matches + cel_matches + inf_matches
    confidence = min(len(set(all_matches)) / 5.0, 1.0)
    
    # Emoji sentiment
    emoji_sent = _calculate_emoji_sentiment(text)
    
    return SentimentScore(
        overall=overall,
        confidence=round(confidence, 3),
        dimensions=dimensions,
        dominant=dominant,
        keywords_found=list(set(all_matches))[:10],
        emoji_sentiment=round(emoji_sent, 3),
    )


def score_to_dict(score: SentimentScore) -> Dict:
    """Convert SentimentScore to JSON-serializable dict."""
    return asdict(score)


def get_sentiment_label(score: SentimentScore) -> str:
    """
    Get a human-readable sentiment label.
    
    Examples: "🔥 Exciting!", "😡 Controversial", "🏆 Celebration"
    """
    labels = {
        SentimentDimension.EXCITEMENT.value: ("🔥", "Exciting"),
        SentimentDimension.CONTROVERSY.value: ("😡", "Controversial"),
        SentimentDimension.DISAPPOINTMENT.value: ("😢", "Disappointing"),
        SentimentDimension.CELEBRATION.value: ("🏆", "Celebration"),
        SentimentDimension.INFORMATIONAL.value: ("📰", "News"),
    }
    
    emoji, label = labels.get(score.dominant, ("📰", "News"))
    
    # Add intensity
    max_score = max(score.dimensions.values())
    if max_score > 0.7:
        return f"{emoji} {label}!"
    elif max_score > 0.4:
        return f"{emoji} {label}"
    else:
        return f"📰 News"


def detect_controversy_spike(tweets: List[Dict]) -> Optional[Dict]:
    """
    Detect if there's a controversy spike in the tweets.
    
    Returns details about the controversy if detected.
    """
    controversy_tweets = []
    
    for tweet in tweets:
        text = tweet.get("text", "")
        score = analyze_sentiment(text)
        
        if score.dimensions.get("controversy", 0) > 0.5:
            controversy_tweets.append({
                "tweet": tweet,
                "score": score.dimensions["controversy"],
            })
    
    # Spike = more than 20% of tweets are controversial
    if len(controversy_tweets) >= len(tweets) * 0.2 and len(controversy_tweets) >= 3:
        # Find the most controversial topic
        topics = {}
        for ct in controversy_tweets:
            text = ct["tweet"].get("text", "").lower()
            for keyword in ["bop", "penalty", "stewards", "protest", "collision"]:
                if keyword in text:
                    topics[keyword] = topics.get(keyword, 0) + 1
        
        top_topic = max(topics, key=topics.get) if topics else "unknown"
        
        return {
            "detected": True,
            "controversialTweetCount": len(controversy_tweets),
            "percentage": round(len(controversy_tweets) / len(tweets) * 100, 1),
            "likelyTopic": top_topic,
            "severity": "high" if len(controversy_tweets) > len(tweets) * 0.4 else "moderate",
        }
    
    return None
