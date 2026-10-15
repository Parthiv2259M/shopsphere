from functools import wraps

from flask import Blueprint, jsonify, request
from flask_login import current_user

from ..extensions import db
from ..models import Cart, CartItem, Order, OrderItem, Product, User
from ..orders import place_order
from ..services.validators import ValidationError, positive_int

api_bp = Blueprint("api", __name__)


def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else request.args.get("token", "")
        user = User.query.filter_by(api_token=token).first() if token else None
        if not user:
            return jsonify(error="Valid bearer token required."), 401
        from flask_login import login_user

        login_user(user)
        return view(*args, **kwargs)
    return wrapped


@api_bp.get("/products")
def list_products():
    query = Product.query.filter_by(active=True)
    term = request.args.get("q", "").strip()[:100]
    if term:
        query = query.filter(Product.name.ilike(f"%{term}%"))
    try:
        page = max(1, int(request.args.get("page", "1")))
        per_page = min(50, max(1, int(request.args.get("per_page", "20"))))
    except ValueError:
        return jsonify(error="page and per_page must be integers."), 400
    pagination = query.order_by(Product.id).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(
        items=[{
            "id": p.id, "name": p.name, "slug": p.slug, "price": str(p.price),
            "stock": p.stock, "category": p.category.slug,
        } for p in pagination.items],
        page=page, per_page=per_page, total=pagination.total,
    )


@api_bp.route("/cart", methods=["GET", "POST"])
@token_required
def cart_endpoint():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        product = db.session.get(Product, payload.get("product_id"))
        try:
            quantity = positive_int(payload.get("quantity", 1))
        except ValidationError as exc:
            return jsonify(error=str(exc)), 400
        if not product or not product.active:
            return jsonify(error="Product not found."), 404
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        new_quantity = quantity + (item.quantity if item else 0)
        if new_quantity > product.stock:
            return jsonify(error="Requested quantity exceeds available stock."), 409
        if item:
            item.quantity = new_quantity
        else:
            db.session.add(CartItem(cart=cart, product=product, quantity=quantity))
        db.session.commit()
    return jsonify(items=[{
        "product_id": item.product_id, "name": item.product.name,
        "quantity": item.quantity, "unit_price": str(item.product.price),
    } for item in cart.items])


@api_bp.route("/orders", methods=["GET", "POST"])
@token_required
def orders_endpoint():
    if request.method == "POST":
        try:
            order = place_order(current_user.id)
        except (ValueError, Exception) as exc:
            db.session.rollback()
            return jsonify(error=str(exc)), 400
        return jsonify(id=order.id, status=order.status, total=str(order.total)), 201
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return jsonify(orders=[{
        "id": order.id, "status": order.status, "total": str(order.total),
        "items": [{"name": item.product_name, "quantity": item.quantity} for item in order.items],
    } for order in orders])
