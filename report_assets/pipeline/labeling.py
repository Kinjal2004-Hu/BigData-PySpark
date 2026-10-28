"""Map arbitrary K-Means cluster IDs to interpretable segment labels.

Cluster IDs carry no inherent meaning, so clusters are ranked by a composite
RFM profile score computed on the original (unscaled) cluster averages:

    score = z(avg Frequency) + z(avg Monetary) - z(avg Recency)

Clusters are sorted by descending score and mapped onto the label spectrum:

    Champions > Loyal Customers > Potential Loyalists > New Customers
              > At Risk > Hibernating

Simplified mapping rule: for k clusters the labels are picked at evenly spaced
positions along the six-label spectrum, so smaller k values coarsen the ladder
instead of inventing labels.
"""

SPECTRUM = [
    "Champions",
    "Loyal Customers",
    "Potential Loyalists",
    "New Customers",
    "At Risk",
    "Hibernating",
]


def _z(values: list[float]) -> list[float]:
    n = len(values)
    if n <= 1:
        return [0.0] * n
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    std = var ** 0.5
    if std == 0:
        return [0.0] * n
    return [(v - mean) / std for v in values]


def label_clusters(profiles: list[dict], k: int) -> dict[int, str]:
    """Return {cluster_id: segment_label} for the given cluster profiles."""
    z_rec = _z([p["avg_recency"] for p in profiles])
    z_freq = _z([p["avg_frequency"] for p in profiles])
    z_mon = _z([p["avg_monetary"] for p in profiles])

    ranked = sorted(
        zip(profiles, z_rec, z_freq, z_mon),
        key=lambda t: t[3] + t[2] - t[1],
        reverse=True,
    )

    if k == 1:
        positions = [0]
    else:
        positions = [round(i * (len(SPECTRUM) - 1) / (k - 1)) for i in range(k)]

    mapping: dict[int, str] = {}
    for (profile, *_), pos in zip(ranked, positions):
        mapping[int(profile["prediction"])] = SPECTRUM[pos]
    return mapping
