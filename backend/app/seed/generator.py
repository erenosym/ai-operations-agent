from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random
from typing import TypeVar

from app.models import OrderStatus, RefundReason, RefundStatus

RANDOM_SEED = 20261001
DATASET_REFERENCE_DATE = datetime(2026, 10, 1, tzinfo=timezone.utc)

HIGH_REFUND_PRODUCT = "Pulse Wireless Headphones"
SIZE_REFUND_PRODUCT = "StridePro Running Shoes"
LOW_REFUND_PRODUCT = "Forge Mechanical Keyboard"
T = TypeVar("T")

DEFAULT_REASON_WEIGHTS = (
    (RefundReason.DEFECTIVE, 25),
    (RefundReason.DAMAGED, 15),
    (RefundReason.NOT_AS_DESCRIBED, 20),
    (RefundReason.CHANGED_MIND, 25),
    (RefundReason.WRONG_ITEM, 10),
    (RefundReason.OTHER, 5),
)


@dataclass(frozen=True, slots=True)
class CustomerSeed:
    name: str
    email: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProductSeed:
    key: str
    name: str
    category: str
    price: Decimal
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RefundSeed:
    reason: RefundReason
    amount: Decimal
    status: RefundStatus
    requested_at: datetime
    processed_at: datetime | None


@dataclass(frozen=True, slots=True)
class OrderItemSeed:
    product_key: str
    quantity: int
    unit_price: Decimal
    refund: RefundSeed | None


@dataclass(frozen=True, slots=True)
class OrderSeed:
    customer_index: int
    status: OrderStatus
    ordered_at: datetime
    total_amount: Decimal
    items: tuple[OrderItemSeed, ...]


@dataclass(frozen=True, slots=True)
class ProductPatternSummary:
    product_name: str
    units_sold: int
    sold_order_items: int
    refunded_units: int
    refunded_order_items: int
    refund_rate: Decimal
    most_common_reason: RefundReason | None


@dataclass(frozen=True, slots=True)
class GeneratedSeedData:
    customers: tuple[CustomerSeed, ...]
    products: tuple[ProductSeed, ...]
    orders: tuple[OrderSeed, ...]

    @property
    def order_item_count(self) -> int:
        return sum(len(order.items) for order in self.orders)

    @property
    def refund_count(self) -> int:
        return sum(
            item.refund is not None
            for order in self.orders
            for item in order.items
        )


@dataclass(frozen=True, slots=True)
class _ProductProfile:
    product: ProductSeed
    selection_weight: int
    refund_probability: float
    reason_weights: tuple[tuple[RefundReason, int], ...]


PRODUCT_DEFINITIONS = (
    ("pulse-headphones", HIGH_REFUND_PRODUCT, "electronics", "129.99"),
    ("stridepro-shoes", SIZE_REFUND_PRODUCT, "footwear", "94.50"),
    ("forge-keyboard", LOW_REFUND_PRODUCT, "electronics", "109.00"),
    ("summit-backpack", "Summit Trail Backpack", "outdoors", "79.95"),
    ("harbor-jacket", "Harbor Rain Jacket", "apparel", "119.00"),
    ("lumen-lamp", "Lumen Desk Lamp", "home", "42.75"),
    ("terra-bottle", "Terra Insulated Bottle", "outdoors", "31.50"),
    ("arc-mouse", "Arc Wireless Mouse", "electronics", "54.99"),
    ("cloud-hoodie", "Cloudline Cotton Hoodie", "apparel", "68.00"),
    ("tempo-watch", "Tempo Fitness Watch", "electronics", "149.95"),
    ("grove-planter", "Grove Ceramic Planter", "home", "28.40"),
    ("atlas-duffel", "Atlas Weekend Duffel", "travel", "88.00"),
    ("cove-sandals", "Cove Walking Sandals", "footwear", "59.90"),
    ("ember-kettle", "Ember Electric Kettle", "kitchen", "64.25"),
    ("ridge-poles", "Ridge Trekking Poles", "outdoors", "71.00"),
    ("nova-webcam", "Nova HD Webcam", "electronics", "82.50"),
    ("meadow-sheet", "Meadow Cotton Sheet Set", "home", "96.00"),
    ("orbit-charger", "Orbit USB-C Charger", "electronics", "36.99"),
    ("drift-sneakers", "Drift Everyday Sneakers", "footwear", "84.00"),
    ("cedar-board", "Cedar Cutting Board", "kitchen", "39.50"),
    ("aero-yoga", "Aero Yoga Mat", "fitness", "47.25"),
    ("haven-throw", "Haven Woven Throw", "home", "58.00"),
    ("vertex-speaker", "Vertex Portable Speaker", "electronics", "74.95"),
    ("trail-cap", "Trail Running Cap", "apparel", "26.50"),
    ("bloom-mug", "Bloom Stoneware Mug Set", "kitchen", "34.00"),
    ("pulse-bands", "Pulse Resistance Bands", "fitness", "24.99"),
    ("roam-organizer", "Roam Travel Organizer", "travel", "29.75"),
    ("north-vest", "Northwind Quilted Vest", "apparel", "89.00"),
    ("signal-hub", "Signal USB-C Hub", "electronics", "61.50"),
    ("brook-towels", "Brook Bath Towel Set", "home", "52.00"),
    ("stride-socks", "Stride Performance Socks", "apparel", "21.00"),
    ("peak-lantern", "Peak Camping Lantern", "outdoors", "45.95"),
    ("echo-earbuds", "Echo Wireless Earbuds", "electronics", "89.99"),
    ("craft-knife", "Craft Chef Knife", "kitchen", "73.00"),
    ("flow-shorts", "Flow Training Shorts", "fitness", "44.50"),
    ("metro-tote", "Metro Canvas Tote", "travel", "38.00"),
    ("soft-knit", "Soft Knit Sweater", "apparel", "72.00"),
    ("focus-stand", "Focus Laptop Stand", "electronics", "49.95"),
    ("nest-pillow", "Nest Memory Foam Pillow", "home", "67.50"),
    ("pace-shoes", "Pace Walking Shoes", "footwear", "78.00"),
    ("camp-stove", "Camp Compact Stove", "outdoors", "69.00"),
    ("snap-toaster", "Snap Two-Slice Toaster", "kitchen", "48.25"),
    ("core-roller", "Core Foam Roller", "fitness", "32.00"),
    ("voyage-pillow", "Voyage Neck Pillow", "travel", "27.50"),
    ("daily-tee", "Daily Organic Tee", "apparel", "29.00"),
    ("pixel-monitor", "Pixel 24-inch Monitor", "electronics", "189.00"),
    ("calm-diffuser", "Calm Aroma Diffuser", "home", "43.00"),
    ("urban-boots", "Urban Chelsea Boots", "footwear", "124.00"),
    ("forest-hammock", "Forest Travel Hammock", "outdoors", "57.00"),
    ("prep-container", "Prep Glass Container Set", "kitchen", "41.50"),
)

FIRST_NAMES = (
    "Avery",
    "Casey",
    "Jordan",
    "Morgan",
    "Riley",
    "Taylor",
    "Cameron",
    "Drew",
    "Jamie",
    "Quinn",
)
LAST_NAMES = (
    "Anderson",
    "Bennett",
    "Carter",
    "Diaz",
    "Evans",
    "Foster",
    "Garcia",
    "Hayes",
    "Ito",
    "Johnson",
)


def _product_profiles() -> tuple[_ProductProfile, ...]:
    profiles: list[_ProductProfile] = []
    for key, name, category, price in PRODUCT_DEFINITIONS:
        selection_weight = 1
        refund_probability = 0.06
        reason_weights = DEFAULT_REASON_WEIGHTS

        if name == HIGH_REFUND_PRODUCT:
            selection_weight = 3
            refund_probability = 0.38
            reason_weights = (
                (RefundReason.DEFECTIVE, 65),
                (RefundReason.DAMAGED, 25),
                (RefundReason.OTHER, 10),
            )
        elif name == SIZE_REFUND_PRODUCT:
            selection_weight = 3
            refund_probability = 0.29
            reason_weights = (
                (RefundReason.SIZE_ISSUE, 80),
                (RefundReason.CHANGED_MIND, 12),
                (RefundReason.OTHER, 8),
            )
        elif name == LOW_REFUND_PRODUCT:
            selection_weight = 2
            refund_probability = 0.025

        profiles.append(
            _ProductProfile(
                product=ProductSeed(
                    key=key,
                    name=name,
                    category=category,
                    price=Decimal(price),
                    created_at=DATASET_REFERENCE_DATE - timedelta(days=365),
                ),
                selection_weight=selection_weight,
                refund_probability=refund_probability,
                reason_weights=reason_weights,
            )
        )
    return tuple(profiles)


def _weighted_choice(
    rng: random.Random, weighted_values: tuple[tuple[T, int], ...]
) -> T:
    values, weights = zip(*weighted_values, strict=True)
    return rng.choices(values, weights=weights, k=1)[0]


def _order_status(rng: random.Random, age_days: int) -> OrderStatus:
    if age_days <= 14:
        weights = (
            (OrderStatus.PENDING, 15),
            (OrderStatus.PAID, 20),
            (OrderStatus.SHIPPED, 25),
            (OrderStatus.DELIVERED, 35),
            (OrderStatus.CANCELLED, 5),
        )
    elif age_days <= 30:
        weights = (
            (OrderStatus.PAID, 10),
            (OrderStatus.SHIPPED, 20),
            (OrderStatus.DELIVERED, 65),
            (OrderStatus.CANCELLED, 5),
        )
    else:
        weights = (
            (OrderStatus.PAID, 3),
            (OrderStatus.SHIPPED, 7),
            (OrderStatus.DELIVERED, 84),
            (OrderStatus.CANCELLED, 6),
        )
    return _weighted_choice(rng, weights)


def _refund_status(
    rng: random.Random, requested_at: datetime
) -> tuple[RefundStatus, datetime | None]:
    age_days = (DATASET_REFERENCE_DATE - requested_at).days
    if age_days < 1:
        return RefundStatus.REQUESTED, None

    if age_days >= 8:
        status = _weighted_choice(
            rng,
            (
                (RefundStatus.PROCESSED, 60),
                (RefundStatus.APPROVED, 15),
                (RefundStatus.REJECTED, 15),
                (RefundStatus.REQUESTED, 10),
            ),
        )
    else:
        status = _weighted_choice(
            rng,
            (
                (RefundStatus.REQUESTED, 55),
                (RefundStatus.APPROVED, 30),
                (RefundStatus.REJECTED, 10),
                (RefundStatus.PROCESSED, 5),
            ),
        )

    if status not in {RefundStatus.PROCESSED, RefundStatus.REJECTED}:
        return status, None

    processed_at = requested_at + timedelta(days=rng.randint(1, min(7, age_days)))
    return status, processed_at


def generate_seed_data() -> GeneratedSeedData:
    rng = random.Random(RANDOM_SEED)
    profiles = _product_profiles()
    profile_by_key = {profile.product.key: profile for profile in profiles}

    customers = tuple(
        CustomerSeed(
            name=f"{FIRST_NAMES[index % 10]} {LAST_NAMES[(index // 10) % 10]} {index + 1:03d}",
            email=f"customer{index + 1:04d}@example.com",
            created_at=DATASET_REFERENCE_DATE
            - timedelta(days=rng.randint(181, 720), seconds=rng.randint(0, 86_399)),
        )
        for index in range(500)
    )

    products = tuple(profile.product for profile in profiles)
    profile_weights = [profile.selection_weight for profile in profiles]
    orders: list[OrderSeed] = []

    for _ in range(2_000):
        age_seconds = rng.randint(0, (180 * 86_400) - 1)
        ordered_at = DATASET_REFERENCE_DATE - timedelta(seconds=age_seconds)
        age_days = (DATASET_REFERENCE_DATE - ordered_at).days
        status = _order_status(rng, age_days)
        customer_index = rng.randrange(len(customers))
        item_count = rng.choices((2, 3, 4), weights=(30, 45, 25), k=1)[0]

        selected_keys: list[str] = []
        while len(selected_keys) < item_count:
            profile = rng.choices(profiles, weights=profile_weights, k=1)[0]
            if profile.product.key not in selected_keys:
                selected_keys.append(profile.product.key)

        items: list[OrderItemSeed] = []
        for product_key in selected_keys:
            profile = profile_by_key[product_key]
            quantity = rng.choices((1, 2, 3), weights=(75, 20, 5), k=1)[0]
            line_total = profile.product.price * quantity
            refund: RefundSeed | None = None

            if status == OrderStatus.DELIVERED and rng.random() < profile.refund_probability:
                requested_at = ordered_at + timedelta(
                    days=rng.randint(1, 21), seconds=rng.randint(0, 43_200)
                )
                if requested_at <= DATASET_REFERENCE_DATE:
                    refund_status, processed_at = _refund_status(rng, requested_at)
                    refund = RefundSeed(
                        reason=_weighted_choice(rng, profile.reason_weights),
                        amount=line_total,
                        status=refund_status,
                        requested_at=requested_at,
                        processed_at=processed_at,
                    )

            items.append(
                OrderItemSeed(
                    product_key=product_key,
                    quantity=quantity,
                    unit_price=profile.product.price,
                    refund=refund,
                )
            )

        total_amount = sum(
            (item.unit_price * item.quantity for item in items), start=Decimal("0.00")
        )
        orders.append(
            OrderSeed(
                customer_index=customer_index,
                status=status,
                ordered_at=ordered_at,
                total_amount=total_amount,
                items=tuple(items),
            )
        )

    return GeneratedSeedData(
        customers=customers,
        products=products,
        orders=tuple(orders),
    )


def summarize_product_patterns(
    data: GeneratedSeedData,
) -> tuple[ProductPatternSummary, ...]:
    names_by_key = {product.key: product.name for product in data.products}
    tracked_names = {HIGH_REFUND_PRODUCT, SIZE_REFUND_PRODUCT, LOW_REFUND_PRODUCT}
    counters = {
        name: {
            "units": 0,
            "items": 0,
            "refunded_units": 0,
            "refunded_items": 0,
            "reasons": Counter(),
        }
        for name in tracked_names
    }

    for order in data.orders:
        for item in order.items:
            name = names_by_key[item.product_key]
            if name not in counters:
                continue
            counts = counters[name]
            counts["units"] += item.quantity
            counts["items"] += 1
            if item.refund is not None:
                counts["refunded_units"] += item.quantity
                counts["refunded_items"] += 1
                counts["reasons"][item.refund.reason] += 1

    summaries: list[ProductPatternSummary] = []
    for name in (HIGH_REFUND_PRODUCT, SIZE_REFUND_PRODUCT, LOW_REFUND_PRODUCT):
        counts = counters[name]
        most_common = counts["reasons"].most_common(1)
        summaries.append(
            ProductPatternSummary(
                product_name=name,
                units_sold=counts["units"],
                sold_order_items=counts["items"],
                refunded_units=counts["refunded_units"],
                refunded_order_items=counts["refunded_items"],
                refund_rate=(
                    Decimal(counts["refunded_items"])
                    / Decimal(counts["items"])
                    * Decimal("100")
                ).quantize(Decimal("0.01")),
                most_common_reason=most_common[0][0] if most_common else None,
            )
        )
    return tuple(summaries)
