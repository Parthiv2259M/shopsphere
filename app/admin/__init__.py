import decimal
from functools import wraps
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Category, Order, Product

admin_bp = Blueprint("admin", __name__)


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@admin_bp.get("/")
@admin_required
def dashboard():
    orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    sales = db.session.query(db.func.coalesce(db.func.sum(Order.total), 0)).filter(
        Order.status != "CANCELLED"
    ).scalar()
    return render_template("admin/dashboard.html", orders=orders, sales=sales)


@admin_bp.route("/products", methods=["GET", "POST"])
@admin_required
def products():
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            slug = request.form.get("slug", "").strip()
            category_id = request.form.get("category_id", "")
            if category_id == "":
                raise ValueError("Category is required.")
            category = db.session.get(Category, int(category_id))
            if category is None:
                raise ValueError("Category is invalid.")
            price = Decimal(request.form.get("price", ""))
            stock = int(request.form.get("stock", ""))
            if not name or not slug or price < 0 or stock < 0:
                raise ValueError("Complete product details with non-negative price and stock.")
            product = Product(
                name=name, slug=slug, description=request.form.get("description", "").strip(),
                price=price, stock=stock, category=category,
                image_url=request.form.get("image_url", "").strip(),
            )
            db.session.add(product)
            db.session.commit()
            flash("Product created.", "success")
        except (ValueError, TypeError, decimal.InvalidOperation):
            db.session.rollback()
            flash("Invalid product details.", "danger")
        return redirect(url_for("admin.products"))
    return render_template(
        "admin/products.html", products=Product.query.order_by(Product.name).all(),
        categories=Category.query.order_by(Category.name).all(),
    )


@admin_bp.post("/products/<int:product_id>/delete")
@admin_required
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    product.active = False
    db.session.commit()
    return redirect(url_for("admin.products"))


@admin_bp.get("/orders")
@admin_required
def orders():
    return render_template("admin/orders.html", orders=Order.query.order_by(Order.created_at.desc()).all())


@admin_bp.post("/orders/<int:order_id>/status")
@admin_required
def update_order_status(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    status = request.form.get("status", "").upper()
    from ..orders import ALLOWED_TRANSITIONS

    if status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        abort(400, description="Invalid order status transition.")
    order.status = status
    db.session.commit()
    return redirect(url_for("admin.orders"))


@admin_bp.get("/reports/sales")
@admin_required
def sales_report():
    rows = db.session.query(
        db.func.date(Order.created_at).label("day"),
        db.func.sum(Order.total).label("sales"),
    ).filter(Order.status != "CANCELLED").group_by(db.func.date(Order.created_at)).all()
    return render_template("admin/sales.html", rows=rows)
