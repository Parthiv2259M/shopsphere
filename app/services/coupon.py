from datetime import datetime
from decimal import Decimal

from .pricing import money


class CouponError(ValueError):
    pass


def validate_coupon(coupon, subtotal, now=None):
    now = now or datetime.utcnow()
    subtotal = money(subtotal)
    if not coupon:
        raise CouponError("Coupon is invalid or inactive.")
    if getattr(coupon, "active", True) is False:
        raise CouponError("Coupon is invalid or inactive.")
    if coupon.expires_at and coupon.expires_at <= now:
        raise CouponError("Coupon has expired.")
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise CouponError("Coupon usage limit has been reached.")
    if subtotal < money(coupon.min_order):
        raise CouponError("Order does not meet the coupon minimum.")
    if coupon.kind not in ("percentage", "fixed"):
        raise CouponError("Coupon type is invalid.")
    if coupon.kind == "percentage":
        if not Decimal("0") < Decimal(coupon.value) <= Decimal("100"):
            raise CouponError("Coupon percentage must be between 0 and 100.")
        return money(subtotal * Decimal(coupon.value) / Decimal("100"))
    return min(subtotal, max(Decimal("0.00"), money(coupon.value)))
