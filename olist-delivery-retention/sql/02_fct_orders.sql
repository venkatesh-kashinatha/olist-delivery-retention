-- 02_fct_orders.sql
-- One row per delivered order with delivery timing, review, value, main seller,
-- main category and seller-to-customer distance.

CREATE OR REPLACE TABLE fct_orders AS
WITH items AS (
    SELECT
        order_id,
        COUNT(*)                   AS item_count,
        COUNT(DISTINCT seller_id)  AS seller_count,
        SUM(price)                 AS item_value,
        SUM(freight)               AS freight_value
    FROM stg_order_items
    GROUP BY order_id
),
-- The "main" seller and category are the ones with the most item value in the order.
main_line AS (
    SELECT order_id, seller_id, product_id
    FROM (
        SELECT
            order_id, seller_id, product_id,
            ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY price DESC, order_item_id) AS rn
        FROM stg_order_items
    ) AS x
    WHERE rn = 1
),
payments AS (
    SELECT order_id, SUM(payment_value) AS paid_value, MAX(installments) AS installments
    FROM stg_payments
    GROUP BY order_id
)
SELECT
    o.order_id,
    c.customer_unique_id,
    o.purchased_at,
    CAST(DATE_TRUNC('month', o.purchased_at) AS DATE)         AS order_month,
    o.delivered_at,
    o.estimated_at,
    DATE_DIFF('day', o.purchased_at, o.delivered_at)          AS delivery_days,
    DATE_DIFF('day', o.purchased_at, o.estimated_at)          AS promised_days,
    -- Positive = delivered after the promised date. Compared by calendar day.
    DATE_DIFF('day', CAST(o.estimated_at AS DATE), CAST(o.delivered_at AS DATE)) AS days_late,
    CAST(o.delivered_at AS DATE) > CAST(o.estimated_at AS DATE)                    AS is_late,
    CASE
        WHEN CAST(o.delivered_at AS DATE) <= CAST(o.estimated_at AS DATE) THEN '0 On time'
        WHEN DATE_DIFF('day', CAST(o.estimated_at AS DATE), CAST(o.delivered_at AS DATE)) <= 3 THEN '1 1-3 days late'
        WHEN DATE_DIFF('day', CAST(o.estimated_at AS DATE), CAST(o.delivered_at AS DATE)) <= 7 THEN '2 4-7 days late'
        WHEN DATE_DIFF('day', CAST(o.estimated_at AS DATE), CAST(o.delivered_at AS DATE)) <= 14 THEN '3 8-14 days late'
        ELSE '4 15+ days late'
    END                                                       AS lateness_bucket,
    r.review_score,
    r.review_score <= 2                                       AS is_negative_review,
    r.has_comment,
    i.item_count,
    i.seller_count,
    i.item_value,
    i.freight_value,
    p.paid_value,
    p.installments,
    c.customer_state,
    c.customer_city,
    s.seller_id                                               AS main_seller_id,
    s.seller_state,
    pr.category                                               AS main_category,
    c.customer_state = s.seller_state                         AS same_state,
    -- Great-circle distance in km between the seller's and the customer's zip prefix.
    2 * 6371 * ASIN(SQRT(
        POWER(SIN(RADIANS(gc.lat - gs.lat) / 2), 2)
        + COS(RADIANS(gs.lat)) * COS(RADIANS(gc.lat)) * POWER(SIN(RADIANS(gc.lng - gs.lng) / 2), 2)
    ))                                                        AS distance_km
FROM stg_orders AS o
JOIN stg_customers AS c   ON c.customer_id = o.customer_id
JOIN items AS i           ON i.order_id = o.order_id
JOIN main_line AS m       ON m.order_id = o.order_id
JOIN stg_sellers AS s     ON s.seller_id = m.seller_id
LEFT JOIN stg_products AS pr ON pr.product_id = m.product_id
LEFT JOIN payments AS p   ON p.order_id = o.order_id
LEFT JOIN stg_reviews AS r ON r.order_id = o.order_id
LEFT JOIN stg_zip_geo AS gc ON gc.zip = c.customer_zip
LEFT JOIN stg_zip_geo AS gs ON gs.zip = s.seller_zip
WHERE o.order_status = 'delivered'
  AND o.delivered_at IS NOT NULL
  AND o.estimated_at IS NOT NULL;
