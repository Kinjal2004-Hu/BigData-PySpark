import json, subprocess, sys, time, uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] if "__file__" in dir() else Path.cwd()
sys.path.insert(0, str(ROOT / "backend"))
from sqlalchemy import text
from app.core.database import session_scope

with session_scope() as db:
    ds = db.execute(text("SELECT id FROM datasets WHERE status='ready' ORDER BY created_at DESC LIMIT 1")).scalar()
    job_id = uuid.uuid4().hex
    db.execute(text("INSERT INTO processing_jobs (id, dataset_id, job_type, status, records_processed, created_at, stage, params_json) VALUES (:id,:ds,'segmentation','pending',0,CURRENT_TIMESTAMP,'Queued',:p)"), {"id": job_id, "ds": ds, "p": json.dumps({"dataset_id": ds, "k": 6, "seed": 42, "run_id": "seg-002"})})
print("job", job_id)
t0 = time.time()
r = subprocess.run([sys.executable, "-m", "data_engine.pipeline", "--job", job_id], cwd=str(ROOT))
with session_scope() as db:
    st = db.execute(text("SELECT status, error_summary FROM processing_jobs WHERE id=:i"), {"i": job_id}).first()
print("status:", st, f"({time.time()-t0:.0f}s)")
sys.exit(0 if r.returncode == 0 and st[0] == "completed" else 1)
