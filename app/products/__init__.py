from flask import Blueprint, abort, render_template, request
from sqlalchemy import or_

from ..models import Category, Product, Review

products_bp = Blueprint("products", __name__)


@products_bp.get("/")
@products_bp.get("/products")
def list_products():
    query = Product.query.filter_by(active=True)
    search = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "").strip()
    minimum = request.args.get("min_price", "")
    maximum = request.args.get("max_price", "")
    sort = request.args.get("sort", "name")
    try:
        page = max(1, min(100000, int(request.args.get("page", 1))))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = max(1, min(50, int(request.args.get("per_page", 12))))
    except (TypeError, ValueError):
        per_page = 12
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))
    if category:
        query = query.join(Category).filter(Category.slug == category)
    try:
        if minimum and float(minimum) >= 0:
            query = query.filter(Product.price >= float(minimum))
        if maximum and float(maximum) >= 0:
            query = query.filter(Product.price <= float(maximum))
    except (TypeError, ValueError):
        pass
    if sort == "price_asc":
        query = query.order_by(Product.price.asc(), Product.id.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc(), Product.id.asc())
    else:
        query = query.order_by(Product.name.asc())
    total_pages = max(1, (query.count() + per_page - 1) // per_page) if query.count() else 1
    page = min(page, total_pages)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template(
        "products/list.html",
        products=pagination.items,
        pagination=pagination,
        categories=Category.query.order_by(Category.name).all(),
        search=search,
    )


@products_bp.get("/products/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, active=True).first_or_404()
    return render_template(
        "products/detail.html",
        product=product,
        reviews=Review.query.filter_by(product_id=product.id).order_by(Review.created_at.desc()).all(),
    )
