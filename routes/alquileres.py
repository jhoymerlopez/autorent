from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from config import alquileres_col, vehiculos_col, usuarios_col, empleados_col, pagos_col
from bson import ObjectId
from datetime import datetime
from correos import correo_alquiler_creado, correo_alquiler_finalizado
import threading

alquileres_bp = Blueprint("alquileres", __name__)

def enviar_async(func, *args):
    """Envía el correo en un hilo aparte para no bloquear la respuesta"""
    threading.Thread(target=func, args=args).start()

# ── Listar alquileres ──
@alquileres_bp.route("/alquileres")
def listar():
    if "usuario" not in session:
        return redirect(url_for("auth.login"))

    rol = session["usuario"]["rol"]
    if rol == "cliente":
        alquileres = list(alquileres_col.find({"usuario_id": ObjectId(session["usuario"]["id"])}))
    else:
        alquileres = list(alquileres_col.find())

    for a in alquileres:
        a["_id"] = str(a["_id"])
        usuario  = usuarios_col.find_one({"_id": a["usuario_id"]})
        vehiculo = vehiculos_col.find_one({"_id": a["vehiculo_id"]})
        a["usuario_nombre"]  = usuario["nombre"]  if usuario  else "N/A"
        a["vehiculo_nombre"] = f'{vehiculo["marca"]} {vehiculo["modelo"]}' if vehiculo else "N/A"

    return render_template("alquileres/listar.html", alquileres=alquileres)


# ── Crear alquiler ──
@alquileres_bp.route("/alquileres/crear", methods=["GET", "POST"])
def crear():
    if "usuario" not in session:
        return redirect(url_for("auth.login"))

    vehiculos = list(vehiculos_col.find({"estado": "disponible"}))
    usuarios  = list(usuarios_col.find({"activo": True}))

    if request.method == "POST":
        vehiculo_id  = ObjectId(request.form["vehiculo_id"])
        usuario_id   = ObjectId(request.form["usuario_id"])
        fecha_inicio = datetime.strptime(request.form["fecha_inicio"], "%Y-%m-%d")
        fecha_fin    = datetime.strptime(request.form["fecha_fin"],    "%Y-%m-%d")
        total_dias   = (fecha_fin - fecha_inicio).days
        vehiculo     = vehiculos_col.find_one({"_id": vehiculo_id})
        precio_total = total_dias * vehiculo["precio_dia"]
        metodo_pago  = request.form["metodo_pago"]

        # ── Validar documentos ──
        docs = vehiculo.get("documentos", {})
        hoy  = datetime.now()

        docs_requeridos = ["soat", "tecnomecanica", "tarjeta_propiedad", "seguro_todo_riesgo"]
        docs_faltantes  = [d.replace("_", " ").upper() for d in docs_requeridos if d not in docs]
        if docs_faltantes:
            flash(f'No se puede alquilar: faltan documentos → {", ".join(docs_faltantes)}', "danger")
            return render_template("alquileres/crear.html", vehiculos=vehiculos, usuarios=usuarios)

        docs_vencidos = []
        for nombre_doc, info in docs.items():
            if "vencimiento" in info and info["vencimiento"] < hoy:
                docs_vencidos.append(nombre_doc.replace("_", " ").upper())
        if docs_vencidos:
            flash(f'No se puede alquilar: documentos vencidos → {", ".join(docs_vencidos)}', "danger")
            return render_template("alquileres/crear.html", vehiculos=vehiculos, usuarios=usuarios)

        alquiler_id = alquileres_col.insert_one({
            "usuario_id"    : usuario_id,
            "vehiculo_id"   : vehiculo_id,
            "empleado_id"   : ObjectId(session["usuario"]["id"]),
            "fecha_inicio"  : fecha_inicio,
            "fecha_fin"     : fecha_fin,
            "total_dias"    : total_dias,
            "precio_total"  : precio_total,
            "estado"        : "activo",
            "observaciones" : request.form.get("observaciones", ""),
            "fecha_creacion": datetime.now()
        }).inserted_id

        vehiculos_col.update_one({"_id": vehiculo_id}, {"$set": {"estado": "alquilado"}})

        pagos_col.insert_one({
            "alquiler_id": alquiler_id,
            "monto"      : precio_total,
            "metodo"     : metodo_pago,
            "estado"     : "completado",
            "fecha"      : datetime.now(),
            "comprobante": f"COMP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        })

        # ── Enviar correo al cliente ──
        usuario = usuarios_col.find_one({"_id": usuario_id})
        if usuario and usuario.get("email"):
            nombre_vehiculo = f'{vehiculo["marca"]} {vehiculo["modelo"]} ({vehiculo["placa"]})'
            enviar_async(
                correo_alquiler_creado,
                usuario["email"],
                usuario["nombre"],
                nombre_vehiculo,
                fecha_inicio.strftime("%d/%m/%Y"),
                fecha_fin.strftime("%d/%m/%Y"),
                total_dias,
                precio_total,
                metodo_pago
            )

        flash("Alquiler creado exitosamente", "success")
        return redirect(url_for("alquileres.listar"))

    return render_template("alquileres/crear.html", vehiculos=vehiculos, usuarios=usuarios)


# ── Finalizar alquiler ──
@alquileres_bp.route("/alquileres/finalizar/<id>")
def finalizar(id):
    if "usuario" not in session or session["usuario"]["rol"] not in ["admin", "agente"]:
        return redirect(url_for("index"))

    alquiler = alquileres_col.find_one({"_id": ObjectId(id)})
    alquileres_col.update_one({"_id": ObjectId(id)}, {"$set": {"estado": "finalizado"}})
    vehiculo = vehiculos_col.find_one({"_id": alquiler["vehiculo_id"]})
    vehiculos_col.update_one({"_id": alquiler["vehiculo_id"]}, {"$set": {"estado": "disponible"}})

    # ── Enviar correo al cliente ──
    usuario = usuarios_col.find_one({"_id": alquiler["usuario_id"]})
    if usuario and usuario.get("email") and vehiculo:
        nombre_vehiculo = f'{vehiculo["marca"]} {vehiculo["modelo"]} ({vehiculo["placa"]})'
        enviar_async(
            correo_alquiler_finalizado,
            usuario["email"],
            usuario["nombre"],
            nombre_vehiculo,
            alquiler["fecha_inicio"].strftime("%d/%m/%Y"),
            alquiler["fecha_fin"].strftime("%d/%m/%Y"),
            alquiler.get("total_dias", 0),
            alquiler.get("precio_total", 0)
        )

    flash("Alquiler finalizado, vehículo disponible nuevamente", "success")
    return redirect(url_for("alquileres.listar"))


# ── Cancelar alquiler ──
@alquileres_bp.route("/alquileres/cancelar/<id>")
def cancelar(id):
    if "usuario" not in session:
        return redirect(url_for("auth.login"))

    alquiler = alquileres_col.find_one({"_id": ObjectId(id)})
    alquileres_col.update_one({"_id": ObjectId(id)}, {"$set": {"estado": "cancelado"}})
    vehiculos_col.update_one({"_id": alquiler["vehiculo_id"]}, {"$set": {"estado": "disponible"}})

    flash("Alquiler cancelado", "warning")
    return redirect(url_for("alquileres.listar"))
