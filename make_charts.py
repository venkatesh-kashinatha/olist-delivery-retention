"""Build the README charts in docs/ from the extracts written by `python -m olist build`.

    python scripts/make_charts.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
EXT = OUT / "tableau"
DOCS = ROOT / "docs"
BLUE, GREEN, AMBER, RED, GREY, INK = "#1F5FA8", "#2E7D5B", "#E0A100", "#C0392B", "#9AA5B1", "#1F2933"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 12, "figure.dpi": 130})


def reviews_by_lateness():
    d = pd.read_csv(EXT / "lateness.csv")
    d["label"] = d["lateness_bucket"].str[2:]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    colors = [GREEN, AMBER, RED, RED, RED]
    bars = ax.bar(d["label"], d["avg_review"], color=colors)
    for b, r, n, neg in zip(bars, d["avg_review"], d["orders"], d["negative_review_rate"]):
        ax.text(b.get_x() + b.get_width() / 2, r + 0.08, f"{r:.2f}★", ha="center", fontweight="bold")
        ax.text(b.get_x() + b.get_width() / 2, 0.15, f"{n:,} orders\n{neg:.0%} 1-2 star",
                ha="center", color="white", fontsize=8.5)
    ax.set_ylim(0, 5)
    ax.set_ylabel("Average review score")
    ax.set_title("Review score falls fast once an order is late")
    fig.tight_layout()
    fig.savefig(DOCS / "reviews_by_lateness.png")
    plt.close(fig)


def repeat_rate():
    t = json.loads((OUT / "retention_test.json").read_text())
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    vals = [t["p1"] * 100, t["p2"] * 100]
    ns = [t["on_time_customers"], t["late_customers"]]
    xs = [t["on_time_repeat"], t["late_repeat"]]
    err = [1.96 * (p / 100 * (1 - p / 100) / n) ** 0.5 * 100 for p, n in zip(vals, ns)]
    bars = ax.bar(["On-time first delivery", "Late first delivery"], vals, color=[GREEN, RED],
                  yerr=err, capsize=6, ecolor=INK)
    for b, v, x, n in zip(bars, vals, xs, ns):
        ax.text(b.get_x() + b.get_width() / 2, v / 2, f"{v:.2f}%\n({x:,} of {n:,})", ha="center",
                color="white", fontweight="bold")
    ax.set_ylim(0, 2.8)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=1))
    ax.set_title(f"Repeat purchase within 180 days: {abs(t['relative_diff']):.0%} lower after a late "
                 f"first order\n(p = {t['p_value']:.3f}, bars show 95% CI)", fontsize=11)
    fig.tight_layout()
    fig.savefig(DOCS / "repeat_rate.png")
    plt.close(fig)


def late_by_state():
    d = pd.read_csv(EXT / "state.csv")
    d = d[d["orders"] >= 300].sort_values("late_rate")
    allst = pd.read_csv(EXT / "state.csv")
    overall = (allst["late_rate"] * allst["orders"]).sum() / allst["orders"].sum()
    fig, ax = plt.subplots(figsize=(8, 6.2))
    colors = [RED if v >= 0.12 else AMBER if v >= 0.08 else BLUE for v in d["late_rate"]]
    ax.barh(d["customer_state"], d["late_rate"] * 100, color=colors)
    for y, (v, km) in enumerate(zip(d["late_rate"], d["avg_distance_km"])):
        ax.text(v * 100 + 0.3, y, f"{v:.1%}  ({km:,.0f} km)", va="center", fontsize=8)
    ax.axvline(overall * 100, color=INK, ls="--", lw=0.9)
    ax.text(overall * 100 + 0.2, -1.0, f"all orders {overall:.1%}", fontsize=8.5)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xlim(0, 26)
    ax.set_title("Late-delivery rate by customer state\n(states with 300+ orders; avg seller distance in brackets)",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(DOCS / "late_by_state.png")
    plt.close(fig)


def late_by_distance():
    d = pd.read_csv(EXT / "distance.csv")
    d = d[~d["distance_band"].str.startswith("9")]
    d["label"] = d["distance_band"].str[2:]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(d["label"], d["late_rate"] * 100, color=BLUE)
    for i, (v, dd, rv) in enumerate(zip(d["late_rate"], d["avg_delivery_days"], d["avg_review"])):
        ax.text(i, v * 100 + 0.3, f"{v:.1%}\n{dd:.0f} days, {rv:.2f}★", ha="center", fontsize=8.5)
    ax.set_ylim(0, 15)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_title("Late rate rises with seller-to-customer distance")
    ax.set_xlabel("Distance between seller and customer zip code")
    fig.tight_layout()
    fig.savefig(DOCS / "late_by_distance.png")
    plt.close(fig)


def monthly():
    d = pd.read_csv(EXT / "monthly.csv", parse_dates=["order_month"])
    d = d[d["orders"] >= 500]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(d["order_month"], d["late_rate"] * 100, width=20, color=AMBER, label="Late rate")
    ax.yaxis.set_major_locator(mtick.MultipleLocator(5))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_ylabel("Late rate")
    ax2 = ax.twinx()
    ax2.plot(d["order_month"], d["avg_review"], color=INK, marker="o", lw=1.8, label="Avg review")
    ax2.set_ylim(3.6, 4.5)
    ax2.set_ylabel("Average review")
    ax2.spines["top"].set_visible(False)
    ax.set_title("Monthly late rate (bars) and average review (line): reviews dip when delays spike")
    fig.tight_layout()
    fig.savefig(DOCS / "monthly_late_vs_review.png")
    plt.close(fig)


def main():
    DOCS.mkdir(exist_ok=True)
    reviews_by_lateness()
    repeat_rate()
    late_by_state()
    late_by_distance()
    monthly()
    print("Charts saved to", DOCS)


if __name__ == "__main__":
    main()
