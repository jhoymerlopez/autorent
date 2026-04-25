from flask import Blueprint, render_template, redirect, url_for, flash, session
from config import usuarios_col, alquileres_col
from bson import ObjectId

clientes_bp = Blueprint("clientes", __name__)

# ── Listar clientes ──
@clientes_bp.route("/clientes")
def listar():
    if "usuario" not in session:
        return redirect(url_for("auth.login"))
    if session["usuario"]["rol"] not in ["admin", "agente"]:
        return redirect(url_for("index"))

    clientes = list(usuarios_col.find({"activo": True}))
    for c in clientes:
        c["_id"] = str(c["_id"])
        # Contar cuántos alquileres tiene cada cliente
        c["total_alquileres"] = alquileres_col.count_documents({"usuario_id": ObjectId(c["_id"])})

    return render_template("clientes/listar.html", clientes=clientes)


# ── Eliminar cliente ──
@clientes_bp.route("/clientes/eliminar/<id>")
def eliminar(id):
    if "usuario" not in session or session["usuario"]["rol"] not in ["admin", "agente"]:
        return redirect(url_for("index"))

    usuarios_col.delete_one({"_id": ObjectId(id)})
    flash("Cliente eliminado correctamente.", "success")
    return redirect(url_for("clientes.listar"))