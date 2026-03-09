"""Modules 8 & 9: Signal Decision Engine + Fallback Decision Layer.

Scoring system
--------------
  Bullish:
    tick momentum bullish  → +2
    EMA20 > EMA50          → +1
    price_now > price_start → +1

  Bearish:
    tick momentum bearish  → −2
    EMA20 < EMA50          → −1
    price_now < price_start → −1

Decision logic:
  score ≥ +3 → CALL
  score ≤ −3 → PUT
  otherwise  → fallback (price direction)
"""

from __future__ import annotations

import logging
from enum import Enum

from src.momentum_analyzer import MomentumBias
from src.trend_engine import TrendDirection

logger = logging.getLogger(__name__)

CALL_THRESHOLD = 3
PUT_THRESHOLD = -3


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
    ) -> tuple[Signal, int, bool]:
        """Return ``(signal, score, used_fallback)``.

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

        # --- Decision ---------------------------------------------------
        used_fallback = False
        if score >= CALL_THRESHOLD:
            signal = Signal.CALL
        elif score <= PUT_THRESHOLD:
            signal = Signal.PUT
        else:
            # Fallback layer – always produce a signal.
            signal = self._fallback(price_start, price_now)
            used_fallback = True

        logger.info(
            "Decision: score=%+d signal=%s fallback=%s",
            score,
            signal.value,
            used_fallback,
        )
        return signal, score, used_fallback

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
