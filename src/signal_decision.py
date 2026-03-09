"""Modules 8 & 9: Signal Decision Engine + Fallback Decision Layer.

Scoring system
--------------
  Bullish:
    tick momentum bullish   -> +2
    EMA20 > EMA50           -> +1
    price_now > price_start -> +1
    RSI oversold (<30)      -> +1

  Bearish:
    tick momentum bearish   -> -2
    EMA20 < EMA50           -> -1
    price_now < price_start -> -1
    RSI overbought (>70)    -> -1

Decision logic:
  score >= +2 -> CALL
  score <= -2 -> PUT
  otherwise   -> fallback (price direction)

Confidence level:
  Based on absolute score relative to maximum possible (+/-5).
"""

from __future__ import annotations

import logging
from enum import Enum

from src.momentum_analyzer import MomentumBias
from src.rsi import RSISignal
from src.trend_engine import TrendDirection

logger = logging.getLogger(__name__)

CALL_THRESHOLD = 2
PUT_THRESHOLD = -2
MAX_SCORE = 5  # Maximum possible absolute score


class Signal(Enum):
    """Trading signal."""

    CALL = "CALL"
    PUT = "PUT"


class SignalDecisionEngine:
    """Produces a deterministic CALL / PUT signal using the scoring system."""

    def evaluate(
        self,
        momentum_bias: MomentumBias,
        trend_direction: TrendDirection,
        price_start: float | None,
        price_now: float | None,
        rsi_signal: RSISignal = RSISignal.NEUTRAL,
    ) -> tuple[Signal, int, bool, float]:
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
        rsi_signal:
            Output of :class:`RSIIndicator`.
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
        if rsi_signal is RSISignal.OVERSOLD:
            score += 1  # Oversold -> bullish reversal expected
        elif rsi_signal is RSISignal.OVERBOUGHT:
            score -= 1  # Overbought -> bearish reversal expected

        # --- Decision ---------------------------------------------------
        used_fallback = False
        if score >= CALL_THRESHOLD:
            signal = Signal.CALL
        elif score <= PUT_THRESHOLD:
            signal = Signal.PUT
        else:
            # Fallback layer - always produce a signal.
            signal = self._fallback(price_start, price_now)
            used_fallback = True

        # --- Confidence -------------------------------------------------
        confidence = self._compute_confidence(score, used_fallback)

        logger.info(
            "Decision: score=%+d signal=%s fallback=%s confidence=%.0f%%",
            score,
            signal.value,
            used_fallback,
            confidence,
        )
        return signal, score, used_fallback, confidence

    @staticmethod
    def _compute_confidence(score: int, used_fallback: bool) -> float:
        """Compute signal confidence as a percentage (0-100).

        Confidence is based on how strong the score is relative to the
        maximum possible score.  Fallback signals get a reduced
        confidence.
        """
        if used_fallback:
            # Fallback signals have low confidence (20-35%)
            return 20.0 + abs(score) / MAX_SCORE * 15.0
        # Non-fallback: base 50% + up to 50% based on score strength
        return 50.0 + (abs(score) / MAX_SCORE) * 50.0

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
