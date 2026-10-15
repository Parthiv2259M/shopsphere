from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import ValidationError as CSRFValidationError, validate_csrf

from ..extensions import db
from ..models import Cart, User
from ..services.validators import ValidationError, validate_email

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("products.list_products"))
    if request.method == "POST":
        if current_app.config.get("WTF_CSRF_ENABLED", True):
            try:
                validate_csrf(request.form.get("csrf_token"))
            except CSRFValidationError:
                return "CSRF token is invalid.", 400
        try:
            email = validate_email(request.form.get("email", ""))
            if User.query.filter_by(email=email).first():
                raise ValidationError("An account with that email already exists.")
            user = User(name=request.form.get("name", "").strip(), email=email)
            if not user.name:
                raise ValidationError("Name is required.")
            user.set_password(request.form.get("password", ""))
            db.session.add(user)
            db.session.flush()
            db.session.add(Cart(user_id=user.id))
            db.session.commit()
            login_user(user)
            return redirect(url_for("products.list_products"))
        except ValidationError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if current_app.config.get("WTF_CSRF_ENABLED", True):
            try:
                validate_csrf(request.form.get("csrf_token"))
            except CSRFValidationError:
                return "CSRF token is invalid.", 400
        try:
            email = validate_email(request.form.get("email", ""))
        except ValidationError:
            email = ""
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user)
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect("/")
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html")


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("products.list_products"))


@auth_bp.get("/account")
@login_required
def account():
    return render_template("auth/account.html")
