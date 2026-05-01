"""Sentiment and Macro Intelligence module."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """Result of sentiment analysis on a piece of text."""
    text: str
    compound: float  # -1.0 to 1.0
    positive: float
    negative: float
    neutral: float
    source: str = "news"


class SentimentAnalyzer:
    """
    Analyzes sentiment of news headlines, social media, and macro events.
    Uses VADER sentiment analysis under the hood.
    """

    def __init__(self) -> None:
        self.analyzer = SentimentIntensityAnalyzer()
        self.recent_sentiments: list[SentimentResult] = []

    def analyze_text(self, text: str, source: str = "news") -> SentimentResult:
        """
        Analyze a single string of text.
        Returns a SentimentResult object.
        """
        scores = self.analyzer.polarity_scores(text)
        
        result = SentimentResult(
            text=text,
            compound=scores["compound"],
            positive=scores["pos"],
            negative=scores["neg"],
            neutral=scores["neu"],
            source=source
        )
        
        self.recent_sentiments.append(result)
        # Keep only last 100 sentiments to save memory
        if len(self.recent_sentiments) > 100:
            self.recent_sentiments.pop(0)
            
        return result

    def get_aggregate_sentiment(self, window: int = 10) -> float:
        """
        Get the average compound sentiment score over the last N items.
        Returns value between -1.0 (extremely negative) and 1.0 (extremely positive).
        """
        if not self.recent_sentiments:
            return 0.0
            
        recent = self.recent_sentiments[-window:]
        total_compound = sum(r.compound for r in recent)
        return total_compound / len(recent)
        
    def evaluate_macro_bias(self) -> float:
        """
        Evaluate overall macro and sentiment bias.
        For integration with the AI/ML Predictive Layer.
        """
        # In a real system, we would query an API (like yfinance news or Twitter)
        # Here we just return the aggregate of processed items.
        return self.get_aggregate_sentiment(window=20)
