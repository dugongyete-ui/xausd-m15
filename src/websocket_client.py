"""Module 1: WebSocket Data Client.

Connects to the Deriv WebSocket API and subscribes to XAUUSD tick data.
Passes incoming ticks to the registered callback for downstream processing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import websockets
import websockets.asyncio.client

logger = logging.getLogger(__name__)

DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=114791"
SUBSCRIBE_PAYLOAD = json.dumps({"ticks": "frxXAUUSD", "subscribe": 1})


class WebSocketClient:
    """Manages the WebSocket connection to the Deriv API for XAUUSD ticks."""

    def __init__(self, on_tick: Callable[[float, int], Awaitable[None]]) -> None:
        """Initialise with a coroutine callback ``on_tick(price, epoch)``."""
        self._on_tick = on_tick
        self._ws: websockets.asyncio.client.ClientConnection | None = None
        self._running = False

    async def connect(self) -> None:
        """Connect, subscribe and start consuming ticks.

        Automatically reconnects on transient failures with exponential back-off.
        """
        self._running = True
        backoff = 1.0
        max_backoff = 30.0

        while self._running:
            try:
                logger.info("Connecting to Deriv WebSocket …")
                async with websockets.asyncio.client.connect(DERIV_WS_URL) as ws:
                    self._ws = ws
                    await ws.send(SUBSCRIBE_PAYLOAD)
                    logger.info("Subscribed to frxXAUUSD ticks.")
                    backoff = 1.0  # reset on successful connection

                    async for raw_msg in ws:
                        if not self._running:
                            break
                        await self._handle_message(raw_msg)

            except (
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                OSError,
            ) as exc:
                logger.warning("WebSocket error: %s – reconnecting in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

        logger.info("WebSocket client stopped.")

    async def _handle_message(self, raw_msg: str | bytes) -> None:
        """Parse an incoming message and dispatch valid ticks."""
        try:
            data: dict[str, Any] = json.loads(raw_msg)
        except json.JSONDecodeError:
            logger.debug("Non-JSON message ignored.")
            return

        tick = data.get("tick")
        if tick is None:
            # Could be a subscription confirmation or error – log and skip.
            if "error" in data:
                logger.error("API error: %s", data["error"])
            return

        price = float(tick["quote"])
        epoch = int(tick["epoch"])
        await self._on_tick(price, epoch)

    async def stop(self) -> None:
        """Gracefully shut down the client."""
        self._running = False
        if self._ws is not None:
            await self._ws.close()
