-- 03_customer_retention.sql
-- Did a customer's FIRST delivery experience change whether they ordered again?
-- Uses ROW_NUMBER and LEAD over each customer's orders (all statuses count as a repeat order).

CREATE OR REPLACE TABLE customer_orders AS
SELECT
    c.customer_unique_id,
    o.order_id,
    o.purchased_at,
    ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id ORDER BY o.purchased_at, o.order_id) AS order_seq,
    LEAD(o.purchased_at) OVER (PARTITION BY c.customer_unique_id ORDER BY o.purchased_at, o.order_id) AS next_purchased_at
FROM stg_orders AS o
JOIN stg_customers AS c ON c.customer_id = o.customer_id
WHERE o.order_status NOT IN ('canceled', 'unavailable');

-- First orders that were delivered, with whether the customer came back.
-- A repeat must be placed after the first order was DELIVERED (so the customer had the experience)
-- and within {{WINDOW}} days of delivery. Only first orders delivered at least {{WINDOW}} days
-- before the end of the data are "mature" enough to judge.
CREATE OR REPLACE TABLE first_order_retention AS
WITH data_end AS (
    SELECT MAX(purchased_at) AS last_purchase FROM stg_orders
),
next_after_delivery AS (
    SELECT
        f.customer_unique_id,
        MIN(n.purchased_at) AS next_order_at
    FROM customer_orders AS f
    JOIN fct_orders AS fo ON fo.order_id = f.order_id
    JOIN customer_orders AS n
      ON n.customer_unique_id = f.customer_unique_id
     AND n.order_seq > 1
     AND n.purchased_at > fo.delivered_at
    WHERE f.order_seq = 1
    GROUP BY f.customer_unique_id
)
SELECT
    fo.*,
    nad.next_order_at,
    DATE_DIFF('day', fo.delivered_at, nad.next_order_at)       AS days_to_next_order,
    COALESCE(DATE_DIFF('day', fo.delivered_at, nad.next_order_at) <= {{WINDOW}}, FALSE) AS repeat_in_window,
    fo.delivered_at <= d.last_purchase - INTERVAL {{WINDOW}} DAY AS is_mature
FROM customer_orders AS f
JOIN fct_orders AS fo ON fo.order_id = f.order_id
CROSS JOIN data_end AS d
LEFT JOIN next_after_delivery AS nad ON nad.customer_unique_id = f.customer_unique_id
WHERE f.order_seq = 1;
