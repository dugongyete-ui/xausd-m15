"""XAUUSD Real-Time Signal Engine — Main Entry Point.

Integrates all nine modules into a single asynchronous pipeline:

  1. WebSocket Data Client
  2. Tick Buffer Manager
  3. Anti-Spike Filter
  4. Window Time Engine
  5. Tick Aggregation Engine
  6. Momentum Analyzer
  7. Trend Indicator Engine
  8. Signal Decision Engine (+ Fallback)
  9. Signal Output Interface

Usage::

    python -m src.main
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from src.anti_spike_filter import AntiSpikeFilter
from src.momentum_analyzer import MomentumAnalyzer
from src.signal_decision import Signal, SignalDecisionEngine
from src.signal_output import SignalOutput
from src.tick_aggregator import TickAggregator
from src.tick_buffer import TickBuffer
from src.trend_engine import TrendEngine
from src.websocket_client import WebSocketClient
from src.window_engine import WindowEngine, WindowPhase

logger = logging.getLogger(__name__)


class SignalEngine:
    """Orchestrates the full signal-generation pipeline."""

    def __init__(self) -> None:
        # --- Modules ---------------------------------------------------
        self.tick_buffer = TickBuffer()
        self.spike_filter = AntiSpikeFilter()
        self.window_engine = WindowEngine()
        self.tick_aggregator = TickAggregator()
        self.momentum_analyzer = MomentumAnalyzer(self.tick_buffer)
        self.trend_engine = TrendEngine(short_period=20, long_period=50)
        self.decision_engine = SignalDecisionEngine()
        self.signal_output = SignalOutput()
        self.ws_client = WebSocketClient(on_tick=self._on_tick)

        # --- Window state ----------------------------------------------
        self._signal_emitted = False
        self._current_signal: Signal | None = None

    # ------------------------------------------------------------------
    # Tick handler (callback from WebSocketClient)
    # ------------------------------------------------------------------

    async def _on_tick(self, price: float, epoch: int) -> None:
        """Process a single incoming tick through the pipeline."""

        # 1. Start window on first tick
        if self.window_engine.window_index == 0:
            self.window_engine.start()

        # 2. Check for window reset
        if self.window_engine.should_reset():
            self._reset_window()

        # 3. Anti-spike filtering
        is_valid = self.spike_filter.check(price)

        # 4. Always update the tick buffer (even spikes, for price tracking)
        #    but only mark valid ones in the aggregator.
        self.tick_buffer.append(price, epoch)
        self.tick_aggregator.on_tick(price, is_valid)

        # 5. Phase-dependent logic
        phase = self.window_engine.phase

        if phase is WindowPhase.DATA_COLLECTION:
            # Phase 1: silently collect data.
            pass

        elif phase is WindowPhase.ANALYSIS:
            # Phase 2: compute indicators (logged but no signal yet).
            self._run_analysis()

        elif phase is WindowPhase.SIGNAL_GENERATION and not self._signal_emitted:
            # Phase 3: generate and output the signal.
            self._generate_signal()

        # Phase 4 (HOLD): no action required — signal stays fixed.

    # ------------------------------------------------------------------
    # Analysis helpers
    # ------------------------------------------------------------------

    def _run_analysis(self) -> None:
        """Compute momentum and trend indicators (logging only)."""
        self.momentum_analyzer.compute()
        prices = self.tick_buffer.prices
        self.trend_engine.compute(prices)

    def _generate_signal(self) -> None:
        """Evaluate the scoring system and emit the signal."""
        # Momentum
        momentum_ratio, momentum_bias = self.momentum_analyzer.compute()

        # Trend
        prices = self.tick_buffer.prices
        ema_short, ema_long, trend_direction = self.trend_engine.compute(prices)

        # Window price direction
        price_start = self.tick_aggregator.price_start
        price_now = self.tick_aggregator.price_now

        # Decision (includes fallback)
        signal_val, score, used_fallback = self.decision_engine.evaluate(
            momentum_bias=momentum_bias,
            trend_direction=trend_direction,
            price_start=price_start,
            price_now=price_now,
        )

        # Output
        entry_price = price_now if price_now is not None else 0.0
        self.signal_output.emit(
            signal=signal_val,
            entry_price=entry_price,
            expiry_epoch=self.window_engine.window_expiry,
            window_index=self.window_engine.window_index,
            score=score,
            used_fallback=used_fallback,
        )

        self._signal_emitted = True
        self._current_signal = signal_val

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def _reset_window(self) -> None:
        """Reset all per-window state and start a new window."""
        logger.info(
            "Window #%d expired. Resetting for next window.",
            self.window_engine.window_index,
        )
        self.window_engine.reset()
        self.tick_aggregator.reset()
        self.spike_filter.reset()
        self._signal_emitted = False
        self._current_signal = None

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start the engine and block until interrupted."""
        logger.info("Starting XAUUSD Signal Engine …")

        # Background task: periodically log window status.
        status_task = asyncio.create_task(self._status_loop())

        try:
            await self.ws_client.connect()
        finally:
            status_task.cancel()
            try:
                await status_task
            except asyncio.CancelledError:
                pass

    async def _status_loop(self) -> None:
        """Log window status every 30 seconds."""
        while True:
            await asyncio.sleep(30)
            if self.window_engine.window_index == 0:
                continue
            phase = self.window_engine.phase
            remaining = self.window_engine.remaining
            buf_len = len(self.tick_buffer)
            agg_count = self.tick_aggregator.tick_count
            sig = self._current_signal.value if self._current_signal else "PENDING"
            logger.info(
                "Window #%d | Phase: %-18s | Remaining: %5.0fs | Buffer: %3d | Ticks: %4d | Signal: %s",
                self.window_engine.window_index,
                phase.value,
                remaining,
                buf_len,
                agg_count,
                sig,
            )


# ======================================================================
# CLI entry point
# ======================================================================

def _setup_logging() -> None:
    """Configure structured logging to stderr."""
    fmt = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


def main() -> None:
    """Run the signal engine."""
    _setup_logging()

    engine = SignalEngine()
    loop = asyncio.new_event_loop()

    # Graceful shutdown on SIGINT / SIGTERM.
    for sig_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig_name, lambda: asyncio.ensure_future(engine.ws_client.stop()))

    try:
        loop.run_until_complete(engine.run())
    except KeyboardInterrupt:
        logger.info("Interrupted – shutting down.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
