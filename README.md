# XAUUSD Real-Time Signal Engine (M15)

Advanced real-time signal generation system for the **XAUUSD (Gold)** trading pair using the Deriv WebSocket API with a 15-minute window architecture.

## Web Dashboard

Open `index.html` in any modern browser to launch the real-time signal dashboard. No server required — the browser connects directly to the Deriv WebSocket API.

The dashboard displays:
- **Live gold price** with tick-by-tick updates
- **Window phase progress** with countdown timer
- **Momentum analysis** with visual bar and uptick/downtick counts
- **EMA-20 / EMA-50 trend indicators** with crossover detection
- **Scoring breakdown** showing each component's contribution
- **Current signal** (CALL / PUT) with entry price and expiry
- **Signal history** log of all generated signals
- **Recent tick log** with spike detection markers

## Features

- **Real-time tick processing** via Deriv WebSocket (`frxXAUUSD`)
- **Web-based dashboard** — no installation needed, runs in the browser
- **Anti-spike filter** to handle gold's characteristic sudden price spikes
- **15-minute window engine** with four distinct phases (Collection → Analysis → Signal → Hold)
- **Tick momentum analysis** (uptick/downtick ratio)
- **EMA-20 / EMA-50 trend indicators**
- **Weighted scoring system** with mandatory fallback layer
- Exactly **one signal per window** — guaranteed

## Architecture

| # | Module | Purpose |
|---|--------|---------|
| 1 | WebSocket Data Client | Connects to Deriv API, subscribes to XAUUSD ticks |
| 2 | Tick Buffer Manager | Rolling buffer of 120 ticks |
| 3 | Anti-Spike Filter | Suppresses anomalous price spikes (>0.25% threshold) |
| 4 | Window Time Engine | 15-min window lifecycle with 4 phases |
| 5 | Tick Aggregation Engine | Collects per-window statistics |
| 6 | Momentum Analyzer | Computes micro-momentum ratio |
| 7 | Trend Indicator Engine | EMA-20 / EMA-50 crossover |
| 8 | Signal Decision Engine | Weighted scoring → CALL / PUT |
| 9 | Signal Output Interface | Formatted signal display |

## Window Phases

| Phase | Time | Purpose |
|-------|------|---------|
| 1 — Data Collection | 0–3 min | Gather ticks, stabilise buffer |
| 2 — Analysis | 3–5 min | Compute momentum & indicators |
| 3 — Signal Generation | Minute 5 | Produce CALL or PUT signal |
| 4 — Hold | 5–15 min | Maintain signal until expiry |

## Signal Scoring

| Condition | Score |
|-----------|-------|
| Tick momentum bullish | +2 |
| EMA20 > EMA50 | +1 |
| price_now > price_start | +1 |
| Tick momentum bearish | −2 |
| EMA20 < EMA50 | −1 |
| price_now < price_start | −1 |

- **Score ≥ +3** → `CALL`
- **Score ≤ −3** → `PUT`
- **Otherwise** → Fallback (price direction)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the engine
python -m src
```

## Requirements

- Python 3.10+
- `websockets >= 12.0`

## Signal Output Example

```
====================================================
  SIGNAL GENERATED  —  Window #1
====================================================
  PAIR:         XAUUSD
  SIGNAL:       CALL
  ENTRY PRICE:  2925.47
  GENERATED AT: 2026-03-09 08:30:00 UTC
  EXPIRY TIME:  2026-03-09 08:40:00 UTC
  SCORE:        +3
  FALLBACK:     NO
====================================================
```

## Data Source

Deriv WebSocket API:
- Endpoint: `wss://ws.derivws.com/websockets/v3?app_id=114791`
- Symbol: `frxXAUUSD`

## Performance Targets

- Signal frequency: 1 signal every 15 minutes
- Expected accuracy: 58–65%
- Emphasis: reliability, deterministic logic, real-time performance
