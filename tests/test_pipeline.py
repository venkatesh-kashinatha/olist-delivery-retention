"""Tests run on a tiny hand-made dataset, so they don't need the Kaggle download."""

import csv
import math
from pathlib import Path

import pytest

from olist.pipeline import (RAW_FILES, build_database, export_extracts, retention_test, run_checks,
                            two_proportion_ztest)

ROOT = Path(__file__).resolve().parent.parent

# Three customers. A: on-time first order, then a repeat 30 days after delivery.
# B: late first order (5 days late), no repeat. C: on-time first order, repeat after 300 days.
# D: canceled order only (excluded). Order o1 has two reviews (latest one should win).
ORDERS = [
    # order_id, customer_id, status, purchase, approved, carrier, delivered, estimated
    ("o1", "c1", "delivered", "2017-01-02 10:00:00", "2017-01-02 11:00:00", "2017-01-03 10:00:00", "2017-01-10 10:00:00", "2017-01-20 00:00:00"),
    ("o2", "c2", "delivered", "2017-02-10 10:00:00", "2017-02-10 11:00:00", "2017-02-11 10:00:00", "2017-02-09 10:00:00", "2017-02-20 00:00:00"),
    ("o3", "c3", "delivered", "2017-01-05 09:00:00", "2017-01-05 10:00:00", "2017-01-06 10:00:00", "2017-01-25 12:00:00", "2017-01-20 00:00:00"),
    ("o4", "c4", "delivered", "2017-01-07 09:00:00", "2017-01-07 10:00:00", "2017-01-08 10:00:00", "2017-01-12 12:00:00", "2017-01-30 00:00:00"),
    ("o5", "c5", "delivered", "2017-11-12 09:00:00", "2017-11-12 10:00:00", "2017-11-13 10:00:00", "2017-11-15 12:00:00", "2017-11-30 00:00:00"),
    ("o6", "c6", "canceled",  "2017-03-01 09:00:00", "", "", "", "2017-03-20 00:00:00"),
    ("o7", "c7", "delivered", "2018-01-01 09:00:00", "2018-01-01 10:00:00", "2018-01-02 10:00:00", "2018-01-05 12:00:00", "2018-01-15 00:00:00"),
]
# o2 has delivered < purchased? No: fix below so checks pass.
ORDERS[1] = ("o2", "c2", "delivered", "2017-02-10 10:00:00", "2017-02-10 11:00:00", "2017-02-11 10:00:00",
             "2017-02-15 10:00:00", "2017-02-20 00:00:00")
CUSTOMERS = [
    # customer_id, unique_id, zip, city, state
    ("c1", "A", "01001", "sao paulo", "SP"), ("c2", "A", "01001", "sao paulo", "SP"),
    ("c3", "B", "57000", "maceio", "AL"),
    ("c4", "C", "01001", "sao paulo", "SP"), ("c5", "C", "01001", "sao paulo", "SP"),
    ("c6", "D", "01001", "sao paulo", "SP"),
    ("c7", "E", "57000", "maceio", "AL"),
]
ITEMS = [
    # order_id, item_id, product_id, seller_id, shipping_limit, price, freight
    ("o1", 1, "p1", "s1", "2017-01-04 00:00:00", 100.0, 10.0),
    ("o1", 2, "p2", "s2", "2017-01-04 00:00:00", 40.0, 5.0),
    ("o2", 1, "p1", "s1", "2017-02-12 00:00:00", 50.0, 8.0),
    ("o3", 1, "p2", "s1", "2017-01-07 00:00:00", 80.0, 20.0),
    ("o4", 1, "p1", "s2", "2017-01-09 00:00:00", 60.0, 7.0),
    ("o5", 1, "p1", "s2", "2017-11-14 00:00:00", 60.0, 7.0),
    ("o6", 1, "p1", "s2", "2017-03-02 00:00:00", 60.0, 7.0),
    ("o7", 1, "p2", "s1", "2018-01-02 00:00:00", 30.0, 9.0),
]
PAYMENTS = [(o, 1, "credit_card", 1, 0.0) for o, *_ in ORDERS]
REVIEWS = [
    # review_id, order_id, score, title, message, created, answered
    ("r1a", "o1", 2, "", "", "2017-01-11 00:00:00", "2017-01-11 05:00:00"),
    ("r1b", "o1", 5, "", "great", "2017-01-12 00:00:00", "2017-01-13 05:00:00"),
    ("r2", "o2", 4, "", "", "2017-02-16 00:00:00", "2017-02-16 05:00:00"),
    ("r3", "o3", 1, "", "late!", "2017-01-26 00:00:00", "2017-01-26 05:00:00"),
    ("r4", "o4", 5, "", "", "2017-01-13 00:00:00", "2017-01-13 05:00:00"),
    ("r7", "o7", 5, "", "", "2018-01-06 00:00:00", "2018-01-06 05:00:00"),
]
PRODUCTS = [("p1", "beleza_saude", 40, 300, 2, 500, 20, 10, 10),
            ("p2", "informatica_acessorios", 40, 300, 2, 800, 20, 10, 10)]
SELLERS = [("s1", "01310", "sao paulo", "SP"), ("s2", "13023", "campinas", "SP")]
GEO = [("01001", -23.55, -46.63, "sao paulo", "SP"), ("01310", -23.56, -46.65, "sao paulo", "SP"),
       ("13023", -22.90, -47.06, "campinas", "SP"), ("57000", -9.65, -35.73, "maceio", "AL")]
TRANSLATION = [("beleza_saude", "health_beauty"), ("informatica_acessorios", "computers_accessories")]

HEADERS = {
    "olist_orders_dataset.csv": ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
                                 "order_approved_at", "order_delivered_carrier_date",
                                 "order_delivered_customer_date", "order_estimated_delivery_date"],
    "olist_customers_dataset.csv": ["customer_id", "customer_unique_id", "customer_zip_code_prefix",
                                    "customer_city", "customer_state"],
    "olist_order_items_dataset.csv": ["order_id", "order_item_id", "product_id", "seller_id",
                                      "shipping_limit_date", "price", "freight_value"],
    "olist_order_payments_dataset.csv": ["order_id", "payment_sequential", "payment_type",
                                         "payment_installments", "payment_value"],
    "olist_order_reviews_dataset.csv": ["review_id", "order_id", "review_score", "review_comment_title",
                                        "review_comment_message", "review_creation_date",
                                        "review_answer_timestamp"],
    "olist_products_dataset.csv": ["product_id", "product_category_name", "product_name_lenght",
                                   "product_description_lenght", "product_photos_qty", "product_weight_g",
                                   "product_length_cm", "product_height_cm", "product_width_cm"],
    "olist_sellers_dataset.csv": ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
    "olist_geolocation_dataset.csv": ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng",
                                      "geolocation_city", "geolocation_state"],
    "product_category_name_translation.csv": ["product_category_name", "product_category_name_english"],
}
DATA = {
    "olist_orders_dataset.csv": ORDERS, "olist_customers_dataset.csv": CUSTOMERS,
    "olist_order_items_dataset.csv": ITEMS, "olist_order_payments_dataset.csv": PAYMENTS,
    "olist_order_reviews_dataset.csv": REVIEWS, "olist_products_dataset.csv": PRODUCTS,
    "olist_sellers_dataset.csv": SELLERS, "olist_geolocation_dataset.csv": GEO,
    "product_category_name_translation.csv": TRANSLATION,
}


@pytest.fixture
def con(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    for name in RAW_FILES:
        with open(raw / name, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(HEADERS[name])
            w.writerows(DATA[name])
    yield build_database(raw, tmp_path / "test.duckdb", window=180, min_seller_orders=1)


def q(con, sql):
    return con.execute(sql).df()


def test_checks_pass(con):
    assert run_checks(con)["failing_rows"].sum() == 0


def test_only_delivered_orders_in_fact(con):
    ids = set(q(con, "SELECT order_id FROM fct_orders")["order_id"])
    assert ids == {"o1", "o2", "o3", "o4", "o5", "o7"}


def test_lateness_by_calendar_day(con):
    f = q(con, "SELECT order_id, days_late, is_late, lateness_bucket FROM fct_orders").set_index("order_id")
    assert bool(f.loc["o3", "is_late"]) is True
    assert int(f.loc["o3", "days_late"]) == 5
    assert f.loc["o3", "lateness_bucket"] == "2 4-7 days late"
    assert bool(f.loc["o1", "is_late"]) is False


def test_latest_review_wins(con):
    score = q(con, "SELECT review_score FROM fct_orders WHERE order_id = 'o1'").iloc[0, 0]
    assert int(score) == 5


def test_main_seller_and_category_follow_highest_price(con):
    r = q(con, "SELECT main_seller_id, main_category, item_count, item_value FROM fct_orders WHERE order_id = 'o1'").iloc[0]
    assert r.main_seller_id == "s1"
    assert r.main_category == "health_beauty"
    assert int(r.item_count) == 2
    assert r.item_value == pytest.approx(140.0)


def test_distance_is_reasonable(con):
    d = q(con, "SELECT order_id, distance_km FROM fct_orders").set_index("order_id")["distance_km"]
    assert d["o1"] < 10                      # same city
    assert 1800 < d["o3"] < 2100             # Sao Paulo to Maceio


def test_repeat_window_logic(con):
    r = q(con, "SELECT customer_unique_id, order_id, repeat_in_window, days_to_next_order, is_mature "
               "FROM first_order_retention").set_index("customer_unique_id")
    assert r.loc["A", "order_id"] == "o1"
    assert bool(r.loc["A", "repeat_in_window"]) is True     # came back 31 days after delivery
    assert bool(r.loc["B", "repeat_in_window"]) is False    # never came back
    assert bool(r.loc["C", "repeat_in_window"]) is False    # came back, but after 180 days
    assert "D" not in r.index                               # canceled only
    assert bool(r.loc["E", "is_mature"]) is False           # delivered < 180 days before data end


def test_retention_mart_counts(con):
    m = q(con, "SELECT * FROM mart_retention_late_vs_ontime").set_index("first_delivery")
    assert int(m.loc["On time", "customers"]) == 2 and int(m.loc["On time", "repeat_customers"]) == 1
    assert int(m.loc["Late", "customers"]) == 1 and int(m.loc["Late", "repeat_customers"]) == 0


def test_extracts_written(con, tmp_path):
    paths = export_extracts(con, tmp_path / "out")
    assert {p.name for p in paths} >= {"orders.csv", "state.csv", "seller.csv", "lateness.csv"}


def test_ztest_matches_hand_calculation():
    r = two_proportion_ztest(1058, 59197, 55, 4517)
    p = (1058 + 55) / (59197 + 4517)
    z = (1058 / 59197 - 55 / 4517) / math.sqrt(p * (1 - p) * (1 / 59197 + 1 / 4517))
    assert r["z"] == pytest.approx(z)
    assert 0 < r["p_value"] < 0.01
    assert r["ci_low"] < r["diff"] < r["ci_high"]


def test_ztest_no_difference():
    r = two_proportion_ztest(50, 1000, 50, 1000)
    assert r["z"] == pytest.approx(0)
    assert r["p_value"] == pytest.approx(1)


def test_missing_files_message(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_database(tmp_path, tmp_path / "x.duckdb")
