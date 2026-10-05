"""Write outputs/summary.md from the marts."""

from __future__ import annotations

import pandas as pd


def _q(con, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def summary(con, test: dict, window: int) -> str:
    tot = _q(con, """SELECT COUNT(*) AS orders, COUNT(DISTINCT customer_unique_id) AS customers,
                            COUNT(DISTINCT main_seller_id) AS sellers,
                            AVG(CASE WHEN is_late THEN 1.0 ELSE 0 END) AS late_rate,
                            MIN(purchased_at) AS first_order, MAX(purchased_at) AS last_order
                     FROM fct_orders""").iloc[0]
    lv = _q(con, "SELECT * FROM mart_late_vs_ontime").set_index("delivery")
    lb = _q(con, "SELECT * FROM mart_lateness")
    st = _q(con, "SELECT * FROM mart_state WHERE orders >= 300 ORDER BY late_rate DESC")
    dist = _q(con, "SELECT * FROM mart_distance WHERE distance_band <> '9 Unknown' ORDER BY distance_band")
    sel = _q(con, """SELECT late_rate_decile, COUNT(*) AS sellers, SUM(orders) AS orders,
                            SUM(late_orders) * 1.0 / SUM(orders) AS late_rate, AVG(avg_review) AS avg_review
                     FROM mart_seller GROUP BY 1 ORDER BY 1""")
    mon = _q(con, "SELECT * FROM mart_monthly WHERE orders >= 500 ORDER BY late_rate DESC LIMIT 3")

    on, late = lv.loc["On time"], lv.loc["Late"]
    lines = [
        "# Olist delivery and retention summary",
        "",
        f"{int(tot.orders):,} delivered orders from {int(tot.customers):,} customers and "
        f"{int(tot.sellers):,} sellers, {pd.Timestamp(tot.first_order):%b %Y} to {pd.Timestamp(tot.last_order):%b %Y}. "
        f"{tot.late_rate:.1%} arrived after the promised date.",
        "",
        "## Late delivery and reviews",
        f"- Average review: {late.avg_review:.2f} late vs {on.avg_review:.2f} on time",
        f"- 1-2 star reviews: {late.negative_review_rate:.0%} late vs {on.negative_review_rate:.0%} on time "
        f"({late.negative_review_rate / on.negative_review_rate:.1f}x)",
        f"- 5-star reviews: {late.five_star_rate:.0%} late vs {on.five_star_rate:.0%} on time",
    ]
    for _, r in lb.iterrows():
        lines.append(f"  - {r.lateness_bucket[2:]}: {r.orders:,} orders, avg review {r.avg_review:.2f}, "
                     f"{r.negative_review_rate:.0%} negative")
    lines += [
        "",
        f"## Late first delivery and repeat purchase (within {window} days of delivery)",
        f"- On time: {test['on_time_repeat']:,} of {test['on_time_customers']:,} came back ({test['p1']:.2%})",
        f"- Late: {test['late_repeat']:,} of {test['late_customers']:,} came back ({test['p2']:.2%})",
        f"- Late first orders had a {abs(test['relative_diff']):.0%} lower repeat rate "
        f"(z = {test['z']:.2f}, p = {test['p_value']:.3f}; 95% CI for the gap "
        f"{test['ci_low']*100:.2f} to {test['ci_high']*100:.2f} pts)",
        "",
        "## Where lateness happens",
        "- States with the highest late rate (300+ orders):",
    ]
    for _, r in st.head(5).iterrows():
        lines.append(f"  - {r.customer_state}: {r.late_rate:.1%} late, {r.orders:,} orders, "
                     f"avg {r.avg_distance_km:,.0f} km from seller, avg review {r.avg_review:.2f}")
    lines.append("- By seller-to-customer distance:")
    for _, r in dist.iterrows():
        lines.append(f"  - {r.distance_band[2:]}: {r.late_rate:.1%} late, {r.avg_delivery_days:.1f} days to deliver")
    worst, best = sel.iloc[0], sel.iloc[-1]
    lines += [
        f"- {int(sel.sellers.sum())} sellers with 30+ orders, split into tenths by late rate. Worst 10%: "
        f"{worst.late_rate:.1%} late, avg review {worst.avg_review:.2f}; best 10%: {best.late_rate:.1%} late, "
        f"avg review {best.avg_review:.2f}",
        "- Worst months: " + ", ".join(f"{pd.Timestamp(r.order_month):%b %Y} ({r.late_rate:.1%})" for _, r in mon.iterrows()),
    ]
    return "\n".join(lines) + "\n"
