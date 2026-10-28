# CustomerIQ — Customer Segmentation & Purchase Analytics

Retail customer analytics platform: CSV ingestion → PySpark validation → RFM metrics → K-Means (Spark MLlib) → FastAPI + SQLite → web dashboard.

## Run (Windows, Python 3.13 already provisioned)

```powershell
py -3.13 -m venv backend/.venv 2>$null; # optional
py -3.13 -m pip install -r requirements_python.txt   # if needed

# 1. generate demo dataset (~105k transactions)
py -3.13 scripts/generate_demo_data.py

# 2. E2E pipeline: import + segmentation (PySpark, ~1-2 min)
py -3.13 scripts/run_e2e.py

# 3. start API + UI (single process, port 8000)
cd backend
py -3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 — pages: Overview, Customers, Segments, Analytics, Data Import, Processing Jobs, Settings. API docs: /docs

## Config
`.env` (copy from `.env.example`): SQLite path, Spark master, k, seed, upload limits.

## Screenshots
`report_assets/screenshots/*.png`
