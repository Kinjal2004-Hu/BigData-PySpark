import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TARGET_FIELDS = [
    "invoice_no",
    "stock_code",
    "description",
    "quantity",
    "invoice_date",
    "unit_price",
    "customer_id",
    "country",
]

# Common header aliases seen in retail exports -> canonical target field.
HEADER_ALIASES = {
    "invoiceNo": "invoice_no",
    "invoiceno": "invoice_no",
    "invoice_no": "invoice_no",
    "invoice": "invoice_no",
    "order_id": "invoice_no",
    "orderno": "invoice_no",
    "stockcode": "stock_code",
    "stock_code": "stock_code",
    "productcode": "stock_code",
    "sku": "stock_code",
    "description": "description",
    "productname": "description",
    "name": "description",
    "quantity": "quantity",
    "qty": "quantity",
    "qtyordered": "quantity",
    "invoicedate": "invoice_date",
    "invoice_date": "invoice_date",
    "date": "invoice_date",
    "orderdate": "invoice_date",
    "timestamp": "invoice_date",
    "unitprice": "unit_price",
    "unit_price": "unit_price",
    "price": "unit_price",
    "customerid": "customer_id",
    "customer_id": "customer_id",
    "customer": "customer_id",
    "userid": "customer_id",
    "country": "country",
    "region": "country",
}


@dataclass
class EngineConfig:
    spark_master: str = field(default_factory=lambda: os.getenv("SPARK_MASTER", "local[2]"))
    spark_app_name: str = field(default_factory=lambda: os.getenv("SPARK_APP_NAME", "CustomerIQ"))
    k: int = field(default_factory=lambda: int(os.getenv("KMEANS_K", "6")))
    seed: int = field(default_factory=lambda: int(os.getenv("KMEANS_SEED", "42")))
    max_iter: int = field(default_factory=lambda: int(os.getenv("KMEANS_MAX_ITER", "50")))
    shuffle_partitions: int = field(
        default_factory=lambda: int(os.getenv("SPARK_SHUFFLE_PARTITIONS", "8"))
    )
    reference_date: str | None = field(default_factory=lambda: os.getenv("REFERENCE_DATE") or None)
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'customeriq.db'}")
    )


def get_engine_config() -> EngineConfig:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    return EngineConfig()


def detect_mapping(columns: list[str]) -> dict[str, str]:
    """Map target_field -> source column using header aliases (case-insensitive)."""
    lower_map = {c.lower().replace(" ", ""): c for c in columns}
    mapping: dict[str, str] = {}
    for col in columns:
        key = col.lower().replace(" ", "")
        target = HEADER_ALIASES.get(key)
        if target and target not in mapping.values():
            mapping[target] = col
    # second pass for remaining aliases with compacted keys
    for target in TARGET_FIELDS:
        if target in mapping:
            continue
        for alias, t in HEADER_ALIASES.items():
            if t == target and alias in lower_map:
                mapping[target] = lower_map[alias]
                break
    return mapping


def load_mapping(path: str | Path) -> dict[str, str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if k in TARGET_FIELDS and v}
