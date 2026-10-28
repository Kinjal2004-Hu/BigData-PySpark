from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 25


class ErrorBody(BaseModel):
    detail: str
    code: str = "error"
    extra: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
    active_dataset: str | None = None
    last_processed: datetime | None = None


class KpiCard(BaseModel):
    label: str
    value: float | int | str | None
    formatted: str
    delta: float | None = None  # None when no historical comparison exists
    delta_label: str | None = None


class DashboardSummary(BaseModel):
    active_dataset: str | None
    total_customers: int
    total_revenue: float
    avg_customer_value: float
    repeat_purchase_rate: float | None
    at_risk_customers: int | None
    last_processing_status: str | None
    last_processed_at: datetime | None
    kpis: list[KpiCard]


class RevenuePoint(BaseModel):
    period: str
    revenue: float
    orders: int
    customers: int


class SegmentDistributionItem(BaseModel):
    segment_id: str
    name: str
    customers: int
    pct: float


class SegmentRevenueItem(BaseModel):
    segment_id: str
    name: str
    revenue: float
    pct: float


class SegmentOut(BaseModel):
    id: str
    cluster_id: int
    name: str
    description: str | None
    customer_count: int
    pct_of_customers: float
    revenue: float
    pct_of_revenue: float
    avg_spend: float
    avg_frequency: float
    avg_recency: float
    centroid_recency: float
    centroid_frequency: float
    centroid_monetary: float


class CustomerRow(BaseModel):
    customer_id: str
    country: str | None
    last_purchase: datetime | None
    recency_days: int | None
    frequency: int | None
    monetary: float | None
    segment_id: str | None
    segment_name: str | None
    rfm_score: int | None


class CustomerDetail(CustomerRow):
    first_purchase: datetime | None
    order_count: int
    total_spend: float
    avg_order_value: float
    cluster_id: int | None


class TransactionOut(BaseModel):
    invoice_no: str | None
    invoice_date: datetime | None
    stock_code: str | None
    description: str | None
    quantity: int
    unit_price: float
    revenue: float
    country: str | None


class DatasetOut(BaseModel):
    id: str
    name: str
    source_filename: str
    file_size: int
    total_rows: int
    valid_rows: int
    status: str
    created_at: datetime
    schema_version: int


class UploadPreview(BaseModel):
    dataset_id: str
    filename: str
    columns: list[str]
    rows: list[list[Any]]
    detected_mapping: dict[str, str]
    file_size: int


class JobOut(BaseModel):
    id: str
    dataset_id: str | None
    dataset_name: str | None
    job_type: str
    status: str
    stage: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    records_processed: int
    error_summary: str | None


class QualityReportOut(BaseModel):
    total_rows: int
    valid_rows: int
    excluded_rows: int
    duplicate_rows: int
    invalid_date_rows: int
    missing_customer_rows: int
    negative_quantity_rows: int
    invalid_price_rows: int
    return_rows: int
    warnings: list[str]


class ActivityOut(BaseModel):
    id: int
    event: str
    target: str | None
    status: str
    created_at: datetime


class AnalyzeRequest(BaseModel):
    dataset_id: str | None = None
    k: int = Field(default=6, ge=2, le=20)
    reference_date: datetime | None = None


class ConfirmImportRequest(BaseModel):
    dataset_id: str
    column_mapping: dict[str, str]  # target_field -> source_column
    dedupe_policy: str = "keep_first"  # keep_first | keep_all
    name: str | None = None
