import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import ActivityLog, Dataset, ProcessingJob


def log_activity(
    db: Session,
    event: str,
    target: str | None = None,
    status: str = "success",
    detail: str | None = None,
) -> ActivityLog:
    entry = ActivityLog(event=event, target=target, status=status, detail=detail)
    db.add(entry)
    db.commit()
    return entry


def active_dataset(db: Session, dataset_id: str | None = None) -> Dataset | None:
    if dataset_id:
        return db.get(Dataset, dataset_id)
    ds = (
        db.query(Dataset)
        .filter(Dataset.status == "ready")
        .order_by(Dataset.created_at.desc())
        .first()
    )
    return ds


def job_params(job: ProcessingJob) -> dict:
    if not job.params_json:
        return {}
    try:
        return json.loads(job.params_json)
    except json.JSONDecodeError:
        return {}


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
