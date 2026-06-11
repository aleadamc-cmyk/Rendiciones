from datetime import datetime
import pandas as pd
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from app.database import (
    db_get_rendicion, db_approve, db_reject, _exec_df_query,
    db_get_pending, format_curr, serialize_data
)
from app.utils.pdf_generator import generate_hgt_pdf
from app.utils.security import login_required
from app.utils.csrf import csrf_required
from app.utils.email_service import send_hgt_email
import os

aprobaciones_bp = Blueprint('aprobaciones', __name__)


@aprobaciones_bp.route('/aprobaciones', methods=['GET'])
@login_required
def listar():
    email = session.get('email', '')
    df_p = _exec_df_query(
        "SELECT id, nombre, total, fecha_registro, moneda FROM rendiciones_workflow "
        "WHERE LOWER(TRIM(email_jefatura)) = LOWER(?) AND status = 'pendiente'",
        params=(email.strip(),)
    )
    pendientes = df_p.to_dict('records') if not df_p.empty else []
    return render_template('aprobaciones.html', pendientes=pendientes, user=session)


@aprobaciones_bp.route('/aprobaciones/<int:rid>/detail', methods=['GET'])
@login_required
def detail(rid):
    data, pdf_fname, email_func, nombre_func, pdf_aprobado = db_get_rendicion(rid)
    if not data:
        flash("Rendición no encontrada.", "error")
        return redirect(url_for('aprobaciones.listar'))
    return render_template('aprobaciones.html',
                           pendientes=[],
                           detail_rid=rid,
                           data=data,
                           pdf_aprobado=pdf_aprobado,
                           email_func=email_func,
                           nombre_func=nombre_func,
                           user=session)


@aprobaciones_bp.route('/aprobaciones/<int:rid>/approve', methods=['POST'])
@login_required
@csrf_required
def approve(rid):
    user = {'id': session.get('user_id'), 'sid': session.get('sid', ''),
            'rut': session.get('rut', ''), 'nombre': session.get('fullname', '')}
    rut_input = request.form.get('rut_confirm', '').strip()
    data, pdf_fname, email_func, nombre_func, _ = db_get_rendicion(rid)
    if not data:
        flash("Rendición no encontrada.", "error")
        return redirect(url_for('aprobaciones.listar'))
    if not rut_input:
        flash("Debe ingresar su RUT.", "error")
        return redirect(url_for('aprobaciones.detail', rid=rid))
    data['fecha_aprobacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data['jefe_id'] = user.get('id')
    data['jefe_sid'] = user.get('sid')
    data['jefe_rut'] = user.get('rut')
    data['jefe_nombre'] = user.get('nombre')
    pdf_final = generate_hgt_pdf(data)
    db_approve(rid, pdf_final, data)
    flash(f"Rendición #{rid} aprobada correctamente.", "success")
    return redirect(url_for('aprobaciones.listar'))


@aprobaciones_bp.route('/aprobaciones/<int:rid>/reject', methods=['POST'])
@login_required
@csrf_required
def reject(rid):
    motivo = request.form.get('motivo', '').strip()
    data, pdf_fname, email_func, nombre_func, _ = db_get_rendicion(rid)
    if not data:
        flash("Rendición no encontrada.", "error")
        return redirect(url_for('aprobaciones.listar'))
    if not motivo:
        flash("Debe ingresar un motivo de rechazo.", "error")
        return redirect(url_for('aprobaciones.detail', rid=rid))
    db_reject(rid, motivo)
    smtp_conf = _get_smtp_config()
    if smtp_conf and email_func:
        subject = f"Rendición de Gastos RECHAZADA - {nombre_func}"
        body = (
            f"Estimado/a {nombre_func},\n\n"
            f"Su rendición de gastos #{rid} ha sido RECHAZADA.\n\n"
            f"Motivo:\n{motivo}\n\n"
            f"Puede ingresar al sistema para corregirla y volver a enviarla.\n\n"
            f"Saludos,\nSistema de Rendiciones HGT"
        )
        send_hgt_email(smtp_conf, email_func, subject, body)
    flash("Rendición rechazada y notificada.", "warning")
    return redirect(url_for('aprobaciones.listar'))


def _get_smtp_config():
    host = os.environ.get('SMTP_HOST', '')
    port = os.environ.get('SMTP_PORT', '587')
    user = os.environ.get('SMTP_USER', '')
    password = os.environ.get('SMTP_PASSWORD', '')
    if host and user and password:
        return {'host': host, 'port': int(port), 'user': user, 'password': password}
    return None
