"""Command line: python -m olist build"""

import argparse
import json
from pathlib import Path

from .pipeline import (REPEAT_WINDOW_DAYS, build_database, export_extracts, retention_test,
                       run_checks)
from .report import summary

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser(prog="olist", description="Olist delivery delays, reviews and retention")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="run the SQL pipeline, checks, stats test and extracts")
    b.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    b.add_argument("--out", type=Path, default=ROOT / "outputs")
    b.add_argument("--window", type=int, default=REPEAT_WINDOW_DAYS,
                   help="days after delivery that count as a repeat purchase")
    a = p.parse_args()

    a.out.mkdir(parents=True, exist_ok=True)
    db = a.out / "olist.duckdb"
    if db.exists():
        db.unlink()
    con = build_database(a.raw, db, a.window)
    checks = run_checks(con)
    checks.to_csv(a.out / "quality_checks.csv", index=False)
    print(checks.to_string(index=False))
    if checks["failing_rows"].sum():
        raise SystemExit("Data quality checks failed")
    test = retention_test(con)
    (a.out / "retention_test.json").write_text(json.dumps(test, indent=2))
    export_extracts(con, a.out / "tableau")
    text = summary(con, test, a.window)
    (a.out / "summary.md").write_text(text)
    print()
    print(text)


if __name__ == "__main__":
    main()
