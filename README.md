# Broker Signal Upload System — Mock Practice

A hands-on simulation of a quantitative trading signal upload pipeline, built to understand how Python interacts with broker APIs in a real-world fintech context.

## What This Project Does

```
signals.csv  ──►  upload_client.py  ──►  mock_broker.py (FastAPI)
  (trading          (reads file,           (simulates broker:
   signals)          retries, logs)         validates, dedupes,
                                            returns order ID)
```

1. **`mock_broker.py`** — A FastAPI server that simulates a real broker's REST API, including random 503 failures and idempotency checks
2. **`upload_client.py`** — A client that reads a CSV signal file, uploads each signal with exponential backoff retry, and saves structured logs
3. **`signals.csv`** — Sample trading signal data (A-share market format)

## Key Concepts Demonstrated

| Concept | Where |
|---------|-------|
| RESTful API design | `mock_broker.py` — POST /signals/upload |
| Pydantic data validation | `TradeSignal` model with field validators |
| Idempotency | Duplicate `signal_id` detection |
| Exponential backoff | Retry on 503: 2s → 4s → 8s |
| Structured logging | Dual output: terminal + `.log` file |
| JSON audit trail | `logs/result_*.json` for reconciliation |
| ConnectionError handling | Client gracefully handles server-down state |

## Quick Start

### 1. Install dependencies
```bash
pip install fastapi uvicorn requests
```

### 2. Start the mock broker server (Terminal 1)
```bash
python mock_broker.py
```
API docs available at: http://localhost:8000/docs

### 3. Run the upload client (Terminal 2)
```bash
python upload_client.py
```

### 4. Check results
```bash
cat logs/result_*.json
```

## Sample Output

```
🚀 Trading Signal Upload Started [2026-04-29 11:17:11]
==================================================
11:17:11 [INFO]   Uploading SIG_20260428_001 ... (attempt 1)
11:17:11 [INFO]   ✅ Success | Order: ORD_52C50020
11:17:11 [INFO]   Uploading SIG_20260428_002 ... (attempt 1)
11:17:13 [WARNING]   ⚠️  Broker unavailable, retrying in 2s...
11:17:15 [INFO]   ✅ Success | Order: ORD_25F9E5A1
11:17:15 [WARNING]   ♻️  Duplicate signal ignored: SIG_20260428_001
==================================================
📊 Done: ✅Success 4  ♻️Duplicate 1  ❌Failed 0
```

## Signal File Format

```csv
date,time,stock_code,direction,action,volume,price,signal_id
2026-04-28,09:30:00,000001.SZ,BUY,OPEN,1000,15.50,SIG_20260428_001
```

| Field | Description |
|-------|-------------|
| `stock_code` | A-share code: `XXXXXX.SZ` (Shenzhen) or `XXXXXX.SH` (Shanghai) |
| `direction` | `BUY` or `SELL` |
| `action` | `OPEN` (open position) or `CLOSE` (close position) |
| `volume` | Number of shares (must be multiples of 100) |
| `price` | Limit price; `0` = market order |
| `signal_id` | Unique ID for idempotency — same ID will never execute twice |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/signals/upload` | Upload a trading signal |
| `GET` | `/api/v1/account/status` | Query account positions and P&L |
| `GET` | `/api/v1/signals/received` | View all received signals |

## Lessons Learned

- **In-memory storage** resets on server restart → production systems use PostgreSQL for the dedup table
- **Idempotency is critical** in financial systems — network retries must never cause double execution
- **Exponential backoff** is the industry standard for handling transient broker failures
- **Structured JSON logs** serve as the daily reconciliation record between system and broker

## Tech Stack

- Python 3.13
- FastAPI + Uvicorn
- Pydantic v2
- Requests
- Standard library: `csv`, `json`, `logging`, `pathlib`
