"""Dataset upload, preview, mapping confirmation.

Large files are streamed to disk in chunks (never loaded fully into
memory); preview reads only the first N rows.
"""
import csv
import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import ActivityLog, DataQualityReport, Dataset
from app.schemas import ConfirmImportRequest, DatasetOut, QualityReportOut, UploadPreview
from app.workers.job_runner import create_job

router = APIRouter(prefix="/datasets", tags=["datasets"])

REQUIRED_TARGETS = [
    "invoice_no", "quantity", "invoice_date", "unit_price", "customer_id",
]
OPTIONAL_TARGETS = ["stock_code", "description", "country"]


def _detect(columns: list[str]) -> dict[str, str]:
    from data_engine.config import detect_mapping

    return detect_mapping(columns)


@router.get("", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_db)) -> list[DatasetOut]:
    rows = db.query(Dataset).order_by(Dataset.created_at.desc()).all()
    return [_out(r) for r in rows]


@router.post("/upload", response_model=UploadPreview)
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadPreview:
    settings = get_settings()
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    dataset_id = uuid.uuid4().hex
    raw_dir = settings.raw_dir / dataset_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / "source.csv"

    # stream to disk in 1 MB chunks; enforce size limit while streaming
    size = 0
    limit = settings.max_upload_bytes
    try:
        with open(dest, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {settings.max_upload_mb} MB limit",
                    )
                out.write(chunk)
    except HTTPException:
        shutil.rmtree(raw_dir, ignore_errors=True)
        raise
    finally:
        await file.close()

    if size == 0:
        shutil.rmtree(raw_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # bounded preview: first N rows only
    preview_rows = settings.preview_rows
    columns: list[str] = []
    rows: list[list] = []
    try:
        with open(dest, "r", encoding="utf-8-sig", newline="", errors="replace") as fh:
            reader = csv.reader(fh)
            for i, row in enumerate(reader):
                if i == 0:
                    columns = [c.strip() for c in row]
                else:
                    rows.append(row[: len(columns)])
                if len(rows) >= preview_rows:
                    break
    except UnicodeDecodeError:
        shutil.rmtree(raw_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="File is not valid UTF-8/ASCII CSV")

    if not columns or len(columns) < 2:
        shutil.rmtree(raw_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="CSV header missing or too few columns")

    mapping = _detect(columns)
    missing = [t for t in REQUIRED_TARGETS if t not in mapping]

    ds = Dataset(
        id=dataset_id,
        name=file.filename or "upload.csv",
        source_filename=file.filename or "upload.csv",
        stored_path=str(dest),
        file_size=size,
        status="pending",
        column_mapping_json=json.dumps({"missing_required": missing, "auto": mapping}),
    )
    db.add(ds)
    db.add(
        ActivityLog(
            event="CSV uploaded",
            target=file.filename,
            status="success",
            detail=f"{size} bytes, {len(columns)} columns",
        )
    )
    db.commit()

    return UploadPreview(
        dataset_id=dataset_id,
        filename=file.filename or "upload.csv",
        columns=columns,
        rows=rows,
        detected_mapping=mapping,
        file_size=size,
    )


@router.post("/confirm", response_model=DatasetOut)
def confirm_import(payload: ConfirmImportRequest, db: Session = Depends(get_db)) -> DatasetOut:
    ds = db.get(Dataset, payload.dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not Path(ds.stored_path).exists():
        raise HTTPException(status_code=400, detail="Uploaded file no longer exists on server")

    mapping = payload.column_mapping
    missing = [t for t in REQUIRED_TARGETS if not mapping.get(t)]
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Missing required field mapping",
                "missing": missing,
            },
        )
    if payload.dedupe_policy not in ("keep_first", "keep_all"):
        raise HTTPException(status_code=422, detail="dedupe_policy must be keep_first or keep_all")

    ds.column_mapping_json = json.dumps(mapping)
    if payload.name:
        ds.name = payload.name
    db.commit()

    job = create_job(
        db,
        job_type="import",
        dataset_id=ds.id,
        params={
            "source_path": ds.stored_path,
            "column_mapping": mapping,
            "dedupe_policy": payload.dedupe_policy,
        },
    )
    return _out(ds)


@router.post("/load-sample", response_model=UploadPreview)
def load_sample_dataset(db: Session = Depends(get_db)) -> UploadPreview:
    """Load the bundled deterministic demo CSV (same flow as a manual upload)."""
    import shutil

    from app.core.config import ROOT_DIR

    demo = ROOT_DIR / "data" / "raw" / "demo_online_retail.csv"

    class _F:  # minimal UploadFile stand-in
        filename = demo.name

    dataset_id = uuid.uuid4().hex
    raw_dir = settings.raw_dir / dataset_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / "source.csv"
    shutil.copyfile(demo, dest)
    size = demo.stat().st_size

    columns: list[str] = []
    rows: list[list] = []
    with open(dest, "r", encoding="utf-8-sig", newline="", errors="replace") as fh:
        reader = csv.reader(fh)
        for i, row in enumerate(reader):
            if i == 0:
                columns = [c.strip() for c in row]
            else:
                rows.append(row[: len(columns)])
            if len(rows) >= settings.preview_rows:
                break

    mapping = _detect(columns)
    missing = [t for t in REQUIRED_TARGETS if t not in mapping]
    ds = Dataset(
        id=dataset_id,
        name=demo.name,
        source_filename=demo.name,
        stored_path=str(dest),
        file_size=size,
        status="pending",
        column_mapping_json=json.dumps({"missing_required": missing, "auto": mapping}),
    )
    db.add(ds)
    db.add(ActivityLog(event="Demo dataset loaded", target=demo.name, status="success",
                       detail=f"{size} bytes, {len(columns)} columns"))
    db.commit()
    return UploadPreview(
        dataset_id=dataset_id,
        filename=demo.name,
        columns=columns,
        rows=rows,
        detected_mapping=mapping,
        file_size=size,
    )


@router.get("/{dataset_id}/quality", response_model=QualityReportOut)
def quality_report(dataset_id: str, db: Session = Depends(get_db)) -> QualityReportOut:
    report = (
        db.query(DataQualityReport)
        .filter(DataQualityReport.dataset_id == dataset_id)
        .order_by(DataQualityReport.created_at.desc())
        .first()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="No quality report for this dataset yet")
    warnings: list[str] = []
    if report.warnings_json:
        try:
            warnings = json.loads(report.warnings_json)
        except json.JSONDecodeError:
            warnings = []
    return QualityReportOut(
        total_rows=report.total_rows,
        valid_rows=report.valid_rows,
        excluded_rows=report.excluded_rows,
        duplicate_rows=report.duplicate_rows,
        invalid_date_rows=report.invalid_date_rows,
        missing_customer_rows=report.missing_customer_rows,
        negative_quantity_rows=report.negative_quantity_rows,
        invalid_price_rows=report.invalid_price_rows,
        return_rows=report.return_rows,
        warnings=warnings,
    )


def _out(ds: Dataset) -> DatasetOut:
    return DatasetOut(
        id=ds.id,
        name=ds.name,
        source_filename=ds.source_filename,
        file_size=ds.file_size,
        total_rows=ds.total_rows,
        valid_rows=ds.valid_rows,
        status=ds.status,
        created_at=ds.created_at,
        schema_version=ds.schema_version,
    )
