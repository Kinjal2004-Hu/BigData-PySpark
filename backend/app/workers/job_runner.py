"""Subprocess-based job runner for long-running Spark operations.

Jobs run as `python -m data_engine.pipeline --job <id>` so HTTP requests
never block on Spark. Job state lives in SQLite and survives restarts.
"""
import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR, get_settings
from app.models import ActivityLog, ProcessingJob

_lock = threading.Lock()
_procs: dict[str, subprocess.Popen] = {}


def _python() -> str:
    return sys.executable or "python"


def start_job(db: Session, job: ProcessingJob) -> None:
    """Spawn the pipeline subprocess for a pending job."""
    with _lock:
        proc = _procs.get(job.id)
        if proc is not None and proc.poll() is None:
            return  # already running

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        settings = get_settings()
        env.setdefault("SPARK_MASTER", settings.spark_master)
        env.setdefault("KMEANS_K", str(settings.kmeans_k))
        env.setdefault("KMEANS_SEED", str(settings.kmeans_seed))

        log_dir = ROOT_DIR / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"job_{job.id}.log"
        log_file = open(log_path, "w", encoding="utf-8")

        proc = subprocess.Popen(
            [_python(), "-m", "data_engine.pipeline", "--job", job.id],
            cwd=str(ROOT_DIR),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        _procs[job.id] = proc

        job.status = "running"
        job.started_at = job.started_at or datetime.utcnow()
        job.stage = "Worker started"
        db.add(
            ActivityLog(
                event=f"{job.job_type.capitalize()} job started",
                target=job.dataset_id,
                status="info",
                detail=f"job_id={job.id}",
            )
        )
        db.commit()
        threading.Thread(target=_reap, args=(job.id, log_file), daemon=True).start()


def _reap(job_id: str, log_file) -> None:
    proc = _procs.get(job_id)
    if proc is None:
        return
    proc.wait()
    try:
        log_file.close()
    except Exception:
        pass


def retry_job(db: Session, job: ProcessingJob) -> ProcessingJob:
    """Reset a failed job to pending and restart it safely."""
    if job.status == "running":
        return job
    job.status = "pending"
    job.error_summary = None
    job.started_at = None
    job.finished_at = None
    job.stage = "Queued for retry"
    db.commit()
    with _lock:
        _procs.pop(job.id, None)
    start_job(db, job)
    return job


def create_job(
    db: Session,
    job_type: str,
    dataset_id: str | None,
    params: dict | None = None,
) -> ProcessingJob:
    job = ProcessingJob(
        job_type=job_type,
        dataset_id=dataset_id,
        status="pending",
        params_json=json.dumps(params or {}),
        stage="Queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    start_job(db, job)
    return job
