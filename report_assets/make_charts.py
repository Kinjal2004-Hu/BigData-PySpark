"""Generate the three report figures from the persisted RFM + segment output.

Inputs : report_assets/data/processed/customer_rfm.csv (small, bounded export)
Outputs: report_assets/fig1_segment_distribution.png
         report_assets/fig2_revenue_by_segment.png
         report_assets/fig3_rfm_profiles.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ASSETS = Path(__file__).resolve().parent
INPUT = ASSETS / "data" / "processed" / "customer_rfm.csv"

SEGMENT_COLORS = {
    "Champions": "#315EFB",
    "Loyal Customers": "#16856B",
    "Potential Loyalists": "#4E8F7B",
    "New Customers": "#C58A25",
    "At Risk": "#D14D5B",
    "Hibernating": "#98A2B3",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8,
    "axes.edgecolor": "#E5E7EB",
    "axes.labelcolor": "#172B4D",
    "axes.titlesize": 9,
    "axes.titleweight": "bold",
    "xtick.color": "#667085",
    "ytick.color": "#667085",
    "figure.dpi": 200,
})


def _clean(ax, grid_axis="x"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis, color="#E5E7EB", linewidth=0.6, alpha=0.9)
    ax.set_axisbelow(True)


def main() -> None:
    df = pd.read_csv(INPUT, dtype={"CustomerID": str})

    summary = (
        df.groupby("Segment")
        .agg(customers=("CustomerID", "count"), revenue=("Monetary", "sum"),
             avg_recency=("Recency", "mean"), avg_frequency=("Frequency", "mean"),
             avg_monetary=("Monetary", "mean"))
        .sort_values("customers", ascending=False)
    )
    overall = df[["Recency", "Frequency", "Monetary"]].mean()

    # ---- Fig 1: customer segment distribution (5.5 x 2.75 in) -----------
    fig, ax = plt.subplots(figsize=(5.5, 2.75))
    colors = [SEGMENT_COLORS.get(s, "#667085") for s in summary.index]
    bars = ax.bar(summary.index, summary["customers"], color=colors, width=0.62)
    for bar, value in zip(bars, summary["customers"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 3,
                f"{value}", ha="center", va="bottom", fontsize=7.5, color="#172B4D")
    ax.set_ylabel("Customers")
    ax.set_title("Customer Distribution by Segment")
    ax.tick_params(axis="x", rotation=18)
    ax.set_ylim(0, summary["customers"].max() * 1.18)
    _clean(ax, grid_axis="y")
    fig.tight_layout()
    fig.savefig(ASSETS / "fig1_segment_distribution.png")
    plt.close(fig)

    # ---- Fig 2: revenue by segment (6.0 x 3.0 in) -----------------------
    rev = df.groupby("Segment")["Monetary"].sum().sort_values()
    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    colors = [SEGMENT_COLORS.get(s, "#667085") for s in rev.index]
    bars = ax.barh(rev.index, rev.values, color=colors, height=0.6)
    for bar, value in zip(bars, rev.values):
        ax.text(value + rev.max() * 0.012, bar.get_y() + bar.get_height() / 2,
                f"{value:,.0f}", ha="left", va="center", fontsize=7.5, color="#172B4D")
    ax.set_xlabel("Revenue")
    ax.set_title("Total Revenue by Customer Segment")
    ax.set_xlim(0, rev.max() * 1.16)
    _clean(ax, grid_axis="x")
    fig.tight_layout()
    fig.savefig(ASSETS / "fig2_revenue_by_segment.png")
    plt.close(fig)

    # ---- Fig 3: RFM profiles by segment (5.5 x 3.4375 in) ---------------
    idx = pd.DataFrame({
        "Recency": summary["avg_recency"] / overall["Recency"] * 100,
        "Frequency": summary["avg_frequency"] / overall["Frequency"] * 100,
        "Monetary": summary["avg_monetary"] / overall["Monetary"] * 100,
    }).loc[summary.index]

    fig, ax = plt.subplots(figsize=(5.5, 3.4375))
    x = range(len(idx))
    width = 0.26
    ax.bar([i - width for i in x], idx["Recency"], width, label="Recency", color="#D14D5B")
    ax.bar(list(x), idx["Frequency"], width, label="Frequency", color="#315EFB")
    ax.bar([i + width for i in x], idx["Monetary"], width, label="Monetary", color="#16856B")
    ax.axhline(100, color="#667085", linewidth=0.8, linestyle="--")
    ax.text(len(idx) - 0.45, 105, "overall avg = 100", fontsize=6.5, color="#667085", ha="right")
    ax.set_xticks(list(x))
    ax.set_xticklabels(idx.index, rotation=15)
    ax.set_ylabel("Index (overall average = 100)")
    ax.set_title("Average RFM Metrics by Segment")
    ax.legend(frameon=False, ncol=3, fontsize=7, loc="upper left")
    ax.set_ylim(0, max(idx.max().max() * 1.12, 120))
    _clean(ax, grid_axis="y")
    fig.tight_layout()
    fig.savefig(ASSETS / "fig3_rfm_profiles.png")
    plt.close(fig)

    print("Saved figures:")
    for name in ["fig1_segment_distribution.png", "fig2_revenue_by_segment.png", "fig3_rfm_profiles.png"]:
        print(f"  {ASSETS / name}")


if __name__ == "__main__":
    main()
