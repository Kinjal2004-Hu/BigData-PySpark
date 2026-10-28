"""K-Means customer segmentation with Spark MLlib.

Pipeline: log1p transform on the right-skewed Frequency/Monetary features ->
VectorAssembler -> StandardScaler (withMean/withStd) -> KMeans.
The random seed is fixed (42) so results are reproducible. k is selected by
maximising the silhouette score over a configurable range.
"""

from dataclasses import dataclass

from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import ClusteringEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.sql import DataFrame, functions as F

RANDOM_SEED = 42
FEATURE_COLS = ["Recency", "log_Frequency", "log_Monetary"]


@dataclass
class ClusteringResult:
    assignments: DataFrame          # customer_id + RFM + prediction + scaled features
    silhouette: float
    best_k: int
    k_scores: dict                  # k -> silhouette
    centroids_scaled: list          # list[list[float]] in scaled feature space
    scaler_mean: list               # mean of raw feature columns
    scaler_std: list                # std of raw feature columns
    model: object = None            # fitted pyspark.ml.clustering.KMeansModel


def evaluate_ks(rfm: DataFrame, k_range=range(3, 9), seed: int = RANDOM_SEED) -> dict:
    """Return {k: silhouette} for each candidate cluster count."""
    scored = _with_features(rfm)
    scores: dict[int, float] = {}
    evaluator = ClusteringEvaluator(
        featuresCol="features", predictionCol="prediction", metricName="silhouette"
    )
    for k in k_range:
        model = KMeans(k=k, seed=seed, featuresCol="features", maxIter=100).fit(scored)
        preds = model.transform(scored)
        scores[k] = evaluator.evaluate(preds)
    return scores


def fit_kmeans(rfm: DataFrame, k: int = 6, seed: int = RANDOM_SEED) -> ClusteringResult:
    """Fit K-Means for a fixed k and return assignments plus diagnostics."""
    scored, mean_vec, std_vec = _with_features(rfm, return_scaler_stats=True)
    model = KMeans(k=k, seed=seed, featuresCol="features", maxIter=100).fit(scored)
    preds = model.transform(scored)
    evaluator = ClusteringEvaluator(
        featuresCol="features", predictionCol="prediction", metricName="silhouette"
    )
    silhouette = evaluator.evaluate(preds)

    return ClusteringResult(
        assignments=preds,
        silhouette=silhouette,
        best_k=k,
        k_scores={},
        centroids_scaled=[
            c.toArray().tolist() if hasattr(c, "toArray") else list(c)
            for c in model.clusterCenters()
        ],
        scaler_mean=mean_vec,
        scaler_std=std_vec,
        model=model,
    )


def cluster_profile(assignments: DataFrame) -> list[dict]:
    """Per-cluster averages of the original (unscaled) RFM metrics."""
    rows = (
        assignments.groupBy("prediction")
        .agg(
            F.count("*").alias("customers"),
            F.avg("Recency").alias("avg_recency"),
            F.avg("Frequency").alias("avg_frequency"),
            F.avg("Monetary").alias("avg_monetary"),
            F.sum("Monetary").alias("revenue"),
        )
        .orderBy("prediction")
        .collect()
    )
    return [r.asDict() for r in rows]


def _with_features(rfm: DataFrame, return_scaler_stats: bool = False):
    """Add log1p feature columns, assemble and scale them."""
    featured = (
        rfm
        .withColumn("log_Frequency", F.log1p(F.col("Frequency")))
        .withColumn("log_Monetary", F.log1p(F.col("Monetary")))
    )
    assembler = VectorAssembler(
        inputCols=FEATURE_COLS, outputCol="features_raw", handleInvalid="skip"
    )
    scaler = StandardScaler(
        inputCol="features_raw", outputCol="features", withMean=True, withStd=True
    )
    assembled = assembler.transform(featured)
    scaler_model = scaler.fit(assembled)
    scaled = scaler_model.transform(assembled)

    if return_scaler_stats:
        return (
            scaled,
            scaler_model.mean.toArray().tolist(),
            scaler_model.std.toArray().tolist(),
        )
    return scaled
