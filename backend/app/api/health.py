from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Dataset, ProcessingJob
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    db_status = "ok"
    active = None
    last_processed = None
    try:
        active = (
            db.query(Dataset)
            .filter(Dataset.status == "ready")
            .order_by(Dataset.created_at.desc())
            .first()
        )
        done = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.status == "completed")
            .order_by(ProcessingJob.finished_at.desc())
            .first()
        )
        last_processed = done.finished_at if done else None
    except Exception:
        db_status = "error"
    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        version="1.0.0",
        active_dataset=active.id if active else None,
        last_processed=last_processed,
    )
