# Query performance baseline

Measured locally against PostgreSQL 17 with the deterministic dataset of 2,000 orders, 5,877 order items, and 404 refunds. Times are environment-specific and serve only as an initial baseline.

## Top refunded products

Purpose: aggregate sales and refunds by product for `2026-04-01` through `2026-10-01`, apply a minimum of 20 sold order items, and rank by distinct-refunded-item rate.

Relevant indexes include `ix_orders_ordered_at`, `ix_refunds_requested_at`, `ix_order_items_product_id`, and the order-item foreign-key access supported by `uq_order_items_order_product`.

Observed plan shape:

- sequential scans over `orders`, `order_items`, `refunds`, and the 50-row `products` table;
- hash joins for the broad date range;
- hash/group aggregation for sales and grouped aggregation for distinct refunded items;
- top-N heapsort for the five results.

Planning time was approximately 1.35 ms and execution time approximately 2.96 ms. Sequential scans are reasonable because the range covers nearly the entire small dataset; index access would add overhead without filtering many rows. No index change is justified by this result.

## Customer order history

Purpose: return one customer's orders in the same date range, aggregate item/unit counts, and sort newest first.

Relevant indexes are `ix_orders_customer_ordered_at` and the leftmost `order_id` portion of `uq_order_items_order_product`.

Observed plan shape:

- bitmap index scan on `ix_orders_customer_ordered_at` followed by a bitmap heap scan;
- nested-loop left join;
- index scan on `uq_order_items_order_product` for each matching order;
- group aggregation and a small in-memory quicksort.

The tested customer had nine matching orders. Planning time was approximately 0.21 ms and execution time approximately 0.10 ms. The existing indexes directly support this selective query, so no schema change is needed.

## Product lookup

`find_products` ranks a case-insensitive exact name first, then applies bounded name or category substring matching. PostgreSQL chooses a sequential scan for the 50-row development catalog followed by a tiny sort and limit. That plan is appropriate at this scale, so no search index or migration was added.
