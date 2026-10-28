from dataclasses import dataclass

from pyspark.ml.clustering import KMeans, KMeansModel
from pyspark.ml.evaluation import ClusteringEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.ml.linalg import Vectors
from pyspark.sql import DataFrame
from pyspark.sql import functions as F


@dataclass
class ClusterResult:
    predictions: DataFrame
    silhouette: float
    k: int
    seed: int
    centroids: list[dict]
    feature_stats: dict
    model: KMeansModel | None = None
    max_iter: int | None = None


def _prepare_features(rfm: DataFrame) -> DataFrame:
    """Assemble, log-transform skewed features and scale with MLlib StandardScaler.

    Monetary and frequency are strongly right-skewed in retail data, so
    log1p is applied before scaling. Recency is used raw (already roughly
    uniform over the analysis window).
    """
    df = rfm.withColumn("log_freq", F.log1p(F.col("frequency")))
    df = df.withColumn("log_mon", F.greatest(F.col("monetary"), F.lit(0.0)).alias("x") * F.lit(1.0))
    df = df.withColumn("log_mon", F.log1p(F.col("log_mon")))
    assembler = VectorAssembler(
        inputCols=["recency", "log_freq", "log_mon"],
        outputCol="features_raw",
        handleInvalid="skip",
    )
    df = assembler.transform(df)
    scaler = StandardScaler(inputCol="features_raw", outputCol="features", withMean=True, withStd=True)
    model = scaler.fit(df)
    return model.transform(df), model


def fit_kmeans(
    rfm: DataFrame,
    k: int = 6,
    seed: int = 42,
    max_iter: int = 50,
) -> ClusterResult:
    """Fit Spark MLlib KMeans on scaled RFM features and evaluate silhouette."""
    featured, scaler_model = _prepare_features(rfm)

    kmeans = KMeans(
        featuresCol="features",
        predictionCol="cluster",
        k=k,
        seed=seed,
        maxIter=max_iter,
        initMode="k-means||",
        tol=1e-4,
    )
    model = kmeans.fit(featured)
    predictions = model.transform(featured)

    evaluator = ClusteringEvaluator(
        featuresCol="features", predictionCol="cluster", metricName="silhouette"
    )
    silhouette = float(evaluator.evaluate(predictions))

    raw_centers = model.clusterCenters()
    scaled_centers = scaler_model.mean  # features were centered by scaler
    # Un-scale centroids (withMean/withStd): x = center * std + mean
    std = scaler_model.std
    mean = scaler_model.mean
    centroids = []
    for cid, vec in enumerate(raw_centers):
        rec = vec[0] * std[0] + mean[0] if std[0] != 0 else vec[0]
        lf = vec[1] * std[1] + mean[1] if std[1] != 0 else vec[1]
        lm = vec[2] * std[2] + mean[2] if std[2] != 0 else vec[2]
        centroids.append(
            {
                "cluster": cid,
                "recency": round(float(rec), 3),
                "log_frequency": round(float(lf), 4),
                "log_monetary": round(float(lm), 4),
                "frequency_est": round(float(max(lf - 1.0, 0.0)), 3),
                "monetary_est": round(float(max(lm - 1.0, 0.0)), 2),
            }
        )

    return ClusterResult(
        predictions=predictions,
        silhouette=silhouette,
        k=k,
        seed=seed,
        centroids=centroids,
        feature_stats={"scaler_mean": [float(x) for x in mean], "scaler_std": [float(x) for x in std]},
        model=model,
        max_iter=max_iter,
    )


def assign_segment_labels(rfm_with_clusters: DataFrame) -> tuple[DataFrame, dict[int, dict]]:
    """Map arbitrary cluster ids to human-readable segment labels.

    Simplified, documented rule set evaluated per cluster profile
    (cluster-level means of recency / frequency / monetary):

      Champions          - low recency, highest frequency+monetary
      Loyal Customers    - frequent + high monetary, moderate recency
      Potential Loyalists- recent, decent monetary, moderate frequency
      New Customers      - very recent, low frequency so far
      At Risk            - historically valuable but high recency
      Hibernating        - high recency, low frequency/monetary

    Clusters are ranked on a composite value score; labels are assigned
    in order so each label is used at most once. Clusters whose profile
    does not support a rule keep a positional label like "Segment N".
    """
    stats = (
        rfm_with_clusters.groupBy("cluster")
        .agg(
            F.count("*").alias("n"),
            F.avg("recency").alias("avg_rec"),
            F.avg("frequency").alias("avg_freq"),
            F.avg("monetary").alias("avg_mon"),
        )
        .collect()
    )
    profiles = [
        {
            "cluster": int(r["cluster"]),
            "n": int(r["n"]),
            "avg_rec": float(r["avg_rec"]),
            "avg_freq": float(r["avg_freq"]),
            "avg_mon": float(r["avg_mon"]),
        }
        for r in stats
    ]
    if not profiles:
        return rfm_with_clusters, {}

    total = sum(p["n"] for p in profiles) or 1
    min_rec = min(p["avg_rec"] for p in profiles)
    max_rec = max(p["avg_rec"] for p in profiles)
    min_freq = min(p["avg_freq"] for p in profiles)
    max_freq = max(p["avg_freq"] for p in profiles)
    min_mon = min(p["avg_mon"] for p in profiles)
    max_mon = max(p["avg_mon"] for p in profiles)

    def norm(v, lo, hi):
        return 0.0 if hi == lo else (v - lo) / (hi - lo)

    for p in profiles:
        p["rec_n"] = norm(p["avg_rec"], min_rec, max_rec)          # 0 fresh .. 1 stale
        p["freq_n"] = norm(p["avg_freq"], min_freq, max_freq)
        p["mon_n"] = norm(p["avg_mon"], min_mon, max_mon)
        p["value_score"] = p["freq_n"] * 0.5 + p["mon_n"] * 0.5 - p["rec_n"] * 0.4

    # Rank by value; assign labels by combined rank/recency rules.
    by_value = sorted(profiles, key=lambda p: -p["value_score"])
    by_recency = sorted(profiles, key=lambda p: p["avg_rec"])

    labels: dict[int, str] = {}

    def try_label(pred, name):
        for p in by_value:
            if p["cluster"] not in labels and pred(p):
                labels[p["cluster"]] = name
                return

    n = len(profiles)
    # Rule 1: Champions = best value score AND fresher than median recency
    median_rec = sorted(p["avg_rec"] for p in profiles)[n // 2]
    median_mon = sorted(p["avg_mon"] for p in profiles)[n // 2]
    try_label(lambda p: p["avg_rec"] <= median_rec, "Champions")
    # Rule 2: New Customers = freshest remaining with low frequency
    for p in by_recency:
        if p["cluster"] not in labels and p["freq_n"] <= 0.4:
            labels[p["cluster"]] = "New Customers"
            break
    # Rule 3: Potential Loyalists = fresher than median, moderate value
    try_label(lambda p: p["avg_rec"] <= median_rec, "Potential Loyalists")
    # Rule 4: Loyal Customers = high frequency, still active
    try_label(lambda p: p["freq_n"] >= 0.4 and p["avg_rec"] <= median_rec, "Loyal Customers")
    # Rule 5: At Risk = stale but historically valuable (monetary >= median)
    try_label(lambda p: p["avg_rec"] >= median_rec and p["avg_mon"] >= median_mon, "At Risk")
    # Rule 6: Hibernating = stalest remaining
    for p in reversed(by_recency):
        if p["cluster"] not in labels:
            labels[p["cluster"]] = "Hibernating"
            break
    # Leftovers: profile-supported fallbacks, positional label as last resort
    for p in sorted(profiles, key=lambda p: p["cluster"]):
        if p["cluster"] not in labels:
            if p["avg_rec"] >= median_rec:
                labels[p["cluster"]] = "Dormant"
            elif p["value_score"] >= 0.5:
                labels[p["cluster"]] = "Emerging"
            else:
                labels[p["cluster"]] = f"Segment {p['cluster'] + 1}"

    label_meta = {}
    for p in profiles:
        label = labels[p["cluster"]]
        pct = 100.0 * p["n"] / total
        label_meta[p["cluster"]] = {
            "label": label,
            "customers": p["n"],
            "pct": round(pct, 2),
            "avg_recency": round(p["avg_rec"], 1),
            "avg_frequency": round(p["avg_freq"], 2),
            "avg_monetary": round(p["avg_mon"], 2),
        }

    mapping_expr = F.create_map(
        *[x for cid, lab in labels.items() for x in (F.lit(str(cid)), F.lit(lab))]
    )
    result = rfm_with_clusters.withColumn(
        "segment_name", mapping_expr[F.col("cluster").cast("string")]
    )
    return result, label_meta


def save_model(model: KMeansModel, path: str) -> None:
    model.write().overwrite().save(path)


def load_model(path: str) -> KMeansModel:
    return KMeansModel.load(path)
