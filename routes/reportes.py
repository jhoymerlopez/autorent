from flask import Blueprint, render_template, request, session, redirect, url_for
from config import alquileres_col, vehiculos_col, usuarios_col, multas_col
from datetime import datetime, timedelta

reportes_bp = Blueprint("reportes", __name__)

@reportes_bp.route("/reportes")
def index():
    if "usuario" not in session:
        return redirect(url_for("auth.login"))
    if session["usuario"]["rol"] not in ["admin", "agente"]:
        return redirect(url_for("index"))

    # ── Período seleccionado ──
    periodo = request.args.get("periodo", "mes")
    hoy     = datetime.now()

    if periodo == "dia":
        fecha_inicio = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        fecha_inicio = hoy - timedelta(days=hoy.weekday())
        fecha_inicio = fecha_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "año":
        fecha_inicio = hoy.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # mes por defecto
        fecha_inicio = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── Alquileres del período ──
    alquileres = list(alquileres_col.find({"fecha_creacion": {"$gte": fecha_inicio}}))

    total_alquileres  = len(alquileres)
    total_ingresos    = sum(a.get("precio_total", 0) for a in alquileres)
    total_activos     = sum(1 for a in alquileres if a["estado"] == "activo")
    total_finalizados = sum(1 for a in alquileres if a["estado"] == "finalizado")
    total_cancelados  = sum(1 for a in alquileres if a["estado"] == "cancelado")

    # ── Entregas a tiempo vs tarde ──
    a_tiempo = 0
    tarde    = 0
    for a in alquileres:
        if a["estado"] == "finalizado":
            # Si no hay fecha de finalización real usamos fecha_fin como referencia
            if a.get("fecha_fin") and a.get("fecha_creacion"):
                if hoy <= a["fecha_fin"]:
                    a_tiempo += 1
                else:
                    tarde += 1

    # Calcular con todos los finalizados históricos para mejor dato
    todos_finalizados = list(alquileres_col.find({"estado": "finalizado"}))
    a_tiempo_total = 0
    tarde_total    = 0
    for a in todos_finalizados:
        if a.get("fecha_fin"):
            # Comparamos fecha_creacion del último estado con fecha_fin
            if a["fecha_fin"] >= datetime.now() or a["estado"] == "finalizado":
                a_tiempo_total += 1
            else:
                tarde_total += 1

    # ── Vehículo más alquilado ──
    from collections import Counter
    vehiculo_ids   = [str(a["vehiculo_id"]) for a in list(alquileres_col.find({}))]
    vehiculo_count = Counter(vehiculo_ids)
    top_vehiculos  = []
    for vid, count in vehiculo_count.most_common(5):
        from bson import ObjectId
        try:
            v = vehiculos_col.find_one({"_id": ObjectId(vid)})
            if v:
                top_vehiculos.append({
                    "nombre": f'{v["marca"]} {v["modelo"]}',
                    "placa" : v["placa"],
                    "total" : count
                })
        except:
            pass

    # ── Clientes con más alquileres ──
    usuario_ids   = [str(a["usuario_id"]) for a in list(alquileres_col.find({}))]
    usuario_count = Counter(usuario_ids)
    top_clientes  = []
    for uid, count in usuario_count.most_common(5):
        try:
            u = usuarios_col.find_one({"_id": ObjectId(uid)})
            if u:
                top_clientes.append({
                    "nombre": u["nombre"],
                    "email" : u["email"],
                    "total" : count
                })
        except:
            pass

    # ── Multas del período ──
    multas_periodo = list(multas_col.find({"fecha": {"$gte": fecha_inicio}}))
    total_multas        = len(multas_periodo)
    total_multas_monto  = sum(m.get("monto", 0) for m in multas_periodo)
    multas_pendientes   = sum(1 for m in multas_periodo if m["estado"] == "pendiente")
    multas_pagadas      = sum(1 for m in multas_periodo if m["estado"] == "pagada")

    # ── Alquileres por día (últimos 7 días para gráfica) ──
    labels_grafica  = []
    datos_grafica   = []
    ingresos_grafica = []
    for i in range(6, -1, -1):
        dia     = hoy - timedelta(days=i)
        inicio  = dia.replace(hour=0, minute=0, second=0, microsecond=0)
        fin     = dia.replace(hour=23, minute=59, second=59, microsecond=999999)
        count   = alquileres_col.count_documents({"fecha_creacion": {"$gte": inicio, "$lte": fin}})
        ingreso = sum(
            a.get("precio_total", 0)
            for a in alquileres_col.find({"fecha_creacion": {"$gte": inicio, "$lte": fin}})
        )
        labels_grafica.append(dia.strftime("%d/%m"))
        datos_grafica.append(count)
        ingresos_grafica.append(ingreso)

    # ── Tabla de alquileres del período ──
    alquileres_tabla = []
    for a in sorted(alquileres, key=lambda x: x.get("fecha_creacion", datetime.min), reverse=True)[:20]:
        u = usuarios_col.find_one({"_id": a["usuario_id"]})
        v = vehiculos_col.find_one({"_id": a["vehiculo_id"]})
        alquileres_tabla.append({
            "cliente"      : u["nombre"] if u else "N/A",
            "vehiculo"     : f'{v["marca"]} {v["modelo"]}' if v else "N/A",
            "fecha_inicio" : a["fecha_inicio"].strftime("%d/%m/%Y"),
            "fecha_fin"    : a["fecha_fin"].strftime("%d/%m/%Y"),
            "dias"         : a.get("total_dias", 0),
            "total"        : a.get("precio_total", 0),
            "estado"       : a["estado"],
            "a_tiempo"     : a["fecha_fin"] >= hoy if a["estado"] == "activo" else a["estado"] == "finalizado"
        })

    return render_template("reportes/index.html",
        periodo          = periodo,
        fecha_inicio     = fecha_inicio.strftime("%d/%m/%Y"),
        total_alquileres = total_alquileres,
        total_ingresos   = total_ingresos,
        total_activos    = total_activos,
        total_finalizados= total_finalizados,
        total_cancelados = total_cancelados,
        a_tiempo         = a_tiempo_total,
        tarde            = tarde_total,
        top_vehiculos    = top_vehiculos,
        top_clientes     = top_clientes,
        total_multas     = total_multas,
        total_multas_monto = total_multas_monto,
        multas_pendientes= multas_pendientes,
        multas_pagadas   = multas_pagadas,
        labels_grafica   = labels_grafica,
        datos_grafica    = datos_grafica,
        ingresos_grafica = ingresos_grafica,
        alquileres_tabla = alquileres_tabla,
    )
