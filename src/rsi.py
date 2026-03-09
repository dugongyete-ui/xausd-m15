"""RSI (Relative Strength Index) indicator module.

Computes the 14-period RSI from tick prices.

Interpretation
--------------
  RSI > 70  → overbought (bearish bias)  → -1 contribution
  RSI < 30  → oversold  (bullish bias)   → +1 contribution
  30–70     → neutral                    →  0 contribution
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)

RSI_PERIOD = 14
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0


class RSIBias(Enum):
    """Signal bias derived from RSI."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


def compute_rsi(prices: list[float], period: int = RSI_PERIOD) -> tuple[float | None, RSIBias]:
    """Compute RSI and return ``(rsi_value, bias)``.

    Returns ``(None, NEUTRAL)`` when there are insufficient data points.
    """
    if len(prices) < period + 1:
        return None, RSIBias.NEUTRAL

    gains: list[float] = []
    losses: list[float] = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        elif change < 0:
            gains.append(0.0)
            losses.append(abs(change))
        else:
            gains.append(0.0)
            losses.append(0.0)

    if len(gains) < period:
        return None, RSIBias.NEUTRAL

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

    if rsi > RSI_OVERBOUGHT:
        bias = RSIBias.BEARISH
    elif rsi < RSI_OVERSOLD:
        bias = RSIBias.BULLISH
    else:
        bias = RSIBias.NEUTRAL

    logger.debug("RSI(%d)=%.2f bias=%s", period, rsi, bias.value)
    return rsi, bias
