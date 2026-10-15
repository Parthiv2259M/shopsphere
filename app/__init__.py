from flask import Flask, render_template

from .config import CONFIGS
from .extensions import csrf, db, login_manager


def create_app(config_name="development", test_config=None):
    if config_name not in CONFIGS:
        raise ValueError(f"Unknown configuration: {config_name}")
    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name])
    if test_config:
        app.config.update(test_config)
    if config_name == "production" and not test_config:
        CONFIGS["production"].validate()

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from .admin import admin_bp
    from .api import api_bp
    from .auth import auth_bp
    from .cart import cart_bp
    from .orders import orders_bp
    from .products import products_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    csrf.exempt(api_bp)

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.context_processor
    def inject_cart_count():
        from flask_login import current_user
        from .models import Cart

        if not current_user.is_authenticated:
            return {"cart_count": 0}
        cart = Cart.query.filter_by(user_id=current_user.id).first()
        return {"cart_count": sum(item.quantity for item in cart.items) if cart else 0}

    return app
