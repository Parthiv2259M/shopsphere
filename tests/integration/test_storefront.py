from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Cart, CartItem, Category, Coupon, Order, OrderItem, Product, Review, User
from app.orders import place_order


@pytest.mark.integration
@pytest.mark.parametrize("query", [
    "", "?q=mug", "?category=home", "?sort=price_asc", "?sort=price_desc",
    "?page=999", "?page=bad", "?per_page=0", "?per_page=999",
    "?q=%27%20OR%201%3D1--", "?min_price=bad", "?max_price=-4",
])
def test_catalog_handles_queries_and_invalid_parameters(client, product, query):
    response = client.get("/products" + query)
    assert response.status_code == 200
    assert b"Ceramic Mug" in response.data if not query.startswith("?q=%27") else b"No products found" in response.data


@pytest.mark.integration
def test_category_filter_returns_empty(client, category):
    response = client.get("/products?category=unknown")
    assert response.status_code == 200
    assert b"No products found" in response.data


@pytest.mark.integration
def test_product_detail_and_missing(client, product):
    assert client.get("/products/ceramic-mug").status_code == 200
    assert client.get("/products/missing").status_code == 404


@pytest.mark.integration
@pytest.mark.parametrize("quantity", ["0", "-1", "abc", "11", "100"])
def test_add_cart_rejects_invalid_or_overstock(client, customer, product, quantity):
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    response = client.post(f"/cart/add/{product.id}", data={"quantity": quantity}, follow_redirects=True)
    assert response.status_code == 200
    assert CartItem.query.count() == 0


@pytest.mark.integration
def test_add_update_remove_cart_and_totals(client, customer, product):
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    client.post(f"/cart/add/{product.id}", data={"quantity": "2"})
    item = CartItem.query.one()
    response = client.post(f"/cart/update/{item.id}", data={"quantity": "3"}, follow_redirects=True)
    assert response.status_code == 200
    assert CartItem.query.one().quantity == 3
    assert b"Rs. 135.00" in response.data
    response = client.post(f"/cart/remove/{item.id}", follow_redirects=True)
    assert response.status_code == 200
    assert CartItem.query.count() == 0


@pytest.mark.integration
def test_cart_item_cannot_be_changed_by_other_user(client, customer, product, db):
    other = User(name="Other", email="other@example.com")
    other.set_password("StrongPass1!")
    db.session.add(other)
    db.session.flush()
    db.session.add(Cart(user_id=other.id))
    db.session.add(CartItem(cart_id=customer.cart.id, product_id=product.id, quantity=1))
    db.session.commit()
    item_id = CartItem.query.one().id
    client.post("/login", data={"email": "other@example.com", "password": "StrongPass1!"})
    assert client.post(f"/cart/update/{item_id}", data={"quantity": 2}).status_code == 404
    assert CartItem.query.one().quantity == 1


@pytest.mark.integration
def test_coupon_apply_and_remove(client, customer, product, db):
    coupon = Coupon(code="SAVE10", kind="percentage", value=10, min_order=100)
    db.session.add(coupon)
    db.session.commit()
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    client.post(f"/cart/add/{product.id}", data={"quantity": 1})
    assert client.post("/cart/coupon", data={"code": "save10"}, follow_redirects=True).status_code == 200
    assert Cart.query.one().coupon.code == "SAVE10"
    assert client.post("/cart/coupon/remove", follow_redirects=True).status_code == 200
    assert Cart.query.one().coupon is None


@pytest.mark.integration
def test_coupon_rejection_is_reported(client, customer, product):
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    client.post(f"/cart/add/{product.id}", data={"quantity": 1})
    response = client.post("/cart/coupon", data={"code": "NOTREAL"}, follow_redirects=True)
    assert b"invalid or inactive" in response.data


@pytest.mark.integration
def test_checkout_creates_order_and_decrements_stock(client, customer, product):
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    client.post(f"/cart/add/{product.id}", data={"quantity": 2})
    response = client.post("/checkout", follow_redirects=True)
    order = Order.query.one()
    assert response.status_code == 200
    assert order.status == "PLACED"
    assert order.total == Decimal("640.00")
    assert product.stock == 8
    assert OrderItem.query.one().quantity == 2
    assert CartItem.query.count() == 0


@pytest.mark.integration
def test_checkout_empty_cart_stays_in_cart(client, customer):
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    response = client.post("/checkout", follow_redirects=True)
    assert b"cart is empty" in response.data
    assert Order.query.count() == 0


@pytest.mark.integration
def test_checkout_stock_race_rolls_back_order_and_cart(db, customer, product):
    cart = Cart.query.filter_by(user_id=customer.id).one()
    db.session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=11))
    db.session.commit()
    with pytest.raises(ValueError, match="stock"):
        place_order(customer.id)
    assert Order.query.count() == 0
    assert CartItem.query.one().quantity == 11
    assert product.stock == 10


@pytest.mark.integration
def test_cancel_before_shipping_restores_inventory(client, customer, product):
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    client.post(f"/cart/add/{product.id}", data={"quantity": 2})
    client.post("/checkout")
    order = Order.query.one()
    assert product.stock == 8
    assert client.post(f"/orders/{order.id}/cancel").status_code == 302
    assert order.status == "CANCELLED"
    assert product.stock == 10


@pytest.mark.integration
def test_cancel_after_shipped_rejected(client, customer, product, db):
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    client.post(f"/cart/add/{product.id}", data={"quantity": 1})
    client.post("/checkout")
    order = Order.query.one()
    order.status = "SHIPPED"
    db.session.commit()
    assert client.post(f"/orders/{order.id}/cancel").status_code == 400


@pytest.mark.integration
def test_review_requires_purchase_and_enforces_one_review(client, customer, product, db):
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    assert client.post(f"/products/{product.id}/reviews", data={"rating": 5}).status_code == 403
    order = Order(user_id=customer.id, subtotal=250, discount=0, tax=45, shipping=50, total=345)
    db.session.add(order)
    db.session.flush()
    db.session.add(OrderItem(order_id=order.id, product_id=product.id, product_name=product.name,
                             unit_price=product.price, quantity=1))
    db.session.commit()
    assert client.post(f"/products/{product.id}/reviews", data={"rating": 5, "body": "Great"}).status_code == 302
    assert Review.query.one().rating == 5
    assert client.post(f"/products/{product.id}/reviews", data={"rating": 4}).status_code == 400


@pytest.mark.integration
@pytest.mark.parametrize("rating", ["0", "6", "oops", ""])
def test_review_rating_bounds(client, customer, product, db, rating):
    order = Order(user_id=customer.id, subtotal=250, discount=0, tax=45, shipping=50, total=345)
    db.session.add(order)
    db.session.flush()
    db.session.add(OrderItem(order_id=order.id, product_id=product.id, product_name=product.name,
                             unit_price=product.price, quantity=1))
    db.session.commit()
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    assert client.post(f"/products/{product.id}/reviews", data={"rating": rating}).status_code == 400


@pytest.mark.integration
def test_order_history_detail_and_owner_protection(client, customer, product, db):
    order = Order(user_id=customer.id, subtotal=250, discount=0, tax=45, shipping=50, total=345)
    db.session.add(order)
    db.session.commit()
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    assert client.get("/orders").status_code == 200
    assert client.get(f"/orders/{order.id}").status_code == 200
    assert client.get("/orders/999").status_code == 404


@pytest.mark.integration
def test_admin_product_create_archive_and_reports(client, admin, category, product):
    client.post("/login", data={"email": admin.email, "password": "StrongPass1!"})
    assert client.get("/admin/").status_code == 200
    response = client.post("/admin/products", data={
        "name": "New Item", "slug": "new-item", "price": "55.50",
        "stock": "4", "category_id": category.id,
    })
    assert response.status_code == 302
    created = Product.query.filter_by(slug="new-item").one()
    assert client.post(f"/admin/products/{created.id}/delete").status_code == 302
    assert created.active is False
    assert client.get("/admin/orders").status_code == 200
    assert client.get("/admin/reports/sales").status_code == 200


@pytest.mark.integration
@pytest.mark.parametrize("payload", [
    {"name": "", "slug": "a", "price": "1", "stock": "1", "category_id": "1"},
    {"name": "X", "slug": "x", "price": "-1", "stock": "1", "category_id": "1"},
    {"name": "X", "slug": "x", "price": "1", "stock": "-1", "category_id": "1"},
    {"name": "X", "slug": "x", "price": "wat", "stock": "1", "category_id": "1"},
])
def test_admin_product_invalid_form_is_not_created(client, admin, payload):
    client.post("/login", data={"email": admin.email, "password": "StrongPass1!"})
    assert client.post("/admin/products", data=payload, follow_redirects=True).status_code == 200
    assert Product.query.filter_by(slug="x").first() is None


@pytest.mark.integration
def test_admin_status_workflow(client, admin, customer, product, db):
    order = Order(user_id=customer.id, subtotal=250, discount=0, tax=45, shipping=50, total=345)
    db.session.add(order)
    db.session.commit()
    client.post("/login", data={"email": admin.email, "password": "StrongPass1!"})
    assert client.post(f"/admin/orders/{order.id}/status", data={"status": "PAID"}).status_code == 302
    assert order.status == "PAID"
    assert client.post(f"/admin/orders/{order.id}/status", data={"status": "DELIVERED"}).status_code == 400


@pytest.mark.integration
def test_registration_login_and_logout(client):
    response = client.post("/register", data={
        "name": "New Customer", "email": "NEW@Example.com", "password": "StrongPass1!",
    })
    assert response.status_code == 302
    user = User.query.one()
    assert user.email == "new@example.com"
    assert client.get("/account").status_code == 200
    assert client.post("/logout").status_code == 302


@pytest.mark.integration
@pytest.mark.parametrize("password", ["weak", "MissingUpper1", "MissingDigit!", "MissingSpecial1"])
def test_registration_rejects_bad_password(client, password):
    response = client.post("/register", data={
        "name": "New Customer", "email": "new@example.com", "password": password,
    }, follow_redirects=True)
    assert response.status_code == 200
    assert User.query.count() == 0


@pytest.mark.integration
def test_duplicate_email_is_case_insensitive(client, customer):
    response = client.post("/register", data={
        "name": "Duplicate", "email": customer.email.upper(), "password": "StrongPass1!",
    }, follow_redirects=True)
    assert b"already exists" in response.data
    assert User.query.count() == 1


@pytest.mark.integration
def test_login_rejects_invalid_credentials_and_unsafe_redirect(client, customer):
    assert client.post("/login", data={"email": customer.email, "password": "bad"}).status_code == 200
    response = client.post("/login?next=//evil.test", data={
        "email": customer.email, "password": "StrongPass1!",
    })
    assert response.status_code == 302
    assert response.location.endswith("/")


@pytest.mark.integration
def test_anonymous_admin_redirect_and_customer_forbidden(client, customer):
    assert client.get("/admin/").status_code == 302
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    assert client.get("/admin/").status_code == 403
