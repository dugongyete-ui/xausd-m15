# Testing the XAUUSD Signal Engine

## Overview
The signal engine is a CLI application that connects to the Deriv WebSocket API and generates CALL/PUT signals on a 15-minute window cycle. Testing requires observing full window cycles.

## Key Challenge: Timing
The engine generates signals at minute 5 of each 15-minute window. Waiting 5+ minutes per cycle makes real-time testing impractical.

## Recommended Testing Approach: Accelerated Window Timings
Create a temporary test script that monkey-patches `src.window_engine` constants and the `WindowEngine.phase` property to use compressed timings:

- Patch `WINDOW_DURATION` from 900s to ~30s
- Patch the `phase` property to use shorter boundaries (e.g., 10s collection, 8s analysis, 2s signal generation, 10s hold)
- Optionally patch the status loop interval from 30s to 5s for more frequent log output

This exercises the exact same code paths with real WebSocket data but completes a full cycle in ~30 seconds.

## What to Verify
1. **WebSocket Connection**: Look for "Connecting to Deriv WebSocket" and "Subscribed to frxXAUUSD ticks" in logs
2. **Phase Transitions**: Status logs should show `data_collection` → `analysis` → `signal_generation` → `hold`
3. **Signal Output**: A formatted signal block should appear on stdout containing:
   - PAIR: XAUUSD
   - SIGNAL: CALL or PUT
   - ENTRY PRICE: non-zero value
   - GENERATED AT / EXPIRY TIME: valid UTC timestamps
   - SCORE: integer
   - FALLBACK: YES or NO
4. **Window Reset**: After window expiry, logs should show "Window #N expired. Resetting" followed by "Window #N+1 started"
5. **Multiple Cycles**: Run for at least 2-3 cycles to confirm repeatable signal generation

## Expected Behavior Notes
- With accelerated timings and fewer ticks, the fallback layer will likely be used (scores rarely reach ±3 with <20 ticks)
- In production with 300s of data collection, the buffer will accumulate many more ticks, making non-fallback scoring decisions more common
- Both CALL and PUT signals should be observable across multiple cycles depending on market direction

## Running the Engine
```bash
pip install -r requirements.txt
python -m src
```

## Dependencies
- Python 3.10+
- `websockets >= 12.0`
- No credentials or API keys needed (Deriv public API with app_id 114791)

## Devin Secrets Needed
None — the Deriv WebSocket API used by this engine is public and requires no authentication.
