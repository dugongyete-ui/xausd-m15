"""Module 4: Window Time Engine.

Manages the 15-minute (900-second) window lifecycle with four distinct phases:

  Phase 1 -- Data Collection   (0-3 min)
  Phase 2 -- Analysis          (3-12 min, signal generated when market is ready)
  Phase 3 -- Signal Generation (brief moment when signal is emitted)
  Phase 4 -- Window Hold       (after signal generated until window end)

Windows are aligned to real clock boundaries (:00, :15, :30, :45).
Signal generation is market-driven — it fires when indicators converge,
not at a fixed time. Hard timeout at 12 minutes forces a signal if none yet.
"""

from __future__ import annotations

import enum
import logging
import time

logger = logging.getLogger(__name__)

WINDOW_DURATION = 900  # seconds
SIGNAL_TIMEOUT = 720   # 12 minutes — hard deadline for signal generation


class WindowPhase(enum.Enum):
    """Phases within a 15-minute window."""

    DATA_COLLECTION = "data_collection"  # 0 – 180 s
    ANALYSIS = "analysis"                # 180 – 720 s (market-driven)
    SIGNAL_GENERATION = "signal_generation"  # brief moment when signal fires
    HOLD = "hold"                        # after signal or 720 s+


class WindowEngine:
    """Tracks the current 15-minute window and its phase."""

    def __init__(self) -> None:
        self._window_start: float = 0.0
        self._window_index: int = 0
        self._started = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin the first window aligned to the current 15-minute clock boundary.

        For example, if the current time is 10:38:22, the window start
        is 10:30:00 and it expires at 10:45:00.
        """
        now = time.time()
        self._window_start = now - (now % WINDOW_DURATION)
        self._window_index = 1
        self._started = True
        logger.info(
            "Window #%d started (aligned). start=%.0f expiry=%.0f elapsed=%.0f",
            self._window_index,
            self._window_start,
            self._window_start + WINDOW_DURATION,
            now - self._window_start,
        )

    @property
    def elapsed(self) -> float:
        """Seconds elapsed since the current window started."""
        if not self._started:
            return 0.0
        return time.time() - self._window_start

    @property
    def phase(self) -> WindowPhase:
        """Return the current phase based on elapsed time.

        Signal generation is market-driven — the SIGNAL_GENERATION phase
        is set externally by the server when a signal is actually emitted.
        Time-based fallback: HOLD after 12 minutes.
        """
        elapsed = self.elapsed
        if elapsed < 180:
            return WindowPhase.DATA_COLLECTION
        if elapsed < SIGNAL_TIMEOUT:
            return WindowPhase.ANALYSIS
        return WindowPhase.HOLD

    @property
    def window_index(self) -> int:
        """Monotonically increasing window counter."""
        return self._window_index

    @property
    def window_start(self) -> float:
        """Epoch of the current window start."""
        return self._window_start

    @property
    def window_expiry(self) -> float:
        """Epoch of the current window end."""
        return self._window_start + WINDOW_DURATION

    def should_reset(self) -> bool:
        """Return ``True`` if the window duration has been exceeded."""
        return self._started and time.time() >= self._window_start + WINDOW_DURATION

    def reset(self) -> None:
        """Begin a new window aligned to the next 15-minute clock boundary."""
        now = time.time()
        self._window_start = now - (now % WINDOW_DURATION)
        self._window_index += 1
        logger.info(
            "Window #%d started (aligned). start=%.0f expiry=%.0f elapsed=%.0f",
            self._window_index,
            self._window_start,
            self._window_start + WINDOW_DURATION,
            now - self._window_start,
        )

    @property
    def remaining(self) -> float:
        """Seconds remaining in the current window."""
        return max(0.0, WINDOW_DURATION - self.elapsed)
