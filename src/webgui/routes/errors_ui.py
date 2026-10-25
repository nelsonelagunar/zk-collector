"""Rutas de error UI (MYK-416).

`GET /403` — pagina amigable para los redirects del decorador `require()`
(MYK-413/414): la flash explica el motivo y esta pagina explica el estado.
El decorador debe redirigir aqui con `url_for("errors_ui.forbidden")`.
"""

from flask import Blueprint, render_template

errors_ui_bp = Blueprint("errors_ui", __name__)


@errors_ui_bp.route("/403", strict_slashes=False)
def forbidden():
    """Pagina 403 amigable (template + flash)."""
    return render_template("403.html")
