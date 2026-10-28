"""Fast E2E seed: create dataset + jobs in SQLite, run pipeline stages via subprocess.

Usage: py -3.13 scripts/run_e2e.py
"""
import csv as csvmod
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import text  # noqa: E402

from app.core.database import init_db, session_scope  # noqa: E402
from app.models import Dataset  # noqa: E402
from data_engine.config import detect_mapping  # noqa: E402

IMPORT_SQL = text(
    "INSERT INTO processing_jobs (id, dataset_id, job_type, status, records_processed, created_at, stage, params_json) "
    "VALUES (:id, :ds, 'import', 'pending', 0, CURRENT_TIMESTAMP, 'Queued', :params)"
)
SEG_SQL = text(
    "INSERT INTO processing_jobs (id, dataset_id, job_type, status, records_processed, created_at, stage, params_json) "
    "VALUES (:id, :ds, 'segmentation', 'pending', 0, CURRENT_TIMESTAMP, 'Queued', :params)"
)


def job_status(job_id: str) -> tuple[str, str | None]:
    import sqlite3

    db = sqlite3.connect(ROOT / "data" / "customeriq.db")
    row = db.execute(
        "SELECT status, error_summary FROM processing_jobs WHERE id=?", (job_id,)
    ).fetchone()
    db.close()
    return (row[0], row[1]) if row else ("missing", "job row not found")


def run_job(job_id: str, label: str) -> None:
    t0 = time.time()
    r = subprocess.run(
        [sys.executable, "-m", "data_engine.pipeline", "--job", job_id],
        cwd=str(ROOT),
    )
    st, err = job_status(job_id)
    print(f"{label}: status={st} ({time.time() - t0:.0f}s)", err or "")
    if r.returncode != 0 or st != "completed":
        sys.exit(f"{label} FAILED")


def main() -> None:
    init_db()
    csv_path = ROOT / "data" / "raw" / "demo_online_retail.csv"
    with open(csv_path, newline="", encoding="utf-8") as fh:
        header = next(csvmod.reader(fh))
    mapping = detect_mapping(header)
    print("mapping:", mapping)

    ds_id = uuid.uuid4().hex
    import_job_id = uuid.uuid4().hex
    seg_job_id = uuid.uuid4().hex

    with session_scope() as db:
        db.add(
            Dataset(
                id=ds_id,
                name="demo_online_retail.csv",
                source_filename="demo_online_retail.csv",
                stored_path=str(csv_path),
                file_size=csv_path.stat().st_size,
                status="pending",
                column_mapping_json=json.dumps(mapping),
            )
        )
        db.flush()  # ensure dataset row exists before job FK insert
        db.execute(
            IMPORT_SQL,
            {
                "id": import_job_id,
                "ds": ds_id,
                "params": json.dumps(
                    {
                        "source_path": str(csv_path),
                        "column_mapping": mapping,
                        "dedupe_policy": "keep_first",
                    }
                ),
            },
        )
        db.execute(
            SEG_SQL,
            {
                "id": seg_job_id,
                "ds": ds_id,
                "params": json.dumps(
                    {"dataset_id": ds_id, "k": 6, "seed": 42, "run_id": "seg-001"}
                ),
            },
        )
    print(f"dataset={ds_id}\nimport_job={import_job_id}\nseg_job={seg_job_id}")

    run_job(import_job_id, "import")
    run_job(seg_job_id, "segmentation")
    print("E2E OK")


if __name__ == "__main__":
    main()
