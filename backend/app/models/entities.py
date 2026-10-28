import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    source_filename: Mapped[str] = mapped_column(String(512))
    stored_path: Mapped[str] = mapped_column(String(1024))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    column_mapping_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|ready|failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_datasets_status", "status"),)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    invoice_no: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    stock_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    invoice_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_return: Mapped[int] = mapped_column(Integer, default=0)
    is_valid: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        Index("ix_transactions_dataset_customer", "dataset_id", "customer_id"),
        Index("ix_transactions_dataset_date", "dataset_id", "invoice_date"),
    )


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(64))
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_purchase: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_purchase: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    total_spend: Mapped[float] = mapped_column(Float, default=0.0)
    avg_order_value: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        UniqueConstraint("dataset_id", "customer_id", name="uq_customer_dataset"),
        Index("ix_customers_dataset_spend", "dataset_id", "total_spend"),
    )


class CustomerRfm(Base):
    __tablename__ = "customer_rfm"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(64))
    recency_days: Mapped[int] = mapped_column(Integer, default=0)
    frequency: Mapped[int] = mapped_column(Integer, default=0)
    monetary: Mapped[float] = mapped_column(Float, default=0.0)
    rfm_score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_id", "customer_id", name="uq_rfm_dataset_customer"),
        Index("ix_rfm_dataset_recency", "dataset_id", "recency_days"),
        Index("ix_rfm_dataset_monetary", "dataset_id", "monetary"),
    )


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # slug, e.g. champions
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    cluster_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_count: Mapped[int] = mapped_column(Integer, default=0)
    pct_of_customers: Mapped[float] = mapped_column(Float, default=0.0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    pct_of_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    avg_spend: Mapped[float] = mapped_column(Float, default=0.0)
    avg_frequency: Mapped[float] = mapped_column(Float, default=0.0)
    avg_recency: Mapped[float] = mapped_column(Float, default=0.0)
    centroid_recency: Mapped[float] = mapped_column(Float, default=0.0)
    centroid_frequency: Mapped[float] = mapped_column(Float, default=0.0)
    centroid_monetary: Mapped[float] = mapped_column(Float, default=0.0)
    analysis_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (Index("ix_segments_dataset", "dataset_id"),)


class SegmentAssignment(Base):
    __tablename__ = "segment_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(64))
    segment_id: Mapped[str] = mapped_column(String(64), index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_id", "customer_id", name="uq_assign_dataset_customer"),
        Index("ix_assign_dataset_segment", "dataset_id", "segment_id"),
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id"), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(32))  # import | segmentation
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending | running | completed | failed
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_jobs_created", "created_at"),)


class DataQualityReport(Base):
    __tablename__ = "data_quality_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    excluded_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_date_rows: Mapped[int] = mapped_column(Integer, default=0)
    missing_customer_rows: Mapped[int] = mapped_column(Integer, default=0)
    negative_quantity_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_price_rows: Mapped[int] = mapped_column(Integer, default=0)
    return_rows: Mapped[int] = mapped_column(Integer, default=0)
    warnings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String(255))
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="success")  # success|failed|info
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
