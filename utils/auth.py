from functools import wraps
from flask_login import login_required, current_user
from flask import abort


def role_required(*roles):
    """Decorator ensuring the current user has one of ``roles``."""

    def wrapper(fn):
        @wraps(fn)
        @login_required
        def decorated(*a, **k):
            if current_user.role not in roles:
                abort(403)
            return fn(*a, **k)

        return decorated

    return wrapper
