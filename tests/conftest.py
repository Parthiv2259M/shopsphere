import os

import pytest

from app import create_app
from app.extensions import db as database
from app.models import Cart, Category, Product, User


def pytest_configure(config):
    os.makedirs("reports", exist_ok=True)


@pytest.fixture
def app():
    application = create_app("testing", {"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with application.app_context():
        database.create_all()
        yield application
        database.session.remove()
        database.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    yield database


def make_user(db, name="Test Customer", email="customer@example.com", role="customer"):
    user = User(name=name, email=User.normalize_email(email), role=role)
    user.set_password("StrongPass1!")
    db.session.add(user)
    db.session.flush()
    db.session.add(Cart(user_id=user.id))
    db.session.commit()
    return user


@pytest.fixture
def customer(db):
    return make_user(db)


@pytest.fixture
def admin(db):
    return make_user(db, "Admin User", "admin@example.com", "admin")


@pytest.fixture
def category(db):
    item = Category(name="Home", slug="home")
    db.session.add(item)
    db.session.commit()
    return item


@pytest.fixture
def product(db, category):
    item = Product(
        name="Ceramic Mug", slug="ceramic-mug", description="A handmade mug",
        price="250.00", stock=10, category_id=category.id,
    )
    db.session.add(item)
    db.session.commit()
    return item


@pytest.fixture
def auth_client(client, customer):
    client.post("/login", data={"email": customer.email, "password": "StrongPass1!"})
    return client
