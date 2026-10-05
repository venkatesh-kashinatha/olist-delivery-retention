# Tableau dashboard

Data: `outputs/tableau/orders.csv` (one row per delivered order). Tableau Public can't connect to DuckDB,
so the build writes CSV extracts.

## Calculated fields

```
Late Orders          = SUM(IF [Is Late] = "true" OR [Is Late] = TRUE THEN 1 ELSE 0 END)
Late Rate            = [Late Orders] / COUNT([Order Id])
Avg Review           = AVG([Review Score])
Negative Review Rate = SUM(IF [Review Score] <= 2 THEN 1 ELSE 0 END) / COUNT([Review Score])
Lateness Bucket      = MID([Lateness Bucket], 3)        // drops the "0 " sort prefix
Distance Band        = IF [Distance Km] < 100 THEN "<100 km"
                       ELSEIF [Distance Km] < 500 THEN "100-499 km"
                       ELSEIF [Distance Km] < 1000 THEN "500-999 km"
                       ELSEIF [Distance Km] < 2000 THEN "1,000-1,999 km"
                       ELSE "2,000+ km" END
```

## Layout (one dashboard, 1200 x 900)

1. **KPI row:** Orders, Late Rate, Avg Review (late vs on time), Negative Review Rate.
2. **Map:** filled map of Brazil by `Customer State`, color = Late Rate, tooltip = orders, avg distance, avg review.
   (Set the state field's geographic role to State/Province and country to Brazil.)
3. **Bar:** Avg Review by Lateness Bucket, with Negative Review Rate as a label.
4. **Bar:** Late Rate by Distance Band.
5. **Dual axis:** Late Rate (bars) and Avg Review (line) by `Order Month`.
6. **Table:** top sellers from `seller.csv`, sorted by late orders, with late rate and avg review.
7. **Filters:** Order Month range, Customer State, Main Category.

Add the repeat-purchase result from `retention_late_vs_ontime.csv` as a text box or a two-bar chart.

Publish: **File > Save to Tableau Public**, then put the link in this README and on your resume.
