-- 01_staging.sql
-- Load the 9 Olist CSV files into typed staging tables.
-- This is the only DuckDB-specific file (read_csv). Files 02-05 are portable SQL.

CREATE OR REPLACE TABLE stg_orders AS
SELECT
    order_id,
    customer_id,
    order_status,
    CAST(order_purchase_timestamp AS TIMESTAMP)      AS purchased_at,
    CAST(order_approved_at AS TIMESTAMP)             AS approved_at,
    CAST(order_delivered_carrier_date AS TIMESTAMP)  AS shipped_at,
    CAST(order_delivered_customer_date AS TIMESTAMP) AS delivered_at,
    CAST(order_estimated_delivery_date AS TIMESTAMP) AS estimated_at
FROM read_csv('{{RAW_DIR}}/olist_orders_dataset.csv', header = true, all_varchar = true);

-- customer_id is per order; customer_unique_id identifies the person across orders.
CREATE OR REPLACE TABLE stg_customers AS
SELECT
    customer_id,
    customer_unique_id,
    LPAD(customer_zip_code_prefix, 5, '0') AS customer_zip,
    customer_city,
    customer_state
FROM read_csv('{{RAW_DIR}}/olist_customers_dataset.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE stg_order_items AS
SELECT
    order_id,
    CAST(order_item_id AS INTEGER) AS order_item_id,
    product_id,
    seller_id,
    CAST(price AS DOUBLE)          AS price,
    CAST(freight_value AS DOUBLE)  AS freight
FROM read_csv('{{RAW_DIR}}/olist_order_items_dataset.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE stg_payments AS
SELECT
    order_id,
    payment_type,
    CAST(payment_installments AS INTEGER) AS installments,
    CAST(payment_value AS DOUBLE)         AS payment_value
FROM read_csv('{{RAW_DIR}}/olist_order_payments_dataset.csv', header = true, all_varchar = true);

-- Some orders have more than one review. Keep the latest answer per order.
CREATE OR REPLACE TABLE stg_reviews AS
WITH ranked AS (
    SELECT
        order_id,
        CAST(review_score AS INTEGER)               AS review_score,
        CAST(review_creation_date AS TIMESTAMP)     AS review_created_at,
        CAST(review_answer_timestamp AS TIMESTAMP)  AS review_answered_at,
        review_comment_message IS NOT NULL
            AND TRIM(review_comment_message) <> ''  AS has_comment,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY CAST(review_answer_timestamp AS TIMESTAMP) DESC, review_id
        ) AS rn
    FROM read_csv('{{RAW_DIR}}/olist_order_reviews_dataset.csv', header = true, all_varchar = true)
)
SELECT order_id, review_score, review_created_at, review_answered_at, has_comment
FROM ranked
WHERE rn = 1;

CREATE OR REPLACE TABLE stg_products AS
SELECT
    p.product_id,
    COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
    TRY_CAST(p.product_weight_g AS DOUBLE) AS weight_g
FROM read_csv('{{RAW_DIR}}/olist_products_dataset.csv', header = true, all_varchar = true) AS p
LEFT JOIN read_csv('{{RAW_DIR}}/product_category_name_translation.csv', header = true, all_varchar = true) AS t
    ON t.product_category_name = p.product_category_name;

CREATE OR REPLACE TABLE stg_sellers AS
SELECT
    seller_id,
    LPAD(seller_zip_code_prefix, 5, '0') AS seller_zip,
    seller_city,
    seller_state
FROM read_csv('{{RAW_DIR}}/olist_sellers_dataset.csv', header = true, all_varchar = true);

-- The geolocation file has ~1M rows with many points per zip prefix. Average them to one
-- point per prefix, dropping coordinates outside Brazil's bounding box.
CREATE OR REPLACE TABLE stg_zip_geo AS
SELECT
    LPAD(geolocation_zip_code_prefix, 5, '0') AS zip,
    AVG(CAST(geolocation_lat AS DOUBLE))      AS lat,
    AVG(CAST(geolocation_lng AS DOUBLE))      AS lng
FROM read_csv('{{RAW_DIR}}/olist_geolocation_dataset.csv', header = true, all_varchar = true)
WHERE CAST(geolocation_lat AS DOUBLE) BETWEEN -34 AND 6
  AND CAST(geolocation_lng AS DOUBLE) BETWEEN -74 AND -34
GROUP BY 1;
