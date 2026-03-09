# Testing XAUUSD M15 Signal Engine Dashboard

## Overview
This is a Python (aiohttp) + vanilla JS single-page dashboard that displays real-time XAUUSD gold price signals using the Deriv WebSocket API.

## Setup
1. Run `bash setup.sh` to install Python dependencies (aiohttp, websockets)
2. Start the server: `python3 server.py` (runs on port 5000)
3. Open browser to `http://localhost:5000`

## Architecture
- **Backend**: `server.py` - aiohttp web server with WebSocket endpoint at `/ws`
  - Connects to Deriv API (`wss://ws.derivws.com/websockets/v3?app_id=114791`) for live XAUUSD ticks
  - Preloads 500 historical ticks on startup
  - Maintains `engine_state`, `signal_history`, and `tick_history` in memory
  - Sends `init` message with full state to new WebSocket clients
- **Frontend**: `index.html` - single HTML file with embedded CSS and JS
  - Connects via WebSocket to `/ws`
  - Renders price chart on canvas, signal cards, indicators, and history

## Key Testing Scenarios

### Chart Persistence After Refresh
1. Open dashboard, wait for chart to show tick line (green line in chart area)
2. Note the tick count and chart pattern
3. Refresh browser (F5)
4. Verify chart immediately shows the same tick history (not "Waiting for tick data...")
5. Verify new ticks continue appending to the restored chart

### Window Reset
- Windows are 15 minutes, aligned to clock boundaries (:00, :15, :30, :45)
- On window reset, `tick_history` clears server-side, chart starts fresh
- Phase progression: Data Collection (0-3min) → Analysis (3-5min) → Signal Gen (min 5) → Hold (5-15min)

### Market Hours
- Gold/Forex markets are closed on weekends (Saturday-Sunday)
- If market is closed, server shows "Market Closed" status and retries every 60s
- Historical preload may fail with `MarketIsClosed` error when market is closed
- Best to test during market hours (Mon-Fri) for live tick data
- Even during market closed periods, the server may still return recent historical data

## Devin Secrets Needed
No secrets needed - the Deriv API app_id is hardcoded in server.py.

## Common Issues
- If the chart shows "Waiting for tick data..." after refresh, the `tick_history` may be empty (e.g. server just started or market was closed during preload)
- Canvas sizing issues may appear on devices with non-integer DPR (e.g. 1.5x) - the code uses `Math.round()` to handle this
- The server stores up to 2000 ticks in memory; after that it downsamples by keeping every other tick
