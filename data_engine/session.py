import os
from pathlib import Path

from pyspark.sql import SparkSession

from data_engine.config import get_engine_config

HADOOP_HOME_DIR = Path(os.environ.get("HADOOP_HOME", r"C:\hadoop"))

_JVM_OPENS = " ".join(
    [
        "--add-opens=java.base/java.lang=ALL-UNNAMED",
        "--add-opens=java.base/java.lang.invoke=ALL-UNNAMED",
        "--add-opens=java.base/java.io=ALL-UNNAMED",
        "--add-opens=java.base/java.nio=ALL-UNNAMED",
        "--add-opens=java.base/java.util=ALL-UNNAMED",
        "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED",
        f"-Dhadoop.home.dir={HADOOP_HOME_DIR.as_posix()}",
        f"-Djava.library.path={HADOOP_HOME_DIR.as_posix()}/bin",
    ]
)


def get_spark(app_name: str | None = None) -> SparkSession:
    """Spark session with Windows-friendly settings (winutils/hadoop.dll)."""
    os.environ.setdefault("HADOOP_HOME", str(HADOOP_HOME_DIR))
    cfg = get_engine_config()
    builder = (
        SparkSession.builder.master(cfg.spark_master)
        .appName(app_name or cfg.spark_app_name)
        .config("spark.driver.extraJavaOptions", _JVM_OPENS)
        .config("spark.sql.shuffle.partitions", str(cfg.shuffle_partitions))
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.ansi.enabled", "false")  # dirty CSV: bad casts/dates -> NULL
        .config("spark.ui.enabled", "false")
        .config("spark.python.worker.reuse", "true")
        .config("spark.sql.parquet.compression.codec", "snappy")
    )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
