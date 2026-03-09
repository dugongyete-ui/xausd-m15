"""Module 6: Momentum Analyzer.

Computes micro-momentum from the tick buffer by counting upticks versus
downticks and deriving a momentum ratio.

Interpretation
--------------
  momentum_ratio > 0.60 → bullish micro momentum
  momentum_ratio < 0.40 → bearish micro momentum
"""

from __future__ import annotations

import logging
from enum import Enum

from src.tick_buffer import TickBuffer

logger = logging.getLogger(__name__)

BULLISH_THRESHOLD = 0.60
BEARISH_THRESHOLD = 0.40


class MomentumBias(Enum):
    """Directional bias from momentum analysis."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class MomentumAnalyzer:
    """Analyses tick-level momentum from a :class:`TickBuffer`."""

    def __init__(self, buffer: TickBuffer) -> None:
        self._buffer = buffer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self) -> tuple[float, MomentumBias]:
        """Return ``(momentum_ratio, bias)``.

        The *momentum_ratio* is defined as ``uptick_count / total_ticks``
        where an *uptick* is a tick whose price is strictly greater than
        the preceding tick.

        Returns ``(0.5, NEUTRAL)`` when the buffer has fewer than 2 ticks.
        """
        prices = self._buffer.prices
        if len(prices) < 2:
            return 0.5, MomentumBias.NEUTRAL

        upticks = 0
        downticks = 0
        for i in range(1, len(prices)):
            if prices[i] > prices[i - 1]:
                upticks += 1
            elif prices[i] < prices[i - 1]:
                downticks += 1
            # equal prices are ignored (neither up nor down)

        total = upticks + downticks
        if total == 0:
            return 0.5, MomentumBias.NEUTRAL

        ratio = upticks / total

        if ratio > BULLISH_THRESHOLD:
            bias = MomentumBias.BULLISH
        elif ratio < BEARISH_THRESHOLD:
            bias = MomentumBias.BEARISH
        else:
            bias = MomentumBias.NEUTRAL

        logger.debug(
            "Momentum: upticks=%d downticks=%d ratio=%.3f bias=%s",
            upticks,
            downticks,
            ratio,
            bias.value,
        )
        return ratio, bias
