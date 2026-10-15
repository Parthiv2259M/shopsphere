from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Cart, CartItem, Coupon, Product
from ..services.coupon import CouponError, validate_coupon
from ..services.pricing import calculate_totals
from ..services.validators import ValidationError, positive_int

cart_bp = Blueprint("cart", __name__)


def user_cart():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.flush()
    return cart


@cart_bp.get("/cart")
@login_required
def view_cart():
    cart = user_cart()
    subtotal = sum((item.product.price * item.quantity for item in cart.items), start=0)
    discount = 0
    if cart.coupon:
        try:
            discount = validate_coupon(cart.coupon, subtotal)
        except CouponError:
            discount = 0
    totals = calculate_totals(subtotal, discount)
    return render_template("cart/view.html", cart=cart, totals=totals)


@cart_bp.post("/cart/add/<int:product_id>")
@login_required
def add_to_cart(product_id):
    product = db.session.get(Product, product_id)
    if not product or not product.active:
        return "Product not found", 404
    try:
        quantity = positive_int(request.form.get("quantity", 1))
        cart = user_cart()
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        new_quantity = quantity + (item.quantity if item else 0)
        if new_quantity > product.stock:
            raise ValidationError("Requested quantity exceeds available stock.")
        if item:
            item.quantity = new_quantity
        else:
            db.session.add(CartItem(cart=cart, product=product, quantity=quantity))
        db.session.commit()
        flash("Added to your cart.", "success")
    except ValidationError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("cart.view_cart"))


@cart_bp.post("/cart/update/<int:item_id>")
@login_required
def update_cart_item(item_id):
    item = CartItem.query.join(Cart).filter(
        CartItem.id == item_id, Cart.user_id == current_user.id
    ).first_or_404()
    try:
        quantity = positive_int(request.form.get("quantity"))
        if quantity > item.product.stock:
            raise ValidationError("Requested quantity exceeds available stock.")
        item.quantity = quantity
        db.session.commit()
    except ValidationError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("cart.view_cart"))


@cart_bp.post("/cart/remove/<int:item_id>")
@login_required
def remove_cart_item(item_id):
    item = CartItem.query.join(Cart).filter(
        CartItem.id == item_id, Cart.user_id == current_user.id
    ).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("cart.view_cart"))


@cart_bp.post("/cart/coupon")
@login_required
def apply_coupon():
    cart = user_cart()
    code = request.form.get("code", "").strip().upper()
    coupon = Coupon.query.filter_by(code=code).first()
    subtotal = sum((item.product.price * item.quantity for item in cart.items), start=0)
    try:
        validate_coupon(coupon, subtotal)
        cart.coupon = coupon
        db.session.commit()
        flash("Coupon applied.", "success")
    except CouponError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("cart.view_cart"))


@cart_bp.post("/cart/coupon/remove")
@login_required
def remove_coupon():
    user_cart().coupon = None
    db.session.commit()
    return redirect(url_for("cart.view_cart"))
