import pytest

from app.models import CartItem, Order


@pytest.mark.api
def test_products_api_schema_and_pagination(client, product):
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    data = response.get_json()
    assert set(data) == {"items", "page", "per_page", "total"}
    assert set(data["items"][0]) == {"id", "name", "slug", "price", "stock", "category"}
    assert data["total"] == 1


@pytest.mark.api
@pytest.mark.parametrize("params", ["?page=nope", "?per_page=x", "?page=0"])
def test_products_api_invalid_pagination(client, product, params):
    response = client.get("/api/v1/products" + params)
    if params == "?page=0":
        assert response.status_code == 200
        assert response.get_json()["page"] == 1
    else:
        assert response.status_code == 400


@pytest.mark.api
def test_products_api_search_empty(client, product):
    assert client.get("/api/v1/products?q=absent").get_json()["total"] == 0


@pytest.mark.api
def test_cart_api_requires_token(client):
    assert client.get("/api/v1/cart").status_code == 401
    assert client.post("/api/v1/cart", json={}).status_code == 401


@pytest.mark.api
def test_cart_api_read_and_add(client, customer, product):
    headers = {"Authorization": f"Bearer {customer.api_token}"}
    assert client.get("/api/v1/cart", headers=headers).get_json()["items"] == []
    response = client.post("/api/v1/cart", headers=headers, json={
        "product_id": product.id, "quantity": 2,
    })
    assert response.status_code == 200
    assert response.get_json()["items"][0]["quantity"] == 2
    assert CartItem.query.one().quantity == 2


@pytest.mark.api
@pytest.mark.parametrize("payload,status", [
    ({"product_id": 1, "quantity": 0}, 400),
    ({"product_id": 1, "quantity": "nope"}, 400),
    ({"product_id": 99999, "quantity": 1}, 404),
    ({"product_id": 1, "quantity": 100}, 409),
    ({"product_id": 1, "quantity": 1}, 200),
])
def test_cart_api_validates_payload(client, customer, product, payload, status):
    payload["product_id"] = product.id if payload["product_id"] == 1 else payload["product_id"]
    response = client.post("/api/v1/cart", headers={
        "Authorization": f"Bearer {customer.api_token}",
    }, json=payload)
    assert response.status_code == status


@pytest.mark.api
def test_cart_api_rejects_invalid_token(client):
    response = client.get("/api/v1/cart", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401


@pytest.mark.api
def test_order_api_checkout_and_history(client, customer, product):
    headers = {"Authorization": f"Bearer {customer.api_token}"}
    client.post("/api/v1/cart", headers=headers, json={"product_id": product.id, "quantity": 1})
    response = client.post("/api/v1/orders", headers=headers)
    assert response.status_code == 201
    assert response.get_json()["status"] == "PLACED"
    assert Order.query.count() == 1
    history = client.get("/api/v1/orders", headers=headers).get_json()
    assert history["orders"][0]["id"] == response.get_json()["id"]
    assert history["orders"][0]["items"][0]["name"] == product.name


@pytest.mark.api
def test_order_api_rejects_empty_cart(client, customer):
    response = client.post("/api/v1/orders", headers={
        "Authorization": f"Bearer {customer.api_token}",
    })
    assert response.status_code == 400
    assert "empty" in response.get_json()["error"]
