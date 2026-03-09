# XAUUSD Real-Time Signal Engine (M15)

## Overview

This project is a real-time trading signal generator for the XAUUSD (Gold) currency pair. It connects to the Deriv WebSocket API, processes live tick data, and produces CALL or PUT signals on a 15-minute window cycle.

The system has two modes of operation:
1. **Browser-only dashboard** (`index.html`) — connects directly to the Deriv WebSocket API from the browser, no server needed
2. **Backend server** (`server.py`) — a Python async server that processes ticks server-side and pushes state to connected browser clients via WebSocket

The signal engine uses a weighted scoring system combining tick momentum, EMA crossover analysis, and price direction to generate exactly one signal per 15-minute window.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Signal Processing Pipeline

The engine is structured as nine sequential modules, each in `src/`:

1. **WebSocketClient** (`websocket_client.py`) — Connects to `wss://ws.derivws.com/websockets/v3?app_id=114791`, subscribes to `frxXAUUSD` ticks, and handles reconnection with exponential backoff
2. **TickBuffer** (`tick_buffer.py`) — Rolling deque of 120 most-recent ticks used by downstream analyzers
3. **AntiSpikeFilter** (`anti_spike_filter.py`) — Rejects ticks with >0.25% price change vs. previous valid tick; requires 3 stable ticks after a spike before resuming
4. **WindowEngine** (`window_engine.py`) — Manages 15-minute (900s) window lifecycle with 4 phases:
   - Data Collection: 0–180s
   - Analysis: 180–300s
   - Signal Generation: at 300s
   - Hold: 300–900s
5. **TickAggregator** (`tick_aggregator.py`) — Tracks window open price and collects valid prices per window
6. **MomentumAnalyzer** (`momentum_analyzer.py`) — Computes uptick/downtick ratio; >0.60 = bullish, <0.40 = bearish
7. **TrendEngine** (`trend_engine.py`) — Calculates EMA-20 and EMA-50; crossover determines trend direction
8. **SignalDecisionEngine** (`signal_decision.py`) — Weighted scoring: momentum (+/-2), EMA crossover (+/-1), price direction (+/-1); score ≥+3 → CALL, ≤-3 → PUT; otherwise falls back to price direction
9. **SignalOutput** (`signal_output.py`) — Formats and emits the signal to stdout/logs

### Backend Server (`server.py`)

- Built with `aiohttp` for HTTP and WebSocket serving
- Maintains a global `engine_state` dict that gets broadcast to all connected browser clients
- Tracks up to 50 signals in `signal_history`
- Runs the Deriv WebSocket connection and tick processing in a background async task
- Listens on port 5000

### Frontend (`index.html`)

- Single HTML file with embedded CSS and JavaScript
- Can run standalone (browser connects directly to Deriv API) or receive state from the Python backend
- Displays live price, window phase countdown, momentum bars, EMA indicators, scoring breakdown, current signal, and signal history

### Orchestration (`src/main.py`)

- `SignalEngine` class wires all modules together
- Runs as an async pipeline via `python -m src`
- Handles graceful shutdown via OS signals

## External Dependencies

### Deriv WebSocket API
- URL: `wss://ws.derivws.com/websockets/v3?app_id=114791`
- Public API — no authentication or API keys required
- Subscription payload: `{"ticks": "frxXAUUSD", "subscribe": 1}`
- Used for real-time XAUUSD tick data

### Python Packages (`requirements.txt`)
- `websockets >= 12.0` — WebSocket client for the Deriv API connection
- `aiohttp` — Async HTTP server and WebSocket server for the browser dashboard backend

### No Database
- The system is entirely in-memory; signal history is stored in a Python list (max 50 entries) and is lost on restart
- No persistent storage is configured

### No Authentication
- The Deriv API endpoint used is public (app_id 114791 is embedded in the URL)
- The web dashboard has no user authentication layer