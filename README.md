# ShopSphere

ShopSphere is a self-contained Flask e-commerce application using SQLite and SQLAlchemy. It includes a responsive storefront, customer accounts, cart and checkout flows, coupons, product reviews, admin tools, and a bearer-token JSON API. It requires no external services.

## Requirements and setup

Python 3.10 or newer is recommended. From this directory:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python seed.py
python run.py
```

Open `http://127.0.0.1:5000`. The seed script is repeatable and creates five categories, 30 products, and an admin account (`admin@shopsphere.local` / `AdminPass1!`). Change the seeded password before deploying.

The development SQLite database is `shopsphere.db`. Set `DATABASE_URL` and `SECRET_KEY` for deployment; production refuses to start without both. `create_app("testing")` uses an in-memory SQLite database.

## Features

- Password policy, case-insensitive email lookup, secure password hashing, and customer/admin roles.
- Search, category and price filters, sorting, pagination, product details, and verified-buyer reviews.
- Cart quantity validation, percentage/fixed coupons, GST (18%), shipping (free at Rs. 999 or more; otherwise Rs. 50), checkout, and atomic stock updates.
- Order states `PLACED -> PAID -> SHIPPED -> DELIVERED`; cancellation is allowed only before shipment and restores inventory.
- Admin-only product archival/creation, order workflow management, and sales reporting.
- Version 1 JSON API: `GET /api/v1/products`, `/api/v1/cart`, and `/api/v1/orders`; add to cart with `POST /api/v1/cart`, checkout with `POST /api/v1/orders`. Send `Authorization: Bearer <user api_token>`.
- CSRF protection for browser form submissions. API routes use bearer token authentication and are exempt from browser CSRF checks.

## Tests and quality checks

```powershell
pytest
pytest --cov=app --cov-report=term-missing --cov-fail-under=85
python -m flake8 app seed.py run.py
python -m bandit -r app
```

The test suite uses pytest markers (`unit`, `integration`, `api`, `security`) and an in-memory SQLite database. Pytest writes JUnit XML to `reports/junit.xml`.

## Jenkins on Windows

Create a Jenkins Pipeline job pointing at this repository and run it on a Windows agent with Python (`py`) installed. `Jenkinsfile` runs Checkout, Setup, Lint, Security Scan, Unit Tests, Integration Tests, API Tests, Security Tests, and Coverage using Windows `bat` steps. It polls SCM each minute, publishes JUnit XML, and archives the HTML coverage report. Lint warnings and Bandit findings are informational and do not fail their stages; test and coverage failures do.

## API quick example

```powershell
curl.exe -H "Authorization: Bearer YOUR_API_TOKEN" http://127.0.0.1:5000/api/v1/products
```
