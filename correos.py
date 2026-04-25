import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

# ── Configuración Gmail ──
GMAIL_USER = os.environ.get("GMAIL_USER", "jhoymerlopez75@gmail.com")
GMAIL_PASS = os.environ.get("GMAIL_PASS", "nhlc vamp eokp tmkz")

def enviar_correo(destinatario, asunto, html):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"]    = f"AutoRent <{GMAIL_USER}>"
        msg["To"]      = destinatario
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, destinatario, msg.as_string())
        print(f"✅ Correo enviado a {destinatario}")
        return True
    except Exception as e:
        print(f"❌ Error enviando correo: {e}")
        return False


def base_html(contenido):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 30px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.1); }}
        .header {{ background: #0A0A0A; padding: 28px 32px; text-align: center; }}
        .header h1 {{ color: #E8FF00; font-size: 26px; margin: 0; letter-spacing: 2px; }}
        .header p {{ color: #888; font-size: 13px; margin: 4px 0 0; }}
        .body {{ padding: 32px; color: #333; }}
        .body h2 {{ color: #1F3864; font-size: 20px; margin-bottom: 8px; }}
        .body p {{ font-size: 15px; line-height: 1.6; color: #555; }}
        .info-box {{ background: #F5F8FF; border-left: 4px solid #1F3864; border-radius: 6px; padding: 16px 20px; margin: 20px 0; }}
        .info-box table {{ width: 100%; border-collapse: collapse; }}
        .info-box td {{ padding: 6px 0; font-size: 14px; }}
        .info-box td:first-child {{ color: #888; width: 40%; }}
        .info-box td:last-child {{ color: #111; font-weight: 600; }}
        .badge-green {{ display: inline-block; background: #e6f9f0; color: #00a550; padding: 4px 14px; border-radius: 20px; font-weight: 700; font-size: 13px; }}
        .badge-red {{ display: inline-block; background: #fff0eb; color: #cc3300; padding: 4px 14px; border-radius: 20px; font-weight: 700; font-size: 13px; }}
        .badge-yellow {{ display: inline-block; background: #fffbe6; color: #b8860b; padding: 4px 14px; border-radius: 20px; font-weight: 700; font-size: 13px; }}
        .footer {{ background: #f9f9f9; text-align: center; padding: 20px; font-size: 12px; color: #aaa; border-top: 1px solid #eee; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>AutoRent</h1>
          <p>Sistema de Alquiler de Vehículos</p>
        </div>
        <div class="body">
          {contenido}
        </div>
        <div class="footer">
          Este es un correo automático, por favor no respondas a este mensaje.<br>
          © 2026 AutoRent — Todos los derechos reservados.
        </div>
      </div>
    </body>
    </html>
    """


# ── Correo: alquiler creado ──
def correo_alquiler_creado(cliente_email, cliente_nombre, vehiculo, fecha_inicio, fecha_fin, dias, total, metodo_pago):
    contenido = f"""
    <h2>¡Tu alquiler está confirmado!</h2>
    <p>Hola <strong>{cliente_nombre}</strong>, tu alquiler ha sido registrado exitosamente. Aquí están los detalles:</p>
    <div class="info-box">
      <table>
        <tr><td>Vehículo</td><td>{vehiculo}</td></tr>
        <tr><td>Fecha de inicio</td><td>{fecha_inicio}</td></tr>
        <tr><td>Fecha de entrega</td><td>{fecha_fin}</td></tr>
        <tr><td>Duración</td><td>{dias} día(s)</td></tr>
        <tr><td>Total pagado</td><td>${total:,} COP</td></tr>
        <tr><td>Método de pago</td><td>{metodo_pago.capitalize()}</td></tr>
        <tr><td>Estado</td><td><span class="badge-green">✓ Confirmado</span></td></tr>
      </table>
    </div>
    <p>Recuerda entregar el vehículo en la fecha acordada. Si te pasas de la fecha se generará una multa automática por cada día de retraso.</p>
    <p>¡Gracias por confiar en AutoRent!</p>
    """
    return enviar_correo(cliente_email, "✅ Alquiler confirmado — AutoRent", base_html(contenido))


# ── Correo: alquiler finalizado ──
def correo_alquiler_finalizado(cliente_email, cliente_nombre, vehiculo, fecha_inicio, fecha_fin, dias, total):
    contenido = f"""
    <h2>Tu alquiler ha finalizado</h2>
    <p>Hola <strong>{cliente_nombre}</strong>, tu alquiler ha sido finalizado correctamente. Gracias por devolver el vehículo.</p>
    <div class="info-box">
      <table>
        <tr><td>Vehículo</td><td>{vehiculo}</td></tr>
        <tr><td>Fecha de inicio</td><td>{fecha_inicio}</td></tr>
        <tr><td>Fecha de entrega</td><td>{fecha_fin}</td></tr>
        <tr><td>Duración</td><td>{dias} día(s)</td></tr>
        <tr><td>Total</td><td>${total:,} COP</td></tr>
        <tr><td>Estado</td><td><span class="badge-green">✓ Finalizado</span></td></tr>
      </table>
    </div>
    <p>Esperamos que hayas tenido una excelente experiencia. ¡Vuelve pronto!</p>
    """
    return enviar_correo(cliente_email, "🏁 Alquiler finalizado — AutoRent", base_html(contenido))


# ── Correo: multa registrada ──
def correo_multa_registrada(cliente_email, cliente_nombre, vehiculo, descripcion, monto, tipo="daño"):
    if tipo == "retraso":
        titulo   = "Multa por retraso en entrega"
        subtitulo = "Se ha registrado una multa por entregar el vehículo después de la fecha acordada."
        badge     = '<span class="badge-yellow">⚠ Retraso</span>'
    else:
        titulo   = "Se ha registrado una multa"
        subtitulo = "Se ha registrado una multa asociada a tu alquiler."
        badge     = '<span class="badge-red">⚠ Daño</span>'

    contenido = f"""
    <h2>{titulo}</h2>
    <p>Hola <strong>{cliente_nombre}</strong>, {subtitulo}</p>
    <div class="info-box">
      <table>
        <tr><td>Vehículo</td><td>{vehiculo}</td></tr>
        <tr><td>Descripción</td><td>{descripcion}</td></tr>
        <tr><td>Monto</td><td>${monto:,} COP</td></tr>
        <tr><td>Estado</td><td>{badge}</td></tr>
      </table>
    </div>
    <p>Por favor comunícate con nosotros para realizar el pago o si deseas disputar esta multa.</p>
    """
    return enviar_correo(cliente_email, "⚠️ Multa registrada — AutoRent", base_html(contenido))
