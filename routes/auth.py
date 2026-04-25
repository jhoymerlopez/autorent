from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from config import usuarios_col, empleados_col
import bcrypt

auth_bp = Blueprint("auth", __name__)

# ── Login ──
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]

        # Buscar en usuarios (clientes)
        usuario = usuarios_col.find_one({"email": email})
        if usuario and bcrypt.checkpw(password.encode("utf-8"), usuario["password"].encode("utf-8")):
            session["usuario"] = {
                "id"     : str(usuario["_id"]),
                "nombre" : usuario["nombre"],
                "email"  : usuario["email"],
                "rol"    : "cliente"
            }
            return redirect(url_for("index"))

        # Buscar en empleados (admin / agente)
        empleado = empleados_col.find_one({"email": email})
        if empleado and bcrypt.checkpw(password.encode("utf-8"), empleado["password"].encode("utf-8")):
            session["usuario"] = {
                "id"     : str(empleado["_id"]),
                "nombre" : empleado["nombre"],
                "email"  : empleado["email"],
                "rol"    : empleado["rol"]
            }
            return redirect(url_for("index"))

        flash("Correo o contraseña incorrectos", "danger")

    return render_template("login.html")


# ── Registro de nuevo cliente ──
@auth_bp.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre   = request.form["nombre"]
        email    = request.form["email"]
        password = request.form["password"]
        telefono = request.form["telefono"]
        doc_tipo = request.form["doc_tipo"]
        doc_num  = request.form["doc_num"]
        licencia = request.form["licencia"]

        # Verificar si el email ya existe
        if usuarios_col.find_one({"email": email}):
            flash("El correo ya está registrado", "danger")
            return render_template("registro.html")

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        usuarios_col.insert_one({
            "nombre"   : nombre,
            "email"    : email,
            "password" : hashed,
            "telefono" : telefono,
            "documento": {"tipo": doc_tipo, "numero": doc_num},
            "licencia" : licencia,
            "activo"   : True
        })

        flash("Registro exitoso, inicia sesión", "success")
        return redirect(url_for("auth.login"))

    return render_template("registro.html")


# ── Logout ──
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
