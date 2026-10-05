"""Run the SQL pipeline in DuckDB, check the data, test the retention gap and export extracts."""

from __future__ import annotations

import math
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
SQL_FILES = ("01_staging.sql", "02_fct_orders.sql", "03_customer_retention.sql", "04_marts.sql")
RAW_FILES = (
    "olist_customers_dataset.csv", "olist_geolocation_dataset.csv", "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv", "olist_order_reviews_dataset.csv", "olist_orders_dataset.csv",
    "olist_products_dataset.csv", "olist_sellers_dataset.csv", "product_category_name_translation.csv",
)
REPEAT_WINDOW_DAYS = 180
MIN_SELLER_ORDERS = 30

# Tables exported for Tableau / Excel.
EXTRACTS = {
    "orders": "SELECT * EXCLUDE (customer_unique_id) FROM fct_orders",
    "lateness": "SELECT * FROM mart_lateness",
    "state": "SELECT * FROM mart_state",
    "seller": "SELECT * FROM mart_seller",
    "monthly": "SELECT * FROM mart_monthly",
    "distance": "SELECT * FROM mart_distance",
    "late_vs_ontime": "SELECT * FROM mart_late_vs_ontime",
    "retention_late_vs_ontime": "SELECT * FROM mart_retention_late_vs_ontime",
}


def build_database(raw_dir: Path, db_path: Path, window: int = REPEAT_WINDOW_DAYS,
                   min_seller_orders: int = MIN_SELLER_ORDERS) -> duckdb.DuckDBPyConnection:
    raw_dir = Path(raw_dir).resolve()
    missing = [f for f in RAW_FILES if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing in {raw_dir}: {', '.join(missing)}. Download the Olist dataset from Kaggle "
            "and unzip it into data/raw/ (see README)."
        )
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    for name in SQL_FILES:
        sql = (SQL_DIR / name).read_text(encoding="utf-8")
        sql = (sql.replace("{{RAW_DIR}}", raw_dir.as_posix().replace("'", "''"))
                  .replace("{{WINDOW}}", str(int(window)))
                  .replace("{{MIN_SELLER_ORDERS}}", str(int(min_seller_orders))))
        con.execute(sql)
    return con


def run_checks(con) -> pd.DataFrame:
    checks = con.execute((SQL_DIR / "checks.sql").read_text(encoding="utf-8")).df()
    checks["failing_rows"] = checks["failing_rows"].astype(int)
    return checks


def two_proportion_ztest(x1: int, n1: int, x2: int, n2: int) -> dict:
    """Two-sided z-test for p1 - p2 with a pooled standard error, plus a 95% CI (unpooled)."""
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se_pooled
    p_value = math.erfc(abs(z) / math.sqrt(2))
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    diff = p1 - p2
    return {"p1": p1, "p2": p2, "diff": diff, "relative_diff": diff / p1 if p1 else float("nan"),
            "z": z, "p_value": p_value, "ci_low": diff - 1.96 * se, "ci_high": diff + 1.96 * se}


def retention_test(con) -> dict:
    df = con.execute("SELECT * FROM mart_retention_late_vs_ontime").df().set_index("first_delivery")
    on, late = df.loc["On time"], df.loc["Late"]
    res = two_proportion_ztest(int(on.repeat_customers), int(on.customers),
                               int(late.repeat_customers), int(late.customers))
    res.update(on_time_customers=int(on.customers), late_customers=int(late.customers),
               on_time_repeat=int(on.repeat_customers), late_repeat=int(late.repeat_customers))
    return res


def export_extracts(con, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, query in EXTRACTS.items():
        path = out_dir / f"{name}.csv"
        con.execute(query).df().to_csv(path, index=False)
        paths.append(path)
    return paths
