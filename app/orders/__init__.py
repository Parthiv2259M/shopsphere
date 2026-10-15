from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Cart, CartItem, Coupon, Order, OrderItem, Product, Review
from ..services.coupon import CouponError, validate_coupon
from ..services.inventory import InventoryError, change_stock
from ..services.pricing import calculate_totals

orders_bp = Blueprint("orders", __name__)
ALLOWED_TRANSITIONS = {
    "PLACED": {"PAID"},
    "PAID": {"SHIPPED"},
    "SHIPPED": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}


def place_order(user_id):
    cart = Cart.query.filter_by(user_id=user_id).first()
    if not cart or not cart.items:
        raise ValueError("Your cart is empty.")
    subtotal = sum((item.product.price * item.quantity for item in cart.items), start=Decimal("0"))
    discount = Decimal("0")
    if cart.coupon:
        discount = validate_coupon(cart.coupon, subtotal)
    totals = calculate_totals(subtotal, discount)
    order = Order(user_id=user_id, coupon_code=cart.coupon.code if cart.coupon else None, **totals)
    db.session.add(order)
    try:
        db.session.flush()
        for item in list(cart.items):
            if not item.product.active:
                raise InventoryError(f"{item.product.name} is no longer available.")
            change_stock(item.product_id, -item.quantity)
            db.session.add(OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                product_name=item.product.name,
                unit_price=item.product.price,
                quantity=item.quantity,
            ))
        if cart.coupon:
            coupon = cart.coupon
            validate_coupon(coupon, subtotal)
            coupon.usage_count += 1
        CartItem.query.filter_by(cart_id=cart.id).delete(synchronize_session=False)
        cart.coupon = None
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return order


@orders_bp.post("/checkout")
@login_required
def checkout():
    try:
        order = place_order(current_user.id)
        return redirect(url_for("orders.order_detail", order_id=order.id))
    except (ValueError, CouponError, InventoryError) as exc:
        flash(str(exc), "danger")
        return redirect(url_for("cart.view_cart"))


@orders_bp.get("/orders")
@login_required
def order_history():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("orders/history.html", orders=orders)


@orders_bp.get("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    return render_template("orders/detail.html", order=order)


@orders_bp.post("/orders/<int:order_id>/cancel")
@login_required
def cancel_order(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    if order.status not in ("PLACED", "PAID"):
        abort(400, description="Only orders before shipment may be cancelled.")
    try:
        for item in order.items:
            change_stock(item.product_id, item.quantity)
        order.status = "CANCELLED"
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return redirect(url_for("orders.order_detail", order_id=order.id))


@orders_bp.post("/products/<int:product_id>/reviews")
@login_required
def add_review(product_id):
    product = db.session.get(Product, product_id)
    if not product or not product.active:
        abort(404)
    purchased = (
        Order.query.join(OrderItem)
        .filter(Order.user_id == current_user.id, OrderItem.product_id == product_id,
                Order.status != "CANCELLED")
        .first()
    )
    if not purchased:
        abort(403, description="Only verified purchasers can review this product.")
    if Review.query.filter_by(user_id=current_user.id, product_id=product_id).first():
        abort(400, description="You have already reviewed this product.")
    try:
        rating = int(request.form.get("rating", ""))
    except (TypeError, ValueError):
        abort(400, description="Rating must be between 1 and 5.")
    if rating < 1 or rating > 5:
        abort(400, description="Rating must be between 1 and 5.")
    db.session.add(Review(
        user_id=current_user.id, product_id=product_id, rating=rating,
        body=request.form.get("body", "").strip()[:2000],
    ))
    db.session.commit()
    return redirect(url_for("products.product_detail", slug=product.slug))
