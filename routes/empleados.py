from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from config import empleados_col
from bson import ObjectId
import bcrypt

empleados_bp = Blueprint("empleados", __name__)

# ── Listar empleados (solo admin) ──
@empleados_bp.route("/empleados")
def listar():
    if "usuario" not in session or session["usuario"]["rol"] != "admin":
        return redirect(url_for("index"))
    empleados = list(empleados_col.find())
    for e in empleados:
        e["_id"] = str(e["_id"])
    return render_template("empleados/listar.html", empleados=empleados)


# ── Agregar empleado ──
@empleados_bp.route("/empleados/agregar", methods=["GET", "POST"])
def agregar():
    if "usuario" not in session or session["usuario"]["rol"] != "admin":
        return redirect(url_for("index"))

    if request.method == "POST":
        hashed = bcrypt.hashpw(request.form["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        empleados_col.insert_one({
            "nombre"       : request.form["nombre"],
            "email"        : request.form["email"],
            "password"     : hashed,
            "rol"          : request.form["rol"],
            "telefono"     : request.form["telefono"],
            "activo"       : True
        })
        flash("Empleado agregado correctamente", "success")
        return redirect(url_for("empleados.listar"))

    return render_template("empleados/agregar.html")


# ── Eliminar empleado ──
@empleados_bp.route("/empleados/eliminar/<id>")
def eliminar(id):
    if "usuario" not in session or session["usuario"]["rol"] != "admin":
        return redirect(url_for("index"))
    empleados_col.delete_one({"_id": ObjectId(id)})
    flash("Empleado eliminado", "warning")
    return redirect(url_for("empleados.listar"))
