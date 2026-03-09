"""Module 3: Anti-Spike Filter.

Gold frequently produces sudden price spikes that can distort signal
calculations.  This filter detects and flags ticks whose price change
relative to the previous tick exceeds a configurable threshold.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Default spike threshold: 0.25 % price change between consecutive ticks.
DEFAULT_SPIKE_THRESHOLD_PCT = 0.25
# Minimum number of *stable* ticks required after a spike before we resume
# normal processing.
STABILISATION_TICKS = 3


class AntiSpikeFilter:
    """Detects and suppresses anomalous price spikes in tick data."""

    def __init__(
        self,
        threshold_pct: float = DEFAULT_SPIKE_THRESHOLD_PCT,
        stabilisation_ticks: int = STABILISATION_TICKS,
    ) -> None:
        self._threshold_pct = threshold_pct
        self._stabilisation_ticks = stabilisation_ticks
        self._last_valid_price: float | None = None
        self._stable_count: int = 0
        self._in_spike: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, price: float) -> bool:
        """Return ``True`` if *price* is considered valid (not a spike).

        If a spike is detected the tick should be **excluded** from momentum
        and indicator calculations.
        """
        if self._last_valid_price is None:
            # First tick – always accept.
            self._last_valid_price = price
            return True

        pct_change = abs(price - self._last_valid_price) / self._last_valid_price * 100.0

        if pct_change > self._threshold_pct:
            # Spike detected.
            if not self._in_spike:
                logger.warning(
                    "Spike detected: %.2f → %.2f (%.3f%%). Ignoring tick.",
                    self._last_valid_price,
                    price,
                    pct_change,
                )
            self._in_spike = True
            self._stable_count = 0
            return False

        if self._in_spike:
            # Price has returned to a normal range – start stabilisation.
            self._stable_count += 1
            if self._stable_count >= self._stabilisation_ticks:
                logger.info("Price stabilised after spike. Resuming normal processing.")
                self._in_spike = False
                self._stable_count = 0
                self._last_valid_price = price
                return True
            # Still stabilising – accept tick but keep monitoring.
            self._last_valid_price = price
            return True

        # Normal tick.
        self._last_valid_price = price
        return True

    def reset(self) -> None:
        """Reset internal state (called on window reset)."""
        self._last_valid_price = None
        self._stable_count = 0
        self._in_spike = False
