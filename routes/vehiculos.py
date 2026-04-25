from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from config import vehiculos_col
from bson import ObjectId
from datetime import datetime
import os, io

vehiculos_bp = Blueprint("vehiculos", __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'documentos')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DOCS_LABELS = {
    "soat"             : "SOAT",
    "tecnomecanica"    : "Tecnomecánica",
    "tarjeta_propiedad": "Tarjeta de Propiedad",
    "seguro_todo_riesgo": "Seguro Todo Riesgo"
}

def recalcular_estados(vehiculo):
    hoy = datetime.now()
    if "documentos" in vehiculo and vehiculo["documentos"]:
        for doc_nombre, doc_info in vehiculo["documentos"].items():
            if "vencimiento" in doc_info and doc_info["vencimiento"]:
                doc_info["estado"] = "vigente" if doc_info["vencimiento"] >= hoy else "vencido"
    return vehiculo

def parse_fecha(valor):
    try:
        return datetime.strptime(valor, "%Y-%m-%d") if valor else None
    except:
        return None

def estado_doc(fecha):
    if fecha is None:
        return "vigente"
    return "vigente" if fecha > datetime.now() else "vencido"


# ── Listar vehículos ──
@vehiculos_bp.route("/vehiculos")
def listar():
    if "usuario" not in session:
        return redirect(url_for("auth.login"))
    vehiculos = list(vehiculos_col.find())
    for v in vehiculos:
        v["_id"] = str(v["_id"])
        recalcular_estados(v)
    return render_template("vehiculos/listar.html", vehiculos=vehiculos)


# ── Agregar vehículo ──
@vehiculos_bp.route("/vehiculos/agregar", methods=["GET", "POST"])
def agregar():
    if "usuario" not in session or session["usuario"]["rol"] not in ["admin", "agente"]:
        return redirect(url_for("index"))
    if request.method == "POST":
        vehiculos_col.insert_one({
            "marca"       : request.form["marca"],
            "modelo"      : request.form["modelo"],
            "año"         : int(request.form["año"]),
            "placa"       : request.form["placa"],
            "tipo"        : request.form["tipo"],
            "color"       : request.form["color"],
            "kilometraje" : int(request.form["kilometraje"]),
            "precio_dia"  : int(request.form["precio_dia"]),
            "estado"      : "disponible",
            "combustible" : request.form["combustible"],
            "transmision" : request.form["transmision"],
        })
        flash("Vehículo agregado correctamente", "success")
        return redirect(url_for("vehiculos.listar"))
    return render_template("vehiculos/agregar.html")


# ── Editar vehículo ──
@vehiculos_bp.route("/vehiculos/editar/<id>", methods=["GET", "POST"])
def editar(id):
    if "usuario" not in session or session["usuario"]["rol"] not in ["admin", "agente"]:
        return redirect(url_for("index"))
    vehiculo = vehiculos_col.find_one({"_id": ObjectId(id)})
    vehiculo["_id"] = str(vehiculo["_id"])
    recalcular_estados(vehiculo)
    if request.method == "POST":
        vehiculos_col.update_one({"_id": ObjectId(id)}, {"$set": {
            "marca"       : request.form["marca"],
            "modelo"      : request.form["modelo"],
            "año"         : int(request.form["año"]),
            "color"       : request.form["color"],
            "kilometraje" : int(request.form["kilometraje"]),
            "precio_dia"  : int(request.form["precio_dia"]),
            "estado"      : request.form["estado"],
            "combustible" : request.form["combustible"],
            "transmision" : request.form["transmision"],
        }})
        flash("Vehículo actualizado correctamente", "success")
        return redirect(url_for("vehiculos.listar"))
    return render_template("vehiculos/editar.html", vehiculo=vehiculo)


# ── Eliminar vehículo ──
@vehiculos_bp.route("/vehiculos/eliminar/<id>")
def eliminar(id):
    if "usuario" not in session or session["usuario"]["rol"] != "admin":
        return redirect(url_for("index"))
    vehiculos_col.delete_one({"_id": ObjectId(id)})
    flash("Vehículo eliminado", "warning")
    return redirect(url_for("vehiculos.listar"))


# ── Guardar documentos + imágenes ──
@vehiculos_bp.route("/vehiculos/documentos/<id>", methods=["POST"])
def guardar_documentos(id):
    if "usuario" not in session or session["usuario"]["rol"] not in ["admin", "agente"]:
        return redirect(url_for("index"))

    soat_venc = parse_fecha(request.form.get("soat_vencimiento"))
    tec_venc  = parse_fecha(request.form.get("tec_vencimiento"))
    seg_venc  = parse_fecha(request.form.get("seg_vencimiento"))

    # Carpeta para las imágenes de este vehículo
    carpeta_v = os.path.join(UPLOAD_FOLDER, id)
    os.makedirs(carpeta_v, exist_ok=True)

    def guardar_imagen(campo):
        archivo = request.files.get(campo)
        if archivo and archivo.filename:
            ext  = os.path.splitext(archivo.filename)[1].lower()
            nombre = campo + ext
            ruta = os.path.join(carpeta_v, nombre)
            archivo.save(ruta)
            return f"documentos/{id}/{nombre}"
        return None

    # Cargar documentos existentes para conservar imágenes previas
    vehiculo_actual = vehiculos_col.find_one({"_id": ObjectId(id)})
    docs_actuales   = vehiculo_actual.get("documentos", {}) if vehiculo_actual else {}

    documentos = {}

    if request.form.get("soat_numero"):
        img = guardar_imagen("soat_imagen") or docs_actuales.get("soat", {}).get("imagen")
        documentos["soat"] = {
            "numero"     : request.form["soat_numero"],
            "vencimiento": soat_venc,
            "estado"     : estado_doc(soat_venc),
            "imagen"     : img
        }

    if request.form.get("tec_numero"):
        img = guardar_imagen("tec_imagen") or docs_actuales.get("tecnomecanica", {}).get("imagen")
        documentos["tecnomecanica"] = {
            "numero"     : request.form["tec_numero"],
            "vencimiento": tec_venc,
            "estado"     : estado_doc(tec_venc),
            "imagen"     : img
        }

    if request.form.get("tp_numero"):
        img = guardar_imagen("tp_imagen") or docs_actuales.get("tarjeta_propiedad", {}).get("imagen")
        documentos["tarjeta_propiedad"] = {
            "numero": request.form["tp_numero"],
            "estado": "vigente",
            "imagen": img
        }

    if request.form.get("seg_numero"):
        img = guardar_imagen("seg_imagen") or docs_actuales.get("seguro_todo_riesgo", {}).get("imagen")
        documentos["seguro_todo_riesgo"] = {
            "numero"     : request.form["seg_numero"],
            "aseguradora": request.form.get("seg_aseguradora", ""),
            "vencimiento": seg_venc,
            "estado"     : estado_doc(seg_venc),
            "imagen"     : img
        }

    vehiculos_col.update_one({"_id": ObjectId(id)}, {"$set": {"documentos": documentos}})
    flash("Documentos actualizados correctamente", "success")
    return redirect(url_for("vehiculos.editar", id=id))


# ── Generar PDF de documentos ──
@vehiculos_bp.route("/vehiculos/documentos/pdf/<id>")
def generar_pdf(id):
    if "usuario" not in session:
        return redirect(url_for("auth.login"))

    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    vehiculo = vehiculos_col.find_one({"_id": ObjectId(id)})
    recalcular_estados(vehiculo)
    docs = vehiculo.get("documentos", {})

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=letter,
                               topMargin=2*cm, bottomMargin=2*cm,
                               leftMargin=2*cm, rightMargin=2*cm)

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle("titulo", fontSize=20, fontName="Helvetica-Bold",
                                  textColor=colors.HexColor("#1F3864"), alignment=TA_CENTER, spaceAfter=6)
    sub_style    = ParagraphStyle("sub", fontSize=12, fontName="Helvetica",
                                  textColor=colors.HexColor("#2E75B6"), alignment=TA_CENTER, spaceAfter=4)
    label_style  = ParagraphStyle("label", fontSize=9, fontName="Helvetica-Bold",
                                  textColor=colors.HexColor("#666666"), spaceBefore=4)
    valor_style  = ParagraphStyle("valor", fontSize=11, fontName="Helvetica",
                                  textColor=colors.HexColor("#111111"))
    doc_titulo   = ParagraphStyle("doctitulo", fontSize=13, fontName="Helvetica-Bold",
                                  textColor=colors.HexColor("#1F3864"), spaceBefore=16, spaceAfter=8)

    story = []

    # Encabezado
    story.append(Paragraph("AutoRent — Sistema de Alquiler de Vehículos", titulo_style))
    story.append(Paragraph("Documentos Legales del Vehículo", sub_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1F3864")))
    story.append(Spacer(1, 0.4*cm))

    # Datos del vehículo
    datos_tabla = [
        ["Vehículo", f'{vehiculo["marca"]} {vehiculo["modelo"]} {vehiculo["año"]}',
         "Placa", vehiculo["placa"]],
        ["Tipo", vehiculo.get("tipo", "—").capitalize(),
         "Color", vehiculo.get("color", "—")],
        ["Estado", vehiculo.get("estado", "—").capitalize(),
         "Precio/día", f'${vehiculo.get("precio_dia", 0):,}'],
    ]
    t = Table(datos_tabla, colWidths=[3.5*cm, 6*cm, 3.5*cm, 4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#EBF3FB")),
        ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#EBF3FB")),
        ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",   (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 10),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.HexColor("#F5F8FF"), colors.white]),
        ("PADDING",    (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CCCCCC")))

    # Documentos
    for clave, label in DOCS_LABELS.items():
        info = docs.get(clave)
        if not info:
            continue

        story.append(Paragraph(label, doc_titulo))

        estado    = info.get("estado", "vigente")
        color_est = colors.HexColor("#00A550") if estado == "vigente" else colors.HexColor("#CC0000")

        filas = [["Campo", "Valor"]]
        filas.append(["Número", info.get("numero", "—")])
        if "vencimiento" in info and info["vencimiento"]:
            filas.append(["Vencimiento", info["vencimiento"].strftime("%d/%m/%Y")])
        if "aseguradora" in info:
            filas.append(["Aseguradora", info.get("aseguradora", "—")])
        filas.append(["Estado", estado.upper()])

        td = Table(filas, colWidths=[5*cm, 12*cm])
        td.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#1F3864")),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME",    (0,1), (0,-1), "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 10),
            ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#F5F8FF"), colors.white]),
            ("PADDING",     (0,0), (-1,-1), 6),
            ("TEXTCOLOR",   (1,-1), (1,-1), color_est),
            ("FONTNAME",    (1,-1), (1,-1), "Helvetica-Bold"),
        ]))
        story.append(td)

        # Imagen si existe (solo si es imagen, no PDF)
        if info.get("imagen"):
            ruta_img = os.path.join(os.path.dirname(__file__), '..', 'static', info["imagen"])
            ext = os.path.splitext(ruta_img)[1].lower()
            if os.path.exists(ruta_img) and ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                story.append(Spacer(1, 0.3*cm))
                try:
                    img = Image(ruta_img, width=14*cm, height=9*cm, kind="proportional")
                    story.append(img)
                except:
                    story.append(Paragraph("(No se pudo cargar la imagen)", styles["Normal"]))
            elif ext == '.pdf':
                story.append(Spacer(1, 0.2*cm))
                story.append(Paragraph("Archivo adjunto: PDF (ver archivo original)", styles["Normal"]))

        story.append(Spacer(1, 0.3*cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#DDDDDD")))

    doc.build(story)
    buffer.seek(0)

    nombre_pdf = f'documentos_{vehiculo["placa"]}.pdf'
    return send_file(buffer, mimetype="application/pdf",
                     as_attachment=True, download_name=nombre_pdf)
