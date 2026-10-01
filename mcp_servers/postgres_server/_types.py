from typing import TypedDict


class ProductLookupOutput(TypedDict):
    product_id: int
    name: str
    category: str
    price: str


class ProductLookupResult(TypedDict):
    products: list[ProductLookupOutput]


class CustomerOrderOutput(TypedDict):
    order_id: int
    customer_id: int
    status: str
    ordered_at: str
    total_amount: str
    order_item_count: int
    units: int


class CustomerOrdersResult(TypedDict):
    orders: list[CustomerOrderOutput]


class RefundOutput(TypedDict):
    refund_id: int
    requested_at: str
    status: str
    reason: str
    amount: str
    product_id: int
    product_name: str
    order_id: int
    customer_id: int


class RecentRefundsResult(TypedDict):
    refunds: list[RefundOutput]


class TopRefundedProductOutput(TypedDict):
    rank: int
    product_id: int
    product_name: str
    units_sold: int
    sold_order_items: int
    refunded_order_items: int
    refund_count: int
    gross_sales: str
    refund_amount: str
    refund_rate: str


class TopRefundedProductsResult(TypedDict):
    products: list[TopRefundedProductOutput]
    refund_rate_definition: str


class ProductStatisticsOutput(TypedDict):
    product_id: int
    product_name: str
    units_sold: int
    sold_order_items: int
    refunded_order_items: int
    refund_count: int
    gross_sales: str
    refund_amount: str
    refund_rate: str
    most_common_refund_reason: str | None


class ProductStatisticsResult(TypedDict):
    found: bool
    product: ProductStatisticsOutput | None


class RefundReasonOutput(TypedDict):
    reason: str
    count: int
    percentage: str


class RefundReasonBreakdownResult(TypedDict):
    reasons: list[RefundReasonOutput]
