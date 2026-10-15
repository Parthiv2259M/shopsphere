import os


class Development:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///shopsphere.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    TAX_RATE = 0.18


class Testing(Development):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = False


class Production(Development):
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True

    @classmethod
    def validate(cls):
        if not cls.SECRET_KEY or not cls.SQLALCHEMY_DATABASE_URI:
            raise RuntimeError("Production requires SECRET_KEY and DATABASE_URL")


CONFIGS = {
    "development": Development,
    "testing": Testing,
    "production": Production,
}
