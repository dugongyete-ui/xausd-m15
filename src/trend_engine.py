"""Module 7: Trend Indicator Engine.

Calculates EMA-20 and EMA-50 from recent tick prices and determines the
prevailing trend direction.

Interpretation
--------------
  EMA20 > EMA50 → bullish trend
  EMA20 < EMA50 → bearish trend
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Trend determined by EMA crossover."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


def _compute_ema(prices: list[float], period: int) -> float | None:
    """Compute the Exponential Moving Average for *period* over *prices*.

    Returns ``None`` if there are fewer data points than *period*.
    """
    if len(prices) < period:
        return None

    multiplier = 2.0 / (period + 1)
    # Seed the EMA with the SMA of the first *period* values.
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


class TrendEngine:
    """Provides EMA-based trend analysis."""

    def __init__(self, short_period: int = 20, long_period: int = 50) -> None:
        self._short_period = short_period
        self._long_period = long_period

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self, prices: list[float]) -> tuple[float | None, float | None, TrendDirection]:
        """Return ``(ema_short, ema_long, direction)``.

        ``direction`` is :attr:`TrendDirection.NEUTRAL` when there are
        insufficient data points for either EMA.
        """
        ema_short = _compute_ema(prices, self._short_period)
        ema_long = _compute_ema(prices, self._long_period)

        if ema_short is None or ema_long is None:
            direction = TrendDirection.NEUTRAL
        elif ema_short > ema_long:
            direction = TrendDirection.BULLISH
        elif ema_short < ema_long:
            direction = TrendDirection.BEARISH
        else:
            direction = TrendDirection.NEUTRAL

        logger.debug(
            "Trend: EMA%d=%.2f  EMA%d=%.2f  direction=%s",
            self._short_period,
            ema_short or 0.0,
            self._long_period,
            ema_long or 0.0,
            direction.value,
        )
        return ema_short, ema_long, direction
