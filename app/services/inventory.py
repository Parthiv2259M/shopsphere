from sqlalchemy import update

from ..extensions import db
from ..models import Product


class InventoryError(ValueError):
    pass


def change_stock(product_id, quantity_delta):
    """Apply a stock delta atomically; negative deltas cannot oversell."""
    condition = Product.id == product_id
    if quantity_delta < 0:
        condition = condition & (Product.stock >= -quantity_delta)
    result = db.session.execute(
        update(Product)
        .where(condition)
        .values(stock=Product.stock + quantity_delta)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise InventoryError("Product is unavailable or stock is insufficient.")
