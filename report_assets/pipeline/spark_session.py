"""Spark session factory with Windows-friendly settings (winutils/hadoop.dll)."""

import os
from pathlib import Path

from pyspark.sql import SparkSession

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


def get_spark(app_name: str = "CustomerIQReportPipeline") -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.driver.extraJavaOptions", _JVM_OPENS)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.python.worker.reuse", "false")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )
