"""
Profile UI Route - menu de usuario (MYK-377).

Muestra la cuenta de la sesion actual dentro del layout.
"""

from typing import cast

from flask import Blueprint, abort, current_app, render_template, session

from ..database import Database
from ..middleware.auth import login_required

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/", strict_slashes=False)
@login_required
def profile_ui():
    """Perfil del usuario en sesion."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]
    user = db.fetch_one(
        """
        SELECT id, username, email, full_name, role, last_login, created_at
        FROM users
        WHERE id = ?
        """,
        (session.get("user_id"),),
    )
    if not user:
        abort(404)
    return render_template("profile/index.html", user=user)
