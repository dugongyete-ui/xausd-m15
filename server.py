"""XAUUSD M15 Signal Engine — Web Server (24/7 Backend)."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from aiohttp import web, WSMsgType
import websockets.asyncio.client as wsc

from src.anti_spike_filter import AntiSpikeFilter
from src.momentum_analyzer import MomentumAnalyzer, MomentumBias
from src.signal_decision import Signal, SignalDecisionEngine
from src.tick_aggregator import TickAggregator
from src.tick_buffer import TickBuffer
from src.trend_engine import TrendEngine, TrendDirection
from src.window_engine import WindowEngine, WindowPhase

logger = logging.getLogger(__name__)

DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=114791"
SUBSCRIBE_PAYLOAD = json.dumps({"ticks": "frxXAUUSD", "subscribe": 1})
PORT = 5000

MARKET_CLOSED_RETRY_INTERVAL = 60.0
NORMAL_BACKOFF_MAX = 30.0

connected_clients: set[web.WebSocketResponse] = set()
signal_history: list[dict] = []
MAX_HISTORY = 50

# Store recent ticks so new/reconnecting clients get chart history
tick_history: list[dict] = []
MAX_TICK_HISTORY = 2000

engine_state: dict = {
    "phase": "data_collection",
    "remaining": 900,
    "elapsed": 0,
    "windowIndex": 0,
    "windowStart": 0,
    "windowExpiry": 0,
    "price": None,
    "priceStart": None,
    "tickCount": 0,
    "bufferCount": 0,
    "derivConnected": False,
    "marketClosed": False,
    "indicators": None,
    "currentSignal": None,
    "inSpike": False,
}


async def broadcast(msg: dict) -> None:
    if not connected_clients:
        return
    data = json.dumps(msg)
    dead: set[web.WebSocketResponse] = set()
    for ws in list(connected_clients):
        try:
            await ws.send_str(data)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


class WebSignalEngine:
    def __init__(self) -> None:
        self.tick_buffer = TickBuffer()
        self.spike_filter = AntiSpikeFilter()
        self.window_engine = WindowEngine()
        self.tick_aggregator = TickAggregator()
        self.momentum_analyzer = MomentumAnalyzer(self.tick_buffer)
        self.trend_engine = TrendEngine(short_period=20, long_period=50)
        self.decision_engine = SignalDecisionEngine()
        self._signal_emitted = False
        self._current_signal: Signal | None = None
        self._data_preloaded = False

    async def _preload_historical_data(self) -> None:
        """Fetch historical ticks from Deriv API to pre-populate the engine.

        This allows the engine to start with complete data so it can
        immediately compute indicators and generate signals without
        waiting for the data collection phase.
        """
        logger.info("Fetching historical tick data from Deriv API...")

        # Start window engine aligned to 15-minute boundary
        self.window_engine.start()
        window_start = self.window_engine.window_start

        try:
            async with wsc.connect(DERIV_WS_URL) as ws:
                payload = json.dumps({
                    "ticks_history": "frxXAUUSD",
                    "adjust_start_time": 1,
                    "count": 500,
                    "end": "latest",
                    "style": "ticks",
                })
                await ws.send(payload)
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(raw)

                if "error" in data:
                    err = data["error"]
                    if err.get("code") == "MarketIsClosed":
                        engine_state["marketClosed"] = True
                        logger.info("Market is closed during pre-load. Engine will standby.")
                        await broadcast({"type": "marketStatus", "closed": True, "message": err.get("message", "Market closed")})
                    else:
                        logger.warning("API error during pre-load: %s", err)
                    return

                if "history" not in data:
                    logger.warning("No historical data received: %s", data)
                    return

                prices = data["history"]["prices"]
                times = data["history"]["times"]

                for i in range(len(prices)):
                    price = float(prices[i])
                    epoch = int(times[i])

                    # Always add to tick buffer for EMA calculations
                    self.tick_buffer.append(price, epoch)

                    # Store ticks within current window for chart history
                    if epoch >= window_start:
                        tick_history.append({"price": price, "epoch": epoch})

                    # Only add to aggregator if within current window
                    if epoch >= window_start:
                        is_valid = self.spike_filter.check(price)
                        self.tick_aggregator.on_tick(price, is_valid)

                logger.info(
                    "Pre-loaded %d historical ticks. Buffer: %d, Window ticks: %d",
                    len(prices),
                    len(self.tick_buffer),
                    self.tick_aggregator.tick_count,
                )

                self._data_preloaded = True

                # Update engine state
                phase = self.window_engine.phase
                engine_state["phase"] = phase.value
                engine_state["remaining"] = self.window_engine.remaining
                engine_state["elapsed"] = self.window_engine.elapsed
                engine_state["windowIndex"] = self.window_engine.window_index
                engine_state["windowStart"] = self.window_engine.window_start
                engine_state["windowExpiry"] = self.window_engine.window_expiry
                engine_state["price"] = self.tick_buffer.latest_price
                engine_state["priceStart"] = self.tick_aggregator.price_start
                engine_state["tickCount"] = self.tick_aggregator.tick_count
                engine_state["bufferCount"] = len(self.tick_buffer)
                engine_state["derivConnected"] = True

                # If we have enough data, compute indicators
                if phase in (
                    WindowPhase.ANALYSIS,
                    WindowPhase.SIGNAL_GENERATION,
                    WindowPhase.HOLD,
                ):
                    indicators = self._compute_indicators()
                    engine_state["indicators"] = indicators

                # If past signal generation and no signal yet, generate now
                if phase in (WindowPhase.SIGNAL_GENERATION, WindowPhase.HOLD):
                    if not self._signal_emitted:
                        await self._generate_signal()
                        logger.info(
                            "Signal generated immediately from historical data (phase: %s)",
                            phase.value,
                        )

        except Exception as e:
            logger.error("Failed to fetch historical data: %s", e)
            # Still start the window engine even if historical fetch fails
            if self.window_engine.window_index == 0:
                self.window_engine.start()

    async def run(self) -> None:
        # Pre-load historical data before starting live stream
        await self._preload_historical_data()

        backoff = 1.0
        while True:
            try:
                logger.info("Connecting to Deriv WebSocket...")
                engine_state["derivConnected"] = False
                await broadcast({"type": "derivStatus", "connected": False, "marketClosed": engine_state["marketClosed"]})
                async with wsc.connect(DERIV_WS_URL) as ws:
                    engine_state["derivConnected"] = True
                    await broadcast({"type": "derivStatus", "connected": True, "marketClosed": engine_state["marketClosed"]})
                    await ws.send(SUBSCRIBE_PAYLOAD)
                    logger.info("Subscribed to frxXAUUSD ticks.")
                    backoff = 1.0
                    async for raw_msg in ws:
                        try:
                            data = json.loads(raw_msg)
                            if "tick" in data:
                                # Market is open — clear closed flag if it was set
                                if engine_state["marketClosed"]:
                                    engine_state["marketClosed"] = False
                                    logger.info("Market is now open. Resuming signal engine.")
                                    await broadcast({"type": "marketStatus", "closed": False})
                                price = float(data["tick"]["quote"])
                                epoch = int(data["tick"]["epoch"])
                                await self._on_tick(price, epoch)
                            elif "error" in data:
                                err = data["error"]
                                err_code = err.get("code", "")
                                err_msg = err.get("message", str(err))
                                if err_code == "MarketIsClosed":
                                    if not engine_state["marketClosed"]:
                                        engine_state["marketClosed"] = True
                                        logger.info("Market is closed. Will retry in %.0fs.", MARKET_CLOSED_RETRY_INTERVAL)
                                        await broadcast({"type": "marketStatus", "closed": True, "message": err_msg})
                                    # Close WS so we retry after the interval
                                    break
                                else:
                                    logger.error("Deriv API error: %s", err)
                        except Exception as e:
                            logger.error("Tick processing error: %s", e)
            except Exception as exc:
                logger.warning("WS disconnected: %s -- reconnecting in %.1fs", exc, backoff)
                engine_state["derivConnected"] = False
                await broadcast({"type": "derivStatus", "connected": False, "marketClosed": engine_state["marketClosed"]})

            if engine_state["marketClosed"]:
                # When market is closed, poll every 60s instead of aggressive backoff
                logger.info("Market closed — waiting %.0fs before next check...", MARKET_CLOSED_RETRY_INTERVAL)
                await asyncio.sleep(MARKET_CLOSED_RETRY_INTERVAL)
                backoff = 1.0
            else:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, NORMAL_BACKOFF_MAX)

    async def _on_tick(self, price: float, epoch: int) -> None:
        if self.window_engine.window_index == 0:
            self.window_engine.start()

        if self.window_engine.should_reset():
            await self._reset_window()

        is_valid = self.spike_filter.check(price)
        self.tick_buffer.append(price, epoch)
        self.tick_aggregator.on_tick(price, is_valid)

        # Store tick for chart history (sent to new/reconnecting clients)
        tick_history.append({"price": price, "epoch": epoch})
        if len(tick_history) > MAX_TICK_HISTORY:
            # Downsample: keep every other tick to reduce memory
            tick_history[:] = tick_history[::2]

        phase = self.window_engine.phase
        engine_state["phase"] = phase.value
        engine_state["remaining"] = self.window_engine.remaining
        engine_state["elapsed"] = self.window_engine.elapsed
        engine_state["windowIndex"] = self.window_engine.window_index
        engine_state["windowStart"] = self.window_engine.window_start
        engine_state["windowExpiry"] = self.window_engine.window_expiry
        engine_state["price"] = price
        engine_state["priceStart"] = self.tick_aggregator.price_start
        engine_state["tickCount"] = self.tick_aggregator.tick_count
        engine_state["bufferCount"] = len(self.tick_buffer)
        engine_state["inSpike"] = self.spike_filter._in_spike

        await broadcast({
            "type": "tick",
            "price": price,
            "epoch": epoch,
            "isSpike": not is_valid,
            "inSpike": self.spike_filter._in_spike,
            "phase": phase.value,
            "remaining": self.window_engine.remaining,
            "elapsed": self.window_engine.elapsed,
            "windowIndex": self.window_engine.window_index,
            "windowStart": self.window_engine.window_start,
            "windowExpiry": self.window_engine.window_expiry,
            "priceStart": self.tick_aggregator.price_start,
            "tickCount": self.tick_aggregator.tick_count,
            "bufferCount": len(self.tick_buffer),
        })

        # Compute indicators in analysis, signal gen, AND hold phases
        # (hold included for mid-window starts with pre-loaded data)
        if phase in (WindowPhase.ANALYSIS, WindowPhase.SIGNAL_GENERATION, WindowPhase.HOLD):
            indicators = self._compute_indicators()
            engine_state["indicators"] = indicators
            await broadcast({"type": "indicators", **indicators})

        # Generate signal in both SIGNAL_GENERATION and HOLD phases
        # (hold included for mid-window starts where minute 5 was missed)
        if phase in (WindowPhase.SIGNAL_GENERATION, WindowPhase.HOLD) and not self._signal_emitted:
            await self._generate_signal()

    def _compute_indicators(self) -> dict:
        ratio, momentum_bias = self.momentum_analyzer.compute()
        prices = self.tick_buffer.prices
        ema20, ema50, trend_dir = self.trend_engine.compute(prices)

        p_start = self.tick_aggregator.price_start
        p_now = self.tick_aggregator.price_now

        s_mom = 2 if momentum_bias is MomentumBias.BULLISH else (-2 if momentum_bias is MomentumBias.BEARISH else 0)
        s_trend = 1 if trend_dir is TrendDirection.BULLISH else (-1 if trend_dir is TrendDirection.BEARISH else 0)
        s_price = 0
        if p_start is not None and p_now is not None:
            if p_now > p_start:
                s_price = 1
            elif p_now < p_start:
                s_price = -1

        p_list = self.tick_buffer.prices
        upticks = downticks = 0
        for i in range(1, len(p_list)):
            if p_list[i] > p_list[i - 1]:
                upticks += 1
            elif p_list[i] < p_list[i - 1]:
                downticks += 1

        return {
            "momentum": {
                "bias": momentum_bias.value,
                "ratio": ratio,
                "upticks": upticks,
                "downticks": downticks,
            },
            "trend": {
                "direction": trend_dir.value,
                "ema20": ema20,
                "ema50": ema50,
            },
            "score": {
                "total": s_mom + s_trend + s_price,
                "momentum": s_mom,
                "trend": s_trend,
                "price": s_price,
            },
        }

    async def _generate_signal(self) -> None:
        ratio, momentum_bias = self.momentum_analyzer.compute()
        prices = self.tick_buffer.prices
        ema20, ema50, trend_dir = self.trend_engine.compute(prices)
        signal, score, used_fallback = self.decision_engine.evaluate(
            momentum_bias, trend_dir,
            self.tick_aggregator.price_start,
            self.tick_aggregator.price_now,
        )

        entry_price = self.tick_aggregator.price_now
        expiry_epoch = self.window_engine.window_expiry
        window_index = self.window_engine.window_index

        sig_record = {
            "signal": signal.value,
            "entryPrice": entry_price,
            "expiryEpoch": expiry_epoch,
            "windowIndex": window_index,
            "score": score,
            "usedFallback": used_fallback,
            "time": time.time(),
            "expiryPrice": None,
            "outcome": None,
        }
        signal_history.insert(0, sig_record)
        if len(signal_history) > MAX_HISTORY:
            signal_history.pop()

        engine_state["currentSignal"] = {
            "signal": signal.value,
            "entryPrice": entry_price,
            "expiryEpoch": expiry_epoch,
            "windowIndex": window_index,
            "score": score,
            "usedFallback": used_fallback,
            "time": time.time(),
        }

        self._signal_emitted = True
        self._current_signal = signal

        logger.info(
            "SIGNAL: %s | score=%+d | fallback=%s | entry=%.2f | window=#%d",
            signal.value, score, used_fallback, entry_price or 0, window_index
        )

        signal_time = engine_state["currentSignal"]["time"]
        await broadcast({
            "type": "signal",
            "signal": signal.value,
            "entryPrice": entry_price,
            "expiryEpoch": expiry_epoch,
            "windowIndex": window_index,
            "score": score,
            "usedFallback": used_fallback,
            "time": signal_time,
        })

    async def _reset_window(self) -> None:
        p_now = self.tick_aggregator.price_now
        if signal_history and signal_history[0]["outcome"] is None and p_now is not None:
            sig_rec = signal_history[0]
            sig_rec["expiryPrice"] = p_now
            if sig_rec["entryPrice"] is not None:
                if sig_rec["signal"] == "CALL":
                    sig_rec["outcome"] = "WIN" if p_now > sig_rec["entryPrice"] else "LOSS"
                else:
                    sig_rec["outcome"] = "WIN" if p_now < sig_rec["entryPrice"] else "LOSS"

        self.window_engine.reset()
        self.tick_aggregator.reset()
        self.spike_filter.reset()
        self._signal_emitted = False
        self._current_signal = None
        engine_state["currentSignal"] = None
        engine_state["indicators"] = None
        engine_state["inSpike"] = False

        # Clear tick history for the new window
        tick_history.clear()

        await broadcast({
            "type": "windowReset",
            "windowIndex": self.window_engine.window_index,
            "history": signal_history[:MAX_HISTORY],
        })


async def index_handler(request: web.Request) -> web.FileResponse:
    return web.FileResponse(Path(__file__).parent / "index.html")


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    connected_clients.add(ws)
    logger.info("Client connected. Total: %d", len(connected_clients))

    try:
        await ws.send_str(json.dumps({
            "type": "init",
            "state": engine_state,
            "history": signal_history,
            "tickHistory": tick_history,
        }))

        async for msg in ws:
            if msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break
    finally:
        connected_clients.discard(ws)
        logger.info("Client disconnected. Total: %d", len(connected_clients))

    return ws


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/ws", ws_handler)
    return app


def _setup_logging() -> None:
    fmt = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


async def main() -> None:
    _setup_logging()
    engine = WebSignalEngine()
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("Server running at http://0.0.0.0:%d", PORT)
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
