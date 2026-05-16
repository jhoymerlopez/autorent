from flask import Blueprint, render_template, request, session, redirect, url_for, send_file
from config import alquileres_col, vehiculos_col, usuarios_col, multas_col
from datetime import datetime, timedelta
from collections import Counter
from bson import ObjectId
import io

reportes_bp = Blueprint("reportes", __name__)

@reportes_bp.route("/reportes")
def index():
    if "usuario" not in session:
        return redirect(url_for("auth.login"))
    if session["usuario"]["rol"] not in ["admin", "agente"]:
        return redirect(url_for("index"))

    hoy = datetime.now()

    # ── Período para gráficas ──
    periodo = request.args.get("periodo", "mes")
    if periodo == "dia":
        fecha_inicio = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        fecha_inicio = hoy - timedelta(days=hoy.weekday())
        fecha_inicio = fecha_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "año":
        fecha_inicio = hoy.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        fecha_inicio = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    alquileres = list(alquileres_col.find({"fecha_creacion": {"$gte": fecha_inicio}}))

    total_alquileres  = len(alquileres)
    total_ingresos    = sum(a.get("precio_total", 0) for a in alquileres)
    total_activos     = sum(1 for a in alquileres if a["estado"] == "activo")
    total_finalizados = sum(1 for a in alquileres if a["estado"] == "finalizado")
    total_cancelados  = sum(1 for a in alquileres if a["estado"] == "cancelado")

    todos_finalizados = list(alquileres_col.find({"estado": "finalizado"}))
    a_tiempo_total = len(todos_finalizados)
    tarde_total    = 0

    vehiculo_ids   = [str(a["vehiculo_id"]) for a in list(alquileres_col.find({}))]
    vehiculo_count = Counter(vehiculo_ids)
    top_vehiculos  = []
    for vid, count in vehiculo_count.most_common(5):
        try:
            v = vehiculos_col.find_one({"_id": ObjectId(vid)})
            if v:
                top_vehiculos.append({"nombre": f'{v["marca"]} {v["modelo"]}', "placa": v["placa"], "total": count})
        except: pass

    usuario_ids   = [str(a["usuario_id"]) for a in list(alquileres_col.find({}))]
    usuario_count = Counter(usuario_ids)
    top_clientes  = []
    for uid, count in usuario_count.most_common(5):
        try:
            u = usuarios_col.find_one({"_id": ObjectId(uid)})
            if u:
                top_clientes.append({"nombre": u["nombre"], "email": u["email"], "total": count})
        except: pass

    multas_periodo     = list(multas_col.find({"fecha": {"$gte": fecha_inicio}}))
    total_multas       = len(multas_periodo)
    total_multas_monto = sum(m.get("monto", 0) for m in multas_periodo)
    multas_pendientes  = sum(1 for m in multas_periodo if m["estado"] == "pendiente")
    multas_pagadas     = sum(1 for m in multas_periodo if m["estado"] == "pagada")

    labels_grafica   = []
    datos_grafica    = []
    ingresos_grafica = []
    for i in range(6, -1, -1):
        dia    = hoy - timedelta(days=i)
        inicio = dia.replace(hour=0, minute=0, second=0, microsecond=0)
        fin    = dia.replace(hour=23, minute=59, second=59, microsecond=999999)
        count  = alquileres_col.count_documents({"fecha_creacion": {"$gte": inicio, "$lte": fin}})
        ingreso = sum(a.get("precio_total", 0) for a in alquileres_col.find({"fecha_creacion": {"$gte": inicio, "$lte": fin}}))
        labels_grafica.append(dia.strftime("%d/%m"))
        datos_grafica.append(count)
        ingresos_grafica.append(ingreso)

    # ── Filtros de consulta ──
    filtro_cliente  = request.args.get("filtro_cliente", "").strip()
    filtro_vehiculo = request.args.get("filtro_vehiculo", "").strip()
    filtro_estado   = request.args.get("filtro_estado", "")
    filtro_desde    = request.args.get("filtro_desde", "")
    filtro_hasta    = request.args.get("filtro_hasta", "")

    query = {}
    if filtro_estado:
        query["estado"] = filtro_estado
    if filtro_desde:
        try:
            query.setdefault("fecha_inicio", {})["$gte"] = datetime.strptime(filtro_desde, "%Y-%m-%d")
        except: pass
    if filtro_hasta:
        try:
            query.setdefault("fecha_inicio", {})["$lte"] = datetime.strptime(filtro_hasta, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except: pass

    todos_alquileres = list(alquileres_col.find(query).sort("fecha_creacion", -1))

    alquileres_tabla = []
    for a in todos_alquileres:
        u = usuarios_col.find_one({"_id": a["usuario_id"]})
        v = vehiculos_col.find_one({"_id": a["vehiculo_id"]})
        nombre_cliente  = u["nombre"] if u else "N/A"
        nombre_vehiculo = f'{v["marca"]} {v["modelo"]} ({v["placa"]})' if v else "N/A"

        # Filtrar por cliente y vehículo (texto)
        if filtro_cliente and filtro_cliente.lower() not in nombre_cliente.lower():
            continue
        if filtro_vehiculo and filtro_vehiculo.lower() not in nombre_vehiculo.lower():
            continue

        alquileres_tabla.append({
            "id"          : str(a["_id"]),
            "cliente"     : nombre_cliente,
            "vehiculo"    : nombre_vehiculo,
            "fecha_inicio": a["fecha_inicio"].strftime("%d/%m/%Y"),
            "fecha_fin"   : a["fecha_fin"].strftime("%d/%m/%Y"),
            "dias"        : a.get("total_dias", 0),
            "total"       : a.get("precio_total", 0),
            "estado"      : a["estado"],
            "a_tiempo"    : a["fecha_fin"] >= hoy if a["estado"] == "activo" else a["estado"] == "finalizado"
        })

    # Lista de vehículos y clientes para los filtros
    lista_vehiculos = list(vehiculos_col.find({}, {"marca": 1, "modelo": 1, "placa": 1}))
    lista_clientes  = list(usuarios_col.find({}, {"nombre": 1}))

    return render_template("reportes/index.html",
        periodo           = periodo,
        fecha_inicio      = fecha_inicio.strftime("%d/%m/%Y"),
        total_alquileres  = total_alquileres,
        total_ingresos    = total_ingresos,
        total_activos     = total_activos,
        total_finalizados = total_finalizados,
        total_cancelados  = total_cancelados,
        a_tiempo          = a_tiempo_total,
        tarde             = tarde_total,
        top_vehiculos     = top_vehiculos,
        top_clientes      = top_clientes,
        total_multas      = total_multas,
        total_multas_monto= total_multas_monto,
        multas_pendientes = multas_pendientes,
        multas_pagadas    = multas_pagadas,
        labels_grafica    = labels_grafica,
        datos_grafica     = datos_grafica,
        ingresos_grafica  = ingresos_grafica,
        alquileres_tabla  = alquileres_tabla,
        lista_vehiculos   = lista_vehiculos,
        lista_clientes    = lista_clientes,
        filtro_cliente    = filtro_cliente,
        filtro_vehiculo   = filtro_vehiculo,
        filtro_estado     = filtro_estado,
        filtro_desde      = filtro_desde,
        filtro_hasta      = filtro_hasta,
    )


# ── Exportar PDF de consulta ──
@reportes_bp.route("/reportes/exportar-pdf")
def exportar_pdf():
    if "usuario" not in session or session["usuario"]["rol"] not in ["admin", "agente"]:
        return redirect(url_for("index"))

    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    hoy = datetime.now()

    filtro_cliente  = request.args.get("filtro_cliente", "").strip()
    filtro_vehiculo = request.args.get("filtro_vehiculo", "").strip()
    filtro_estado   = request.args.get("filtro_estado", "")
    filtro_desde    = request.args.get("filtro_desde", "")
    filtro_hasta    = request.args.get("filtro_hasta", "")

    query = {}
    if filtro_estado:
        query["estado"] = filtro_estado
    if filtro_desde:
        try:
            query.setdefault("fecha_inicio", {})["$gte"] = datetime.strptime(filtro_desde, "%Y-%m-%d")
        except: pass
    if filtro_hasta:
        try:
            query.setdefault("fecha_inicio", {})["$lte"] = datetime.strptime(filtro_hasta, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except: pass

    todos = list(alquileres_col.find(query).sort("fecha_creacion", -1))

    filas = []
    total_general = 0
    for a in todos:
        u = usuarios_col.find_one({"_id": a["usuario_id"]})
        v = vehiculos_col.find_one({"_id": a["vehiculo_id"]})
        nombre_cliente  = u["nombre"] if u else "N/A"
        nombre_vehiculo = f'{v["marca"]} {v["modelo"]} ({v["placa"]})' if v else "N/A"
        if filtro_cliente and filtro_cliente.lower() not in nombre_cliente.lower():
            continue
        if filtro_vehiculo and filtro_vehiculo.lower() not in nombre_vehiculo.lower():
            continue
        total_general += a.get("precio_total", 0)
        filas.append([
            nombre_cliente,
            nombre_vehiculo,
            a["fecha_inicio"].strftime("%d/%m/%Y"),
            a["fecha_fin"].strftime("%d/%m/%Y"),
            str(a.get("total_dias", 0)),
            f'${a.get("precio_total", 0):,}',
            a["estado"].upper()
        ])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=1.5*cm, rightMargin=1.5*cm)

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle("t", fontSize=18, fontName="Helvetica-Bold",
                                  textColor=colors.HexColor("#1F3864"), alignment=TA_CENTER, spaceAfter=4)
    sub_style    = ParagraphStyle("s", fontSize=11, fontName="Helvetica",
                                  textColor=colors.HexColor("#888888"), alignment=TA_CENTER, spaceAfter=12)

    story = []
    story.append(Paragraph("AutoRent — Reporte de Alquileres", titulo_style))

    filtros_str = f"Generado el {hoy.strftime('%d/%m/%Y %H:%M')}"
    if filtro_cliente:  filtros_str += f" | Cliente: {filtro_cliente}"
    if filtro_vehiculo: filtros_str += f" | Vehículo: {filtro_vehiculo}"
    if filtro_estado:   filtros_str += f" | Estado: {filtro_estado}"
    if filtro_desde:    filtros_str += f" | Desde: {filtro_desde}"
    if filtro_hasta:    filtros_str += f" | Hasta: {filtro_hasta}"
    story.append(Paragraph(filtros_str, sub_style))

    encabezado = [["Cliente", "Vehículo", "Inicio", "Fin", "Días", "Total", "Estado"]]
    tabla_data = encabezado + filas
    tabla_data.append(["", "", "", "", "", f"TOTAL: ${total_general:,}", f"{len(filas)} registros"])

    t = Table(tabla_data, colWidths=[5*cm, 6*cm, 2.5*cm, 2.5*cm, 1.8*cm, 3*cm, 2.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#1F3864")),
        ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS",(0,1), (-1,-2), [colors.HexColor("#F5F8FF"), colors.white]),
        ("BACKGROUND",    (0,-1), (-1,-1), colors.HexColor("#EBF3FB")),
        ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
        ("PADDING",       (0,0), (-1,-1), 5),
        ("ALIGN",         (4,0), (-1,-1), "CENTER"),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)

    nombre_pdf = f'reporte_alquileres_{hoy.strftime("%Y%m%d")}.pdf'
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=nombre_pdf)