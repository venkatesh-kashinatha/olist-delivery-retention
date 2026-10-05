-- 04_marts.sql
-- Reporting tables for the README, the Excel/Tableau extracts and the tests.

-- Review score and repeat rate by how late the order was.
CREATE OR REPLACE TABLE mart_lateness AS
WITH reviews AS (
    SELECT
        lateness_bucket,
        COUNT(*)                                            AS orders,
        AVG(review_score)                                   AS avg_review,
        AVG(CASE WHEN is_negative_review THEN 1.0 ELSE 0 END) AS negative_review_rate
    FROM fct_orders
    WHERE review_score IS NOT NULL
    GROUP BY lateness_bucket
),
retention AS (
    SELECT
        lateness_bucket,
        COUNT(*)                                             AS mature_first_orders,
        AVG(CASE WHEN repeat_in_window THEN 1.0 ELSE 0 END)  AS repeat_rate
    FROM first_order_retention
    WHERE is_mature
    GROUP BY lateness_bucket
)
SELECT
    r.lateness_bucket,
    r.orders,
    r.orders * 1.0 / SUM(r.orders) OVER ()  AS share_of_orders,
    r.avg_review,
    r.negative_review_rate,
    t.mature_first_orders,
    t.repeat_rate
FROM reviews AS r
LEFT JOIN retention AS t USING (lateness_bucket)
ORDER BY r.lateness_bucket;

-- Late vs on time headline.
CREATE OR REPLACE TABLE mart_late_vs_ontime AS
SELECT
    CASE WHEN fo.is_late THEN 'Late' ELSE 'On time' END     AS delivery,
    COUNT(*)                                               AS orders,
    AVG(fo.review_score)                                   AS avg_review,
    AVG(CASE WHEN fo.is_negative_review THEN 1.0 ELSE 0 END) AS negative_review_rate,
    AVG(CASE WHEN fo.review_score = 5 THEN 1.0 ELSE 0 END)   AS five_star_rate,
    AVG(fo.delivery_days)                                  AS avg_delivery_days
FROM fct_orders AS fo
WHERE fo.review_score IS NOT NULL
GROUP BY 1;

CREATE OR REPLACE TABLE mart_retention_late_vs_ontime AS
SELECT
    CASE WHEN is_late THEN 'Late' ELSE 'On time' END       AS first_delivery,
    COUNT(*)                                               AS customers,
    SUM(CASE WHEN repeat_in_window THEN 1 ELSE 0 END)      AS repeat_customers,
    AVG(CASE WHEN repeat_in_window THEN 1.0 ELSE 0 END)    AS repeat_rate
FROM first_order_retention
WHERE is_mature
GROUP BY 1;

-- By customer state, ranked by late rate.
CREATE OR REPLACE TABLE mart_state AS
SELECT
    customer_state,
    COUNT(*)                                               AS orders,
    AVG(CASE WHEN is_late THEN 1.0 ELSE 0 END)             AS late_rate,
    AVG(delivery_days)                                     AS avg_delivery_days,
    AVG(promised_days)                                     AS avg_promised_days,
    AVG(distance_km)                                       AS avg_distance_km,
    AVG(review_score)                                      AS avg_review,
    RANK() OVER (ORDER BY AVG(CASE WHEN is_late THEN 1.0 ELSE 0 END) DESC) AS late_rank
FROM fct_orders
GROUP BY customer_state
ORDER BY late_rate DESC;

-- By seller (sellers with at least {{MIN_SELLER_ORDERS}} delivered orders).
CREATE OR REPLACE TABLE mart_seller AS
WITH s AS (
    SELECT
        main_seller_id                                     AS seller_id,
        MAX(seller_state)                                  AS seller_state,
        COUNT(*)                                           AS orders,
        SUM(CASE WHEN is_late THEN 1 ELSE 0 END)           AS late_orders,
        AVG(CASE WHEN is_late THEN 1.0 ELSE 0 END)         AS late_rate,
        AVG(review_score)                                  AS avg_review,
        SUM(item_value)                                    AS item_value
    FROM fct_orders
    GROUP BY main_seller_id
    HAVING COUNT(*) >= {{MIN_SELLER_ORDERS}}
)
SELECT
    *,
    late_orders * 1.0 / SUM(late_orders) OVER ()           AS share_of_all_late_orders,
    NTILE(10) OVER (ORDER BY late_rate DESC)               AS late_rate_decile
FROM s
ORDER BY late_orders DESC;

-- Monthly trend.
CREATE OR REPLACE TABLE mart_monthly AS
SELECT
    order_month,
    COUNT(*)                                               AS orders,
    AVG(CASE WHEN is_late THEN 1.0 ELSE 0 END)             AS late_rate,
    AVG(review_score)                                      AS avg_review,
    AVG(delivery_days)                                     AS avg_delivery_days
FROM fct_orders
GROUP BY order_month
ORDER BY order_month;

-- Distance bands.
CREATE OR REPLACE TABLE mart_distance AS
SELECT
    CASE
        WHEN distance_km IS NULL THEN '9 Unknown'
        WHEN distance_km < 100  THEN '1 <100 km'
        WHEN distance_km < 500  THEN '2 100-499 km'
        WHEN distance_km < 1000 THEN '3 500-999 km'
        WHEN distance_km < 2000 THEN '4 1,000-1,999 km'
        ELSE '5 2,000+ km'
    END                                                    AS distance_band,
    COUNT(*)                                               AS orders,
    AVG(CASE WHEN is_late THEN 1.0 ELSE 0 END)             AS late_rate,
    AVG(delivery_days)                                     AS avg_delivery_days,
    AVG(promised_days)                                     AS avg_promised_days,
    AVG(review_score)                                      AS avg_review
FROM fct_orders
GROUP BY 1
ORDER BY 1;
