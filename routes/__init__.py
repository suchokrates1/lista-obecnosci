from flask import Blueprint

routes_bp = Blueprint("routes", __name__)

from . import auth, attendance, admin, panel  # noqa: E402,F401
