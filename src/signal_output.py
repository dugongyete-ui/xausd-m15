"""Module 9: Signal Output Interface.

Formats and presents the generated signal to the console.

Output format
-------------
  PAIR:        XAUUSD
  SIGNAL:      CALL / PUT
  ENTRY PRICE: <current market price>
  EXPIRY TIME: <end of current 15-minute window>
"""

from __future__ import annotations

import datetime
import logging

from src.signal_decision import Signal

logger = logging.getLogger(__name__)


class SignalOutput:
    """Formats and emits trading signals."""

    PAIR = "XAUUSD"

    def emit(
        self,
        signal: Signal,
        entry_price: float,
        expiry_epoch: float,
        window_index: int,
        score: int,
        used_fallback: bool,
    ) -> None:
        """Print the signal to stdout and log it."""
        expiry_dt = datetime.datetime.fromtimestamp(expiry_epoch, tz=datetime.timezone.utc)
        now_dt = datetime.datetime.now(tz=datetime.timezone.utc)

        border = "=" * 52
        lines = [
            "",
            border,
            f"  SIGNAL GENERATED  —  Window #{window_index}",
            border,
            f"  PAIR:         {self.PAIR}",
            f"  SIGNAL:       {signal.value}",
            f"  ENTRY PRICE:  {entry_price:.2f}",
            f"  GENERATED AT: {now_dt:%Y-%m-%d %H:%M:%S} UTC",
            f"  EXPIRY TIME:  {expiry_dt:%Y-%m-%d %H:%M:%S} UTC",
            f"  SCORE:        {score:+d}",
            f"  FALLBACK:     {'YES' if used_fallback else 'NO'}",
            border,
            "",
        ]

        output = "\n".join(lines)
        print(output)
        logger.info(
            "Signal emitted: %s @ %.2f  score=%+d  fallback=%s  expiry=%s",
            signal.value,
            entry_price,
            score,
            used_fallback,
            expiry_dt.isoformat(),
        )
