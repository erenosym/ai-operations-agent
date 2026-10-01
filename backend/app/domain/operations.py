from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.models import OrderStatus, RefundReason, RefundStatus


@dataclass(frozen=True, slots=True)
class CustomerOrderSummary:
    order_id: int
    customer_id: int
    status: OrderStatus
    ordered_at: datetime
    total_amount: Decimal
    order_item_count: int
    units: int


@dataclass(frozen=True, slots=True)
class RefundSummary:
    refund_id: int
    requested_at: datetime
    status: RefundStatus
    reason: RefundReason
    amount: Decimal
    product_id: int
    product_name: str
    order_id: int
    customer_id: int


@dataclass(frozen=True, slots=True)
class TopRefundedProduct:
    product_id: int
    product_name: str
    units_sold: int
    sold_order_items: int
    refunded_order_items: int
    refund_count: int
    gross_sales: Decimal
    refund_amount: Decimal
    refund_rate: Decimal


@dataclass(frozen=True, slots=True)
class ProductLookupResult:
    product_id: int
    name: str
    category: str
    price: Decimal


@dataclass(frozen=True, slots=True)
class ProductStatistics:
    product_id: int
    product_name: str
    units_sold: int
    sold_order_items: int
    refunded_order_items: int
    refund_count: int
    gross_sales: Decimal
    refund_amount: Decimal
    refund_rate: Decimal
    most_common_refund_reason: RefundReason | None


@dataclass(frozen=True, slots=True)
class RefundReasonCount:
    reason: RefundReason
    count: int
    percentage: Decimal
