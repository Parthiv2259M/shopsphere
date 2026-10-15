from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models import Category, Product, User

app = create_app()


def seed():
    with app.app_context():
        db.create_all()
        categories = [
            ("Home", "home"), ("Tech", "tech"), ("Lifestyle", "lifestyle"),
            ("Kitchen", "kitchen"), ("Outdoors", "outdoors"),
        ]
        records = {}
        for name, slug in categories:
            category = Category.query.filter_by(slug=slug).first()
            if not category:
                category = Category(name=name, slug=slug)
                db.session.add(category)
            records[slug] = category
        admin = User.query.filter_by(email="admin@shopsphere.local").first()
        if not admin:
            admin = User(name="ShopSphere Admin", email="admin@shopsphere.local", role="admin")
            admin.set_password("AdminPass1!")
            db.session.add(admin)
        db.session.flush()
        for number in range(1, 31):
            slug = f"everyday-essential-{number:02d}"
            if Product.query.filter_by(slug=slug).first():
                continue
            category = list(records.values())[(number - 1) % len(records)]
            db.session.add(Product(
                name=f"Everyday Essential {number:02d}",
                slug=slug,
                description=f"A thoughtfully selected ShopSphere essential, item {number}.",
                price=Decimal(f"{(number * 129 + 199) / 1:.2f}"),
                stock=5 + number,
                category=category,
            ))
        db.session.commit()


if __name__ == "__main__":
    seed()
