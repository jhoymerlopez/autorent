from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from config import multas_col, alquileres_col, vehiculos_col, usuarios_col
from bson import ObjectId
from datetime import datetime
from correos import correo_multa_registrada
import threading

def enviar_async(func, *args):
    threading.Thread(target=func, args=args).start()

multas_bp = Blueprint("multas", __name__)

# ── Listar multas ──
@multas_bp.route("/multas")
def listar():
    if "usuario" not in session:
        return redirect(url_for("auth.login"))

    rol = session["usuario"]["rol"]
    if rol == "cliente":
        multas = list(multas_col.find({"usuario_id": ObjectId(session["usuario"]["id"])}))
    else:
        multas = list(multas_col.find())

    for m in multas:
        m["_id"] = str(m["_id"])
        usuario  = usuarios_col.find_one({"_id": m["usuario_id"]})
        vehiculo = vehiculos_col.find_one({"_id": m["vehiculo_id"]})
        m["usuario_nombre"]  = usuario["nombre"]  if usuario  else "N/A"
        m["vehiculo_nombre"] = f'{vehiculo["marca"]} {vehiculo["modelo"]}' if vehiculo else "N/A"

    return render_template("multas/listar.html", multas=multas)


# ── Registrar multa ──
@multas_bp.route("/multas/registrar", methods=["GET", "POST"])
def registrar():
    if "usuario" not in session or session["usuario"]["rol"] not in ["admin", "agente"]:
        return redirect(url_for("index"))

    # Enriquecer alquileres activos con nombre de cliente y vehículo
    alquileres_raw = list(alquileres_col.find({"estado": "activo"}))
    alquileres = []
    for a in alquileres_raw:
        usuario  = usuarios_col.find_one({"_id": a["usuario_id"]})
        vehiculo = vehiculos_col.find_one({"_id": a["vehiculo_id"]})
        alquileres.append({
            "_id"          : str(a["_id"]),
            "cliente"      : usuario["nombre"] if usuario else "N/A",
            "vehiculo"     : f'{vehiculo["marca"]} {vehiculo["modelo"]} ({vehiculo["placa"]})' if vehiculo else "N/A",
            "fecha_inicio" : a["fecha_inicio"].strftime("%d/%m/%Y"),
            "fecha_fin"    : a["fecha_fin"].strftime("%d/%m/%Y"),
        })

    if request.method == "POST":
        alquiler = alquileres_col.find_one({"_id": ObjectId(request.form["alquiler_id"])})
        multas_col.insert_one({
            "alquiler_id" : ObjectId(request.form["alquiler_id"]),
            "vehiculo_id" : alquiler["vehiculo_id"],
            "usuario_id"  : alquiler["usuario_id"],
            "empleado_id" : ObjectId(session["usuario"]["id"]),
            "descripcion" : request.form["descripcion"],
            "monto"       : int(request.form["monto"]),
            "estado"      : "pendiente",
            "fecha"       : datetime.now(),
            "evidencia"   : []
        })
        # ── Enviar correo al cliente ──
        alquiler_obj = alquileres_col.find_one({"_id": ObjectId(request.form["alquiler_id"])})
        usuario  = usuarios_col.find_one({"_id": alquiler_obj["usuario_id"]})
        vehiculo = vehiculos_col.find_one({"_id": alquiler_obj["vehiculo_id"]})
        if usuario and usuario.get("email") and vehiculo:
            nombre_vehiculo = f'{vehiculo["marca"]} {vehiculo["modelo"]} ({vehiculo["placa"]})'
            enviar_async(
                correo_multa_registrada,
                usuario["email"],
                usuario["nombre"],
                nombre_vehiculo,
                request.form["descripcion"],
                int(request.form["monto"]),
                "daño"
            )

        flash("Multa registrada correctamente", "success")
        return redirect(url_for("multas.listar"))

    return render_template("multas/registrar.html", alquileres=alquileres)


# ── Marcar multa como pagada ──
@multas_bp.route("/multas/pagar/<id>")
def pagar(id):
    if "usuario" not in session or session["usuario"]["rol"] not in ["admin", "agente"]:
        return redirect(url_for("index"))
    multas_col.update_one({"_id": ObjectId(id)}, {"$set": {"estado": "pagada"}})
    flash("Multa marcada como pagada", "success")
    return redirect(url_for("multas.listar"))
