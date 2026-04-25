from flask import Flask, render_template, session, redirect, url_for
from routes.auth       import auth_bp
from routes.vehiculos  import vehiculos_bp
from routes.alquileres import alquileres_bp
from routes.empleados  import empleados_bp
from routes.multas     import multas_bp
from routes.reportes   import reportes_bp
from routes.clientes   import clientes_bp
from config import vehiculos_col, alquileres_col, multas_col, usuarios_col
from correos import correo_multa_registrada
import threading

def enviar_async(func, *args):
    threading.Thread(target=func, args=args).start()
from datetime import datetime
import builtins

app = Flask(__name__)
import os
app.secret_key = os.environ.get("SECRET_KEY", "alquiler_vehiculos_secret_2024")

# Hacer enumerate disponible en las plantillas Jinja2
app.jinja_env.globals.update(enumerate=builtins.enumerate)

# -- Registrar Blueprints --
app.register_blueprint(auth_bp)
app.register_blueprint(vehiculos_bp)
app.register_blueprint(alquileres_bp)
app.register_blueprint(empleados_bp)
app.register_blueprint(multas_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(clientes_bp)


# -- Finalizar alquileres vencidos y cobrar dias extra como multa --
def finalizar_alquileres_vencidos():
    hoy = datetime.now()
    vencidos = list(alquileres_col.find({
        "estado"   : "activo",
        "fecha_fin": {"$lt": hoy}
    }))

    for alquiler in vencidos:

        # Calcular dias de retraso (minimo 1)
        dias_retraso = (hoy - alquiler["fecha_fin"]).days
        if dias_retraso < 1:
            dias_retraso = 1

        # Obtener precio por dia del vehiculo
        vehiculo   = vehiculos_col.find_one({"_id": alquiler["vehiculo_id"]})
        precio_dia = vehiculo.get("precio_dia", 0) if vehiculo else 0
        monto_multa = dias_retraso * precio_dia

        # Verificar que no exista ya una multa de retraso para este alquiler
        ya_multado = multas_col.find_one({
            "alquiler_id": alquiler["_id"],
            "tipo"       : "retraso"
        })

        if not ya_multado and monto_multa > 0:
            fecha_fin_str = alquiler["fecha_fin"].strftime("%d/%m/%Y")
            multas_col.insert_one({
                "alquiler_id" : alquiler["_id"],
                "vehiculo_id" : alquiler["vehiculo_id"],
                "usuario_id"  : alquiler["usuario_id"],
                "empleado_id" : None,
                "tipo"        : "retraso",
                "descripcion" : (
                    "Retraso en entrega del vehiculo: "
                    + str(dias_retraso)
                    + " dia(s) despues de la fecha pactada ("
                    + fecha_fin_str
                    + "). Se cobra el precio del alquiler por cada dia de retraso."
                ),
                "monto"      : monto_multa,
                "estado"     : "pendiente",
                "fecha"      : hoy,
                "evidencia"  : []
            })
            print("Multa por retraso registrada: " + str(dias_retraso) + " dia(s) - $" + str(monto_multa))
            # Enviar correo al cliente
            usuario  = usuarios_col.find_one({"_id": alquiler["usuario_id"]})
            vehiculo_obj = vehiculos_col.find_one({"_id": alquiler["vehiculo_id"]})
            if usuario and usuario.get("email") and vehiculo_obj:
                nombre_v = f'{vehiculo_obj["marca"]} {vehiculo_obj["modelo"]} ({vehiculo_obj["placa"]})'
                desc = f"Retraso de {dias_retraso} día(s) en la entrega del vehículo."
                enviar_async(correo_multa_registrada, usuario["email"], usuario["nombre"], nombre_v, desc, monto_multa, "retraso")

        # Finalizar alquiler y liberar vehiculo
        alquileres_col.update_one(
            {"_id": alquiler["_id"]},
            {"$set": {"estado": "finalizado"}}
        )
        vehiculos_col.update_one(
            {"_id": alquiler["vehiculo_id"]},
            {"$set": {"estado": "disponible"}}
        )

    if vencidos:
        print("Alquileres finalizados automaticamente: " + str(len(vencidos)))


# -- Dashboard --
@app.route("/")
def index():
    if "usuario" not in session:
        return redirect(url_for("auth.login"))

    finalizar_alquileres_vencidos()

    total_vehiculos       = vehiculos_col.count_documents({})
    vehiculos_disponibles = vehiculos_col.count_documents({"estado": "disponible"})
    alquileres_activos    = alquileres_col.count_documents({"estado": "activo"})
    multas_pendientes     = multas_col.count_documents({"estado": "pendiente"})

    vehiculos_recientes = list(vehiculos_col.find().limit(5))
    for v in vehiculos_recientes:
        v["_id"] = str(v["_id"])

    alquileres_recientes = list(alquileres_col.find().sort("fecha_creacion", -1).limit(5))
    for a in alquileres_recientes:
        a["_id"]  = str(a["_id"])
        usuario  = usuarios_col.find_one({"_id": a["usuario_id"]})
        vehiculo = vehiculos_col.find_one({"_id": a["vehiculo_id"]})
        a["usuario_nombre"]  = usuario["nombre"]  if usuario  else "N/A"
        a["vehiculo_nombre"] = f'{vehiculo["marca"]} {vehiculo["modelo"]}' if vehiculo else "N/A"

    return render_template("index.html",
        usuario               = session["usuario"],
        total_vehiculos       = total_vehiculos,
        vehiculos_disponibles = vehiculos_disponibles,
        alquileres_activos    = alquileres_activos,
        multas_pendientes     = multas_pendientes,
        vehiculos_recientes   = vehiculos_recientes,
        alquileres_recientes  = alquileres_recientes
    )

if __name__ == "__main__":
    app.run(debug=True)
