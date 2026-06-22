import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.header import Header
import os


def get_smtp_config():
    host = os.environ.get('SMTP_HOST', '')
    port = int(os.environ.get('SMTP_PORT', '587'))
    user = os.environ.get('SMTP_USER', '')
    password = os.environ.get('SMTP_PASSWORD', '')
    if host and user and password:
        return {'host': host, 'port': port, 'user': user, 'password': password}
    return None


def send_hgt_email(smtp_conf, to_email, subject, body, pdf_bytes=None, pdf_name=None):
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_conf["user"]
        msg['To'] = to_email
        msg['Subject'] = Header(subject, 'utf-8').encode()
        html = (f"<html><body style='font-family:Arial,sans-serif;color:#212a37;'>"
                f"<p>{body.replace(chr(10), '<br>')}</p></body></html>")
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        if pdf_bytes and pdf_name:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(pdf_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={pdf_name}')
            msg.attach(part)
        srv = smtplib.SMTP(smtp_conf["host"], smtp_conf["port"])
        srv.starttls()
        srv.login(smtp_conf["user"], smtp_conf["password"])
        srv.send_message(msg)
        srv.quit()
        return True
    except Exception as e:
        return str(e)


def send_correccion_email(smtp_conf, to_email, nombre_func, rid, cambios):
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_conf["user"]
        msg['To'] = to_email
        msg['Subject'] = Header(f"Rendición de Gastos #{rid} - Correcciones Realizadas", 'utf-8').encode()
        rows_html = ""
        for c in cambios:
            rows_html += f"""<tr>
                <td style='padding:6px 10px;border:1px solid #ddd;'>{c['fila']}</td>
                <td style='padding:6px 10px;border:1px solid #ddd;'>{c['campo']}</td>
                <td style='padding:6px 10px;border:1px solid #ddd;color:#b91c1c;'>{c['anterior']}</td>
                <td style='padding:6px 10px;border:1px solid #ddd;color:#166534;'>{c['nuevo']}</td>
            </tr>"""
        html = f"""<html><body style='font-family:Arial,sans-serif;color:#212a37;'>
        <p>Estimado/a {nombre_func},</p>
        <p>Su rendición de gastos <b>#{rid}</b> fue procesada por el Encargado. Se realizaron las siguientes <b>correcciones</b> a la asignación de centros de costo / cuentas contables:</p>
        <table style='border-collapse:collapse;width:100%;margin:12px 0;'>
            <thead><tr style='background:#f3f4f6;'>
                <th style='padding:6px 10px;border:1px solid #ddd;'>Fila</th>
                <th style='padding:6px 10px;border:1px solid #ddd;'>Campo</th>
                <th style='padding:6px 10px;border:1px solid #ddd;'>Valor Anterior</th>
                <th style='padding:6px 10px;border:1px solid #ddd;'>Valor Nuevo</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <p>Si tiene alguna consulta, contacte al Encargado.</p>
        <p>Saludos,<br>Sistema de Rendiciones HGT</p>
        </body></html>"""
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        srv = smtplib.SMTP(smtp_conf["host"], smtp_conf["port"])
        srv.starttls()
        srv.login(smtp_conf["user"], smtp_conf["password"])
        srv.send_message(msg)
        srv.quit()
        return True
    except Exception as e:
        return str(e)
