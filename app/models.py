import secrets
from datetime import datetime, timezone
from decimal import Decimal

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")
    api_token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_hex(32))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    cart = db.relationship("Cart", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        from .services.validators import validate_password

        validate_password(password)
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def normalize_email(email):
        return email.strip().casefold()


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    products = db.relationship("Product", back_populates="category")


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False, index=True)
    slug = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False, default="")
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image_url = db.Column(db.String(500), nullable=False, default="")
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    category = db.relationship("Category", back_populates="products")
    reviews = db.relationship("Review", back_populates="product", cascade="all, delete-orphan")


class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey("coupon.id"))
    user = db.relationship("User", back_populates="cart")
    items = db.relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")
    coupon = db.relationship("Coupon")


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("cart.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    cart = db.relationship("Cart", back_populates="items")
    product = db.relationship("Product")
    __table_args__ = (db.UniqueConstraint("cart_id", "product_id"),)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="PLACED")
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    discount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    tax = db.Column(db.Numeric(10, 2), nullable=False)
    shipping = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    coupon_code = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    user = db.relationship("User")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product_name = db.Column(db.String(180), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    body = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    product = db.relationship("Product", back_populates="reviews")
    user = db.relationship("User")
    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id"),
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="rating_range"),
    )


class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    kind = db.Column(db.String(20), nullable=False)
    value = db.Column(db.Numeric(10, 2), nullable=False)
    expires_at = db.Column(db.DateTime)
    min_order = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    usage_limit = db.Column(db.Integer)
    usage_count = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
