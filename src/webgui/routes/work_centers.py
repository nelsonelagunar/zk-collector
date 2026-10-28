"""
Work Centers Routes - CRUD de centros de trabajo (CT-1, MYK-427)
"""

from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from ..middleware.auth import api_require, require

work_centers_bp = Blueprint("work_centers", __name__, url_prefix="/work-centers")


@work_centers_bp.route("/", strict_slashes=False)
@require("devices:read")
def list_work_centers():
    """Lista de centros de trabajo"""
    db = current_app.db
    work_centers = db.get_work_centers()
    return render_template("work_centers/list.html", work_centers=work_centers)


@work_centers_bp.route("/new", methods=["GET", "POST"])
@require("devices:write")
def create_work_center():
    """Crear nuevo centro de trabajo"""
    if request.method == "POST":
        data = {
            "nombre": request.form.get("nombre", ""),
            "rfc_pattern": request.form.get("rfc_pattern", ""),
            "imss_registro_patronal": request.form.get("imss_registro_patronal", ""),
            "direccion": request.form.get("direccion", ""),
        }

        # Validaciones
        errors = []
        if not data["nombre"]:
            errors.append("Nombre es requerido")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("work_centers/create.html")

        # Guardar en DB
        db = current_app.db
        db.create_work_center(data)

        flash(f'Centro de trabajo "{data["nombre"]}" creado exitosamente', "success")
        return redirect(url_for("work_centers.list_work_centers"))

    return render_template("work_centers/create.html")


@work_centers_bp.route("/<int:work_center_id>/edit", methods=["GET", "POST"])
@require("devices:write")
def edit_work_center(work_center_id):
    """Editar centro de trabajo"""
    db = current_app.db

    if request.method == "POST":
        data = {
            "nombre": request.form.get("nombre", ""),
            "rfc_pattern": request.form.get("rfc_pattern", ""),
            "imss_registro_patronal": request.form.get("imss_registro_patronal", ""),
            "direccion": request.form.get("direccion", ""),
            "updated_at": datetime.now().isoformat(),
        }

        # Validaciones
        if not data["nombre"]:
            flash("Nombre es requerido", "error")
            return render_template("work_centers/edit.html", work_center_id=work_center_id)

        # Actualizar en DB
        db.update_work_center(work_center_id, data)

        flash("Centro de trabajo actualizado", "success")
        return redirect(url_for("work_centers.list_work_centers"))

    # GET - mostrar form
    work_center = db.get_work_center_by_id(work_center_id)

    if not work_center:
        flash("Centro de trabajo no encontrado", "error")
        return redirect(url_for("work_centers.list_work_centers"))

    return render_template("work_centers/edit.html", work_center=work_center)


@work_centers_bp.route("/<int:work_center_id>/delete", methods=["POST"])
@require("devices:write")
def delete_work_center(work_center_id):
    """Eliminar centro de trabajo"""
    db = current_app.db
    try:
        db.delete_work_center(work_center_id)
        flash("Centro de trabajo eliminado", "success")
    except ValueError as e:
        flash(str(e), "error")

    return redirect(url_for("work_centers.list_work_centers"))


@work_centers_bp.route("/api/work-centers")
@api_require("devices:read")
def api_work_centers():
    """API para obtener lista de centros de trabajo (para select en dispositivos)"""
    db = current_app.db
    work_centers = db.get_work_centers()
    return jsonify({"work_centers": work_centers})
