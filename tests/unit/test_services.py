from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.models import Coupon
from app.services.coupon import CouponError, validate_coupon
from app.services.inventory import InventoryError, change_stock
from app.services.pricing import calculate_totals, money
from app.services.validators import ValidationError, positive_int, validate_email, validate_password


@pytest.mark.unit
@pytest.mark.parametrize("password", ["", "short", "alllowercase1!", "ALLUPPER1!", "NoNumber!!", "NoSpecial11"])
def test_password_rules_reject_weak(password):
    with pytest.raises(ValidationError):
        validate_password(password)


@pytest.mark.unit
@pytest.mark.parametrize("password", ["Abcdef1!", "Pass word2$", "X123456a#"])
def test_password_rules_accept_strong(password):
    assert validate_password(password)


@pytest.mark.unit
@pytest.mark.parametrize("address,expected", [
    (" USER@Example.COM ", "user@example.com"), ("a+b@shop.co", "a+b@shop.co"),
    ("x.y@sub.domain.org", "x.y@sub.domain.org"),
])
def test_email_normalization(address, expected):
    assert validate_email(address) == expected


@pytest.mark.unit
@pytest.mark.parametrize("address", ["", "plain", "a@", "@b.com", "a b@c.com", None])
def test_email_validation_rejects_malformed(address):
    with pytest.raises(ValidationError):
        validate_email(address)


@pytest.mark.unit
@pytest.mark.parametrize("value,expected", [(1, 1), ("2", 2), ("0004", 4), (True, 1)])
def test_positive_integer_accepts_positive_values(value, expected):
    assert positive_int(value) == expected


@pytest.mark.unit
@pytest.mark.parametrize("value", [0, -1, "0", "-9", "abc", None, 1.5])
def test_positive_integer_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        positive_int(value)


@pytest.mark.unit
@pytest.mark.parametrize("value,expected", [
    ("1.005", Decimal("1.01")), ("1.004", Decimal("1.00")),
    ("-2.355", Decimal("-2.36")), (0, Decimal("0.00")),
])
def test_money_rounds_half_up(value, expected):
    assert money(value) == expected


@pytest.mark.unit
@pytest.mark.parametrize("subtotal,ship", [
    ("0", "50.00"), ("1", "50.00"), ("998.99", "50.00"),
    ("999", "0.00"), ("1200", "0.00"),
])
def test_tax_shipping_boundary(subtotal, ship):
    totals = calculate_totals(Decimal(subtotal))
    assert totals["shipping"] == Decimal(ship)
    assert totals["tax"] == money(Decimal(subtotal) * Decimal("0.18"))


@pytest.mark.unit
def test_coupon_fixed_and_percentage_limits():
    coupon = Coupon(code="TEN", kind="fixed", value=25, min_order=50)
    assert validate_coupon(coupon, 100) == Decimal("25.00")
    coupon.kind, coupon.value = "percentage", 15
    assert validate_coupon(coupon, 100) == Decimal("15.00")
    coupon.value = 150
    with pytest.raises(CouponError):
        validate_coupon(coupon, 100)


@pytest.mark.unit
@pytest.mark.parametrize("attrs,subtotal,message", [
    ({"active": False}, 100, "invalid"),
    ({"expires_at": datetime.utcnow() - timedelta(seconds=1)}, 100, "expired"),
    ({"usage_limit": 1, "usage_count": 1}, 100, "limit"),
    ({"min_order": 100}, 99, "minimum"),
    ({"kind": "bogus"}, 100, "type"),
])
def test_coupon_rejects_unusable_coupon(attrs, subtotal, message):
    values = dict(code="EDGE", kind="fixed", value=5, active=True, usage_count=0,
                  min_order=0, usage_limit=None, expires_at=None)
    values.update(attrs)
    coupon = Coupon(**values)
    with pytest.raises(CouponError, match=message):
        validate_coupon(coupon, subtotal)


@pytest.mark.unit
def test_discount_cannot_exceed_subtotal():
    result = calculate_totals("10", "99")
    assert result["discount"] == Decimal("10.00")
    assert result["tax"] == Decimal("0.00")
    assert result["total"] == Decimal("50.00")


@pytest.mark.unit
def test_atomic_inventory_change_prevents_negative_stock(db, product):
    change_stock(product.id, -3)
    db.session.commit()
    db.session.refresh(product)
    assert product.stock == 7
    with pytest.raises(InventoryError):
        change_stock(product.id, -8)
    db.session.rollback()
    db.session.refresh(product)
    assert product.stock == 7


@pytest.mark.unit
def test_inventory_rejects_missing_product(db):
    with pytest.raises(InventoryError):
        change_stock(99999, -1)


@pytest.mark.unit
def test_inventory_restocks(db, product):
    change_stock(product.id, 2)
    db.session.commit()
    db.session.refresh(product)
    assert product.stock == 12
