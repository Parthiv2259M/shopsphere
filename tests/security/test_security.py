import re

import pytest

from app import create_app
from app.extensions import db
from app.models import User
from tests.conftest import make_user


@pytest.mark.security
def test_passwords_are_hashed_and_checked(db):
    user = make_user(db)
    assert user.password_hash != "StrongPass1!"
    assert user.check_password("StrongPass1!")
    assert not user.check_password("wrong")


@pytest.mark.security
def test_email_uniqueness_is_case_insensitive(client, customer):
    response = client.post("/register", data={
        "name": "Injected", "email": customer.email.swapcase(),
        "password": "StrongPass1!",
    }, follow_redirects=True)
    assert b"already exists" in response.data
    assert User.query.count() == 1


@pytest.mark.security
@pytest.mark.parametrize("payload", [
    "' OR '1'='1", "'; DROP TABLE product; --", "admin'--", "%27%20OR%201%3D1",
])
def test_search_sql_injection_payloads_are_data(client, product, payload):
    response = client.get("/products", query_string={"q": payload})
    assert response.status_code == 200
    assert User.query.count() >= 0
    assert product.name.encode() not in response.data


@pytest.mark.security
def test_template_escapes_untrusted_product_text(client, product, db):
    product.name = "<script>alert(1)</script>"
    db.session.commit()
    response = client.get("/products")
    assert b"<script>alert(1)</script>" not in response.data
    assert b"&lt;script&gt;" in response.data


@pytest.mark.security
def test_admin_access_controls(client, customer):
    assert client.get("/admin/products").status_code == 302
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    assert client.get("/admin/products").status_code == 403


@pytest.mark.security
def test_api_requires_valid_bearer_token(client, customer):
    assert client.get("/api/v1/orders").status_code == 401
    assert client.get("/api/v1/orders", headers={
        "Authorization": f"Bearer {customer.api_token}",
    }).status_code == 200


@pytest.mark.security
def test_csrf_rejects_form_without_token():
    application = create_app("testing", {
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": True,
    })
    with application.app_context():
        db.create_all()
        test_client = application.test_client()
        response = test_client.post("/login", data={"email": "a@example.com", "password": "bad"})
        assert response.status_code == 400
        db.drop_all()


@pytest.mark.security
def test_csrf_accepts_valid_token_for_browser_form():
    application = create_app("testing", {
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": True,
    })
    with application.app_context():
        db.create_all()
        test_client = application.test_client()
        page = test_client.get("/login")
        token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
        response = test_client.post("/login", data={
            "csrf_token": token, "email": "unknown@example.com", "password": "bad",
        })
        assert response.status_code == 200
        db.drop_all()


@pytest.mark.security
def test_next_parameter_does_not_allow_external_redirect(client, customer):
    response = client.post("/login?next=https://evil.example", data={
        "email": customer.email, "password": "StrongPass1!",
    })
    assert response.status_code == 302
    assert response.location.endswith("/")
