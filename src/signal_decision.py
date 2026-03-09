"""Modules 8 & 9: Signal Decision Engine + Fallback Decision Layer.

Scoring system
--------------
  Bullish:
    tick momentum bullish  → +2
    EMA20 > EMA50          → +1
    price_now > price_start → +1
    RSI < 30 (oversold)    → +1

  Bearish:
    tick momentum bearish  → −2
    EMA20 < EMA50          → −1
    price_now < price_start → −1
    RSI > 70 (overbought)  → −1

Decision logic:
  score ≥ +2 → CALL  (lowered from +3 for more strong signals)
  score ≤ −2 → PUT   (lowered from -3 for more strong signals)
  otherwise  → fallback (price direction)

Confidence level:
  HIGH   : |score| ≥ 4, no fallback
  MEDIUM : |score| ≥ 2, no fallback
  LOW    : fallback used
"""

from __future__ import annotations

import logging
from enum import Enum

from src.momentum_analyzer import MomentumBias
from src.trend_engine import TrendDirection
from src.rsi import RSIBias

logger = logging.getLogger(__name__)

CALL_THRESHOLD = 2
PUT_THRESHOLD = -2


class Signal(Enum):
    """Trading signal."""

    CALL = "CALL"
    PUT = "PUT"


class Confidence(Enum):
    """Signal confidence level."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SignalDecisionEngine:
    """Produces a deterministic CALL / PUT signal using the scoring system."""

    def evaluate(
        self,
        momentum_bias: MomentumBias,
        trend_direction: TrendDirection,
        price_start: float | None,
        price_now: float | None,
        rsi_bias: RSIBias = RSIBias.NEUTRAL,
    ) -> tuple[Signal, int, bool, Confidence]:
        """Return ``(signal, score, used_fallback, confidence)``.

        Parameters
        ----------
        momentum_bias:
            Output of :class:`MomentumAnalyzer`.
        trend_direction:
            Output of :class:`TrendEngine`.
        price_start:
            Window opening price.
        price_now:
            Current price.
        rsi_bias:
            Output of :func:`compute_rsi`.
        """
        score = 0

        # --- Momentum contribution (weight 2) --------------------------
        if momentum_bias is MomentumBias.BULLISH:
            score += 2
        elif momentum_bias is MomentumBias.BEARISH:
            score -= 2

        # --- Trend contribution (weight 1) -----------------------------
        if trend_direction is TrendDirection.BULLISH:
            score += 1
        elif trend_direction is TrendDirection.BEARISH:
            score -= 1

        # --- Window price direction (weight 1) -------------------------
        if price_start is not None and price_now is not None:
            if price_now > price_start:
                score += 1
            elif price_now < price_start:
                score -= 1

        # --- RSI contribution (weight 1) -------------------------------
        if rsi_bias is RSIBias.BULLISH:
            score += 1
        elif rsi_bias is RSIBias.BEARISH:
            score -= 1

        # --- Decision ---------------------------------------------------
        used_fallback = False
        if score >= CALL_THRESHOLD:
            signal = Signal.CALL
        elif score <= PUT_THRESHOLD:
            signal = Signal.PUT
        else:
            signal = self._fallback(price_start, price_now)
            used_fallback = True

        # --- Confidence level -------------------------------------------
        abs_score = abs(score)
        if used_fallback:
            confidence = Confidence.LOW
        elif abs_score >= 4:
            confidence = Confidence.HIGH
        else:
            confidence = Confidence.MEDIUM

        logger.info(
            "Decision: score=%+d signal=%s fallback=%s confidence=%s",
            score,
            signal.value,
            used_fallback,
            confidence.value,
        )
        return signal, score, used_fallback, confidence

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback(price_start: float | None, price_now: float | None) -> Signal:
        """Fallback Decision Layer.

        If the score is inconclusive, decide based on raw price direction:
          price_now > price_start → CALL
          otherwise               → PUT
        """
        if price_start is not None and price_now is not None and price_now > price_start:
            return Signal.CALL
        return Signal.PUT
