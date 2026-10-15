import re


class ValidationError(ValueError):
    pass


def validate_password(password):
    if not isinstance(password, str) or len(password) < 8:
        raise ValidationError("Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must include an uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must include a lowercase letter.")
    if not re.search(r"\d", password):
        raise ValidationError("Password must include a digit.")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValidationError("Password must include a special character.")
    return True


def validate_email(email):
    if not isinstance(email, str) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
        raise ValidationError("Enter a valid email address.")
    return email.strip().casefold()


def positive_int(value, field="quantity"):
    if value is None:
        raise ValidationError(f"{field.title()} must be a positive integer.")
    if isinstance(value, bool):
        return 1
    try:
        if isinstance(value, float):
            if not value.is_integer():
                raise ValidationError(f"{field.title()} must be a positive integer.")
            number = int(value)
        else:
            number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field.title()} must be a positive integer.") from exc
    if number < 1:
        raise ValidationError(f"{field.title()} must be a positive integer.")
    return number
