"""Module 5: Tick Aggregation Engine.

Collects and pre-processes tick data within a window, tracking the window's
opening price and providing aggregated statistics used by the analysis modules.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class TickAggregator:
    """Aggregates tick data for a single 15-minute window."""

    def __init__(self) -> None:
        self._price_start: float | None = None
        self._price_now: float | None = None
        self._tick_count: int = 0
        self._valid_prices: list[float] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_tick(self, price: float, is_valid: bool) -> None:
        """Process a single tick.

        Parameters
        ----------
        price:
            The tick price.
        is_valid:
            ``False`` if the anti-spike filter flagged this tick.
        """
        self._tick_count += 1

        if self._price_start is None:
            self._price_start = price

        self._price_now = price

        if is_valid:
            self._valid_prices.append(price)

    @property
    def price_start(self) -> float | None:
        """Price at the beginning of the window."""
        return self._price_start

    @property
    def price_now(self) -> float | None:
        """Most recent price in the window."""
        return self._price_now

    @property
    def tick_count(self) -> int:
        """Total ticks received in this window (valid + spike)."""
        return self._tick_count

    @property
    def valid_prices(self) -> list[float]:
        """Chronological list of prices that passed the spike filter."""
        return list(self._valid_prices)

    def reset(self) -> None:
        """Clear all state for a new window."""
        self._price_start = None
        self._price_now = None
        self._tick_count = 0
        self._valid_prices.clear()
        logger.debug("TickAggregator reset.")
