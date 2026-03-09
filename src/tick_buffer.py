"""Module 2: Tick Buffer Manager.

Maintains a rolling buffer of the most recent 120 ticks for micro-momentum
and indicator calculations.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

BUFFER_SIZE = 120


@dataclass(slots=True)
class Tick:
    """A single price tick."""

    price: float
    epoch: int


class TickBuffer:
    """Fixed-size rolling buffer of :class:`Tick` objects."""

    def __init__(self, max_size: int = BUFFER_SIZE) -> None:
        self._buffer: deque[Tick] = deque(maxlen=max_size)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, price: float, epoch: int) -> None:
        """Add a tick to the buffer, evicting the oldest if full."""
        self._buffer.append(Tick(price=price, epoch=epoch))

    @property
    def prices(self) -> list[float]:
        """Return all buffered prices in chronological order."""
        return [t.price for t in self._buffer]

    @property
    def ticks(self) -> list[Tick]:
        """Return a snapshot of all buffered ticks."""
        return list(self._buffer)

    @property
    def latest_price(self) -> float | None:
        """Return the most recent price, or ``None`` if buffer is empty."""
        if self._buffer:
            return self._buffer[-1].price
        return None

    @property
    def latest_epoch(self) -> int | None:
        """Return the most recent epoch, or ``None`` if buffer is empty."""
        if self._buffer:
            return self._buffer[-1].epoch
        return None

    def __len__(self) -> int:
        return len(self._buffer)

    def clear(self) -> None:
        """Remove all ticks from the buffer."""
        self._buffer.clear()
