from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Dataset, ProcessingJob
from app.schemas import AnalyzeRequest, JobOut
from app.services.common import active_dataset, job_params
from app.workers.job_runner import create_job, retry_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    job_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[JobOut]:
    q = db.query(ProcessingJob)
    if job_type:
        q = q.filter(ProcessingJob.job_type == job_type)
    if status:
        q = q.filter(ProcessingJob.status == status)
    rows = q.order_by(ProcessingJob.created_at.desc()).limit(min(limit, 200)).all()
    return [_out(db, r) for r in rows]


@router.get("/{job_id}", response_model=JobOut)
def job_detail(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _out(db, job)


@router.post("/{job_id}/retry", response_model=JobOut)
def job_retry(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("failed", "completed"):
        raise HTTPException(status_code=409, detail=f"Cannot retry a {job.status} job")
    job = retry_job(db, job)
    return _out(db, job)


@router.post("/segmentation/run", response_model=JobOut)
def run_segmentation(payload: AnalyzeRequest, db: Session = Depends(get_db)) -> JobOut:
    ds = active_dataset(db, payload.dataset_id)
    if ds is None:
        raise HTTPException(
            status_code=404,
            detail="No imported dataset found — import a CSV before running segmentation",
        )
    running = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.job_type == "segmentation",
            ProcessingJob.status.in_(["pending", "running"]),
        )
        .first()
    )
    if running is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A segmentation job is already {running.status}",
        )
    params = {
        "dataset_id": ds.id,
        "k": payload.k,
        "seed": 42,
        "reference_date": payload.reference_date.isoformat() if payload.reference_date else None,
        "run_id": f"seg-{len(_seg_runs(db)) + 1:03d}",
    }
    job = create_job(db, job_type="segmentation", dataset_id=ds.id, params=params)
    return _out(db, job)


def _seg_runs(db: Session) -> list[ProcessingJob]:
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.job_type == "segmentation")
        .all()
    )


def _out(db: Session, job: ProcessingJob) -> JobOut:
    ds = db.get(Dataset, job.dataset_id) if job.dataset_id else None
    params = job_params(job)
    return JobOut(
        id=job.id,
        dataset_id=job.dataset_id,
        dataset_name=ds.name if ds else None,
        job_type=job.job_type,
        status=job.status,
        stage=job.stage,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        records_processed=job.records_processed,
        error_summary=job.error_summary,
    )
