-- checks.sql
-- Data quality checks. Each row is one check, and failing_rows should be 0.
SELECT 'Duplicate order IDs in fct_orders' AS check_name, COUNT(*) - COUNT(DISTINCT order_id) AS failing_rows
FROM fct_orders
UNION ALL
SELECT 'Orders without a customer', COUNT(*)
FROM stg_orders AS o LEFT JOIN stg_customers AS c ON c.customer_id = o.customer_id
WHERE c.customer_id IS NULL
UNION ALL
SELECT 'Order items with an unknown seller', COUNT(*)
FROM stg_order_items AS i LEFT JOIN stg_sellers AS s ON s.seller_id = i.seller_id
WHERE s.seller_id IS NULL
UNION ALL
SELECT 'Order items with an unknown product', COUNT(*)
FROM stg_order_items AS i LEFT JOIN stg_products AS p ON p.product_id = i.product_id
WHERE p.product_id IS NULL
UNION ALL
SELECT 'More than one review per order after dedupe', COUNT(*) - COUNT(DISTINCT order_id) FROM stg_reviews
UNION ALL
SELECT 'Review scores outside 1-5', COUNT(*) FROM stg_reviews WHERE review_score NOT BETWEEN 1 AND 5
UNION ALL
SELECT 'Delivered before purchase', COUNT(*) FROM fct_orders WHERE delivered_at < purchased_at
UNION ALL
SELECT 'Negative prices or freight', COUNT(*) FROM stg_order_items WHERE price < 0 OR freight < 0
UNION ALL
SELECT 'Distance over 5,000 km (bad coordinates)', COUNT(*) FROM fct_orders WHERE distance_km > 5000
UNION ALL
SELECT 'Customers with more than one first order', COUNT(*) - COUNT(DISTINCT customer_unique_id)
FROM first_order_retention;
