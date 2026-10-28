"""CustomerIQ Spark pipeline.

Run as a subprocess by the backend job runner:

    python -m data_engine.pipeline --job <job_id>

Stages: import (validate + persist) and segmentation (RFM + K-Means).
Updates the processing_jobs row in SQLite as it progresses so the API
can report real status without fake progress percentages.
"""
import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import text  # noqa: E402


def _db_url() -> str:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip() == "DATABASE_URL" and v.strip():
                    return v.strip()
    return f"sqlite:///{ROOT / 'data' / 'customeriq.db'}"


def set_job(job_id: str, **fields) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(_db_url())
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        db.execute(
            text(f"UPDATE processing_jobs SET {sets} WHERE id = :id"),
            {**fields, "id": job_id},
        )
        db.commit()
    finally:
        db.close()


def log(job_id: str, message: str) -> None:
    print(f"[job {job_id}] {message}", flush=True)
    try:
        set_job(job_id, stage=message[:120])
    except Exception:
        pass


def stage_import(job_id: str, params: dict) -> None:
    import shutil

    from data_engine.config import detect_mapping, get_engine_config
    from data_engine.ingestion.validation import validate_and_clean
    from data_engine.session import get_spark
    from data_engine.storage.writer import (
        save_quality_report,
        write_transactions,
        write_valid_parquet,
    )

    cfg = get_engine_config()
    dataset_id = params["dataset_id"]
    source_path = params["source_path"]
    mapping = params.get("column_mapping") or detect_mapping([])
    dedupe_policy = params.get("dedupe_policy", "keep_first")

    log(job_id, "Starting Spark session")
    spark = get_spark(f"CustomerIQ-import-{job_id}")
    try:
        log(job_id, "Reading source CSV")
        raw = (
            spark.read.option("header", "true")
            .option("multiLine", "false")
            .option("escape", '"')
            .option("enforceSchema", "false")
            .csv(source_path)
        )
        # rename mapped source columns to canonical target names
        rename = {src: tgt for tgt, src in mapping.items() if src in raw.columns}
        for tgt in ("invoice_no", "stock_code", "description", "quantity",
                    "invoice_date", "unit_price", "customer_id", "country"):
            if tgt not in rename.values():
                # create null column so downstream references resolve
                from pyspark.sql import functions as F
                raw = raw.withColumn(tgt, F.lit(None).cast("string"))
        raw = raw.select(list(mapping.values()) if mapping else raw.columns)
        for tgt, src in mapping.items():
            if src != tgt:
                raw = raw.withColumnRenamed(src, tgt)

        log(job_id, "Validating rows and computing data quality statistics")
        clean, stats = validate_and_clean(raw)
        if dedupe_policy == "keep_all":
            stats.warnings += ("Dedupe policy 'keep_all' selected: duplicates retained.",)

        log(job_id, f"Writing processed parquet ({stats.valid_rows} valid rows)")
        processed_dir = cfg_process_dir() / dataset_id
        write_valid_parquet(clean, str(processed_dir))

        log(job_id, "Persisting transactions to database")
        write_transactions(clean, dataset_id)

        log(job_id, "Recording data quality report")
        save_quality_report(dataset_id, job_id, stats)

        log(job_id, "Import completed")
        set_job(
            job_id,
            status="completed",
            records_processed=stats.total_rows,
            finished_at=datetime.utcnow().isoformat(sep=" ", timespec="seconds"),
            stage="Completed",
            error_summary=None,
        )
    finally:
        spark.stop()


def cfg_process_dir() -> Path:
    from data_engine.config import get_engine_config  # noqa: F401
    p = ROOT / "data" / "processed"
    p.mkdir(parents=True, exist_ok=True)
    return p


def stage_segmentation(job_id: str, params: dict) -> None:
    import shutil

    from data_engine.clustering.kmeans import (
        assign_segment_labels,
        fit_kmeans,
        save_model,
    )
    from data_engine.config import get_engine_config
    from data_engine.features.rfm import add_rfm_scores, compute_rfm, latest_valid_date
    from data_engine.session import get_spark
    from data_engine.storage.writer import read_valid_parquet, save_segment_results

    cfg = get_engine_config()
    dataset_id = params["dataset_id"]
    k = int(params.get("k") or cfg.k)
    seed = int(params.get("seed") or cfg.seed)
    ref_date_str = params.get("reference_date")
    model_version = params.get("run_id") or job_id

    log(job_id, "Starting Spark session")
    spark = get_spark(f"CustomerIQ-segmentation-{job_id}")
    try:
        log(job_id, "Loading processed dataset")
        clean = read_valid_parquet(str(cfg_process_dir() / dataset_id), spark)

        if ref_date_str:
            from pyspark.sql import functions as F
            from datetime import datetime as dt

            ref_date = dt.fromisoformat(ref_date_str)
            log(job_id, f"Using configured reference date {ref_date.date()}")
        else:
            mx = latest_valid_date(clean)
            if mx is None:
                raise ValueError(
                    "No valid transactions available for segmentation. Run an import first."
                )
            ref_date = mx + timedelta(days=1)
            log(job_id, f"Reference date = latest valid purchase + 1 day ({ref_date.date()})")

        log(job_id, "Computing RFM metrics")
        rfm = compute_rfm(clean, ref_date)
        rfm = add_rfm_scores(rfm)
        rfm.persist()
        n_customers = rfm.count()
        if n_customers == 0:
            raise ValueError("No customers with valid purchases — cannot segment.")
        log(job_id, f"RFM computed for {n_customers} customers")

        log(job_id, f"Fitting K-Means (k={k}, seed={seed})")
        result = fit_kmeans(rfm, k=k, seed=seed, max_iter=cfg.max_iter)
        log(job_id, f"Silhouette score = {result.silhouette:.4f}")

        log(job_id, "Assigning segment labels from cluster profiles")
        labeled, label_meta = assign_segment_labels(result.predictions)

        log(job_id, "Persisting segment results")
        model_dir = ROOT / "data" / "models" / dataset_id / f"kmeans_{model_version}"
        model_dir.mkdir(parents=True, exist_ok=True)

        _save_kmeans_artifacts(result, label_meta, k, seed, ref_date, job_id, model_dir)

        save_segment_results(
            dataset_id=dataset_id,
            labeled=labeled,
            label_meta=label_meta,
            run_id=model_version,
            silhouette=result.silhouette,
            k=k,
            seed=seed,
            ref_date=ref_date,
            centroids=result.centroids,
        )
        log(job_id, "Segmentation completed")
        set_job(
            job_id,
            status="completed",
            records_processed=n_customers,
            finished_at=datetime.utcnow().isoformat(sep=" ", timespec="seconds"),
            stage="Completed",
            error_summary=None,
        )
    finally:
        spark.stop()


_last_model_holder: dict = {}


def _save_kmeans_artifacts(result, label_meta, k, seed, ref_date, job_id, model_dir: Path) -> None:
    model_path = model_dir / "spark_model"
    if result.model is not None:
        result.model.write().overwrite().save(str(model_path))
    meta = {
        "job_id": job_id,
        "k": k,
        "seed": seed,
        "max_iter": getattr(result, "max_iter", None),
        "silhouette": round(result.silhouette, 4),
        "reference_date": ref_date.isoformat(sep=" ", timespec="seconds"),
        "feature_stats": result.feature_stats,
        "centroids": result.centroids,
        "segments": label_meta,
        "trained_at": datetime.utcnow().isoformat(sep=" ", timespec="seconds"),
    }
    (model_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="CustomerIQ Spark pipeline")
    parser.add_argument("--job", required=True, help="processing job id")
    args = parser.parse_args()
    job_id = args.job

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(_db_url())
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        row = db.execute(
            text("SELECT job_type, dataset_id, params_json FROM processing_jobs WHERE id = :id"),
            {"id": job_id},
        ).first()
        if row is None:
            print(f"job {job_id} not found", file=sys.stderr)
            return 2
        job_type, job_dataset_id, params_json = row
        params = json.loads(params_json) if params_json else {}
        params.setdefault("dataset_id", job_dataset_id)
    finally:
        db.close()

    set_job(
        job_id,
        status="running",
        started_at=datetime.utcnow().isoformat(sep=" ", timespec="seconds"),
        stage="Starting",
    )
    try:
        if job_type == "import":
            stage_import(job_id, params)
        elif job_type == "segmentation":
            stage_segmentation(job_id, params)
        else:
            raise ValueError(f"Unknown job type: {job_type}")
        return 0
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        summary = f"{type(exc).__name__}: {exc}"
        try:
            set_job(
                job_id,
                status="failed",
                finished_at=datetime.utcnow().isoformat(sep=" ", timespec="seconds"),
                error_summary=summary[:2000],
                stage="Failed",
            )
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
