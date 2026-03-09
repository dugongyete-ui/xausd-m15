"""RSI (Relative Strength Index) Indicator Module.

Computes the RSI from a tick buffer to provide an additional signal
for overbought/oversold conditions.

Interpretation
--------------
  RSI > 70 → overbought (bearish signal)
  RSI < 30 → oversold (bullish signal)
  30 <= RSI <= 70 → neutral
"""

from __future__ import annotations

import logging
from enum import Enum

from src.tick_buffer import TickBuffer

logger = logging.getLogger(__name__)

DEFAULT_RSI_PERIOD = 14
OVERBOUGHT_THRESHOLD = 70.0
OVERSOLD_THRESHOLD = 30.0


class RSISignal(Enum):
    """Signal derived from RSI analysis."""

    OVERBOUGHT = "overbought"
    OVERSOLD = "oversold"
    NEUTRAL = "neutral"


class RSIIndicator:
    """Computes RSI from a :class:`TickBuffer`."""

    def __init__(
        self,
        buffer: TickBuffer,
        period: int = DEFAULT_RSI_PERIOD,
        overbought: float = OVERBOUGHT_THRESHOLD,
        oversold: float = OVERSOLD_THRESHOLD,
    ) -> None:
        self._buffer = buffer
        self._period = period
        self._overbought = overbought
        self._oversold = oversold

    def compute(self) -> tuple[float | None, RSISignal]:
        """Return ``(rsi_value, signal)``.

        Returns ``(None, NEUTRAL)`` when the buffer has fewer data points
        than the RSI period + 1.
        """
        prices = self._buffer.prices
        if len(prices) < self._period + 1:
            return None, RSISignal.NEUTRAL

        # Calculate price changes
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

        # Use exponential moving average method for RSI
        # Start with SMA for the first period
        avg_gain = sum(gains[:self._period]) / self._period
        avg_loss = sum(losses[:self._period]) / self._period

        # Apply smoothing for remaining data points
        for i in range(self._period, len(gains)):
            avg_gain = (avg_gain * (self._period - 1) + gains[i]) / self._period
            avg_loss = (avg_loss * (self._period - 1) + losses[i]) / self._period

        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        # Determine signal
        if rsi >= self._overbought:
            signal = RSISignal.OVERBOUGHT
        elif rsi <= self._oversold:
            signal = RSISignal.OVERSOLD
        else:
            signal = RSISignal.NEUTRAL

        logger.debug(
            "RSI: value=%.2f signal=%s (period=%d)",
            rsi,
            signal.value,
            self._period,
        )
        return rsi, signal
