from flask import Blueprint

routes_bp = Blueprint("routes", __name__)

from . import auth, attendance, admin  # noqa: E402,F401
