import io
from datetime import datetime
import pandas as pd
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, send_file
from app.database import (
    db_get_rendicion, db_encargado_approve, db_encargado_reject,
    db_get_encargado_stats, db_get_rendiciones_by_status,
    db_reassign_jefatura, db_get_jefaturas, _exec_df_query, 
    db_get_dashboard_data, format_curr, db_get_users,
    db_get_terminales, db_get_centros_costos, db_get_cuentas_contables,
    db_update_rendicion_data_json
)
from app.utils.pdf_generator import generate_hgt_pdf
from app.utils.security import login_required
from app.utils.csrf import csrf_required
from app.utils.email_service import send_hgt_email
import os

encargado_bp = Blueprint('encargado', __name__)


@encargado_bp.route('/encargado', methods=['GET'])
@login_required
def panel():
    stats = db_get_encargado_stats()
    filtro = request.args.get('filtro', 'Todas')
    
    if filtro == 'Por Procesar':
        df_display = db_get_rendiciones_by_status(["APROBADO_POR_JEFATURA"])
    elif filtro == 'En Jefatura':
        df_display = db_get_rendiciones_by_status(["pendiente"])
        email = session.get('email', '')
        if not df_display.empty and 'email_jefatura' in df_display.columns:
            df_display = df_display[df_display['email_jefatura'].str.lower() == email.lower()]
    elif filtro == 'Procesadas':
        df_display = db_get_rendiciones_by_status(["PROCESADO_ENCARGADO"])
    else:
        df_display = db_get_rendiciones_by_status(None)
    
    rendiciones = df_display.to_dict('records') if not df_display.empty else []
    jefaturas = db_get_jefaturas().to_dict('records') if not db_get_jefaturas().empty else []
    user = {'email': session.get('email', ''), 'nombre': session.get('fullname', '')}
    
    return render_template('encargado.html', stats=stats, rendiciones=rendiciones,
                           jefaturas=jefaturas, user=user, filtro=filtro)


@encargado_bp.route('/encargado/<int:rid>/detail', methods=['GET'])
@login_required
def detail(rid):
    data, pdf_fname, email_func, nombre_func, pdf_aprobado = db_get_rendicion(rid)
    if not data:
        flash("Rendición no encontrada.", "error")
        return redirect(url_for('encargado.panel'))
    return render_template('encargado.html', stats=db_get_encargado_stats(),
                           rendiciones=[], detail_rid=rid, data=data,
                           pdf_aprobado=pdf_aprobado, email_func=email_func,
                           nombre_func=nombre_func, user=session, filtro='Todas',
                           cuentas_contables=db_get_cuentas_contables().to_dict('records'))


@encargado_bp.route('/encargado/<int:rid>/procesar', methods=['POST'])
@login_required
@csrf_required
def procesar(rid):
    data, pdf_fname, email_func, nombre_func, _ = db_get_rendicion(rid)
    pdf_bytes = generate_hgt_pdf(data) if data else None
    db_encargado_approve(rid)
    smtp_conf = _get_smtp_config()
    if smtp_conf and email_func and pdf_bytes:
        subject = f"Rendición de Gastos APROBADA - {nombre_func}"
        body = (
            f"Estimado/a {nombre_func},\n\n"
            f"Su rendición de gastos #{rid} ha sido aprobada y procesada por el Encargado.\n\n"
            f"Adjunto encontrará el PDF con el detalle completo.\n\n"
            f"Saludos,\nSistema de Rendiciones HGT"
        )
        pdf_name = pdf_fname or f"Rendicion_HGT_{nombre_func}_{rid}.pdf"
        send_hgt_email(smtp_conf, email_func, subject, body, pdf_bytes=pdf_bytes, pdf_name=pdf_name)
    flash(f"Rendición #{rid} procesada y notificada.", "success")
    return redirect(url_for('encargado.panel'))


@encargado_bp.route('/encargado/<int:rid>/rechazar', methods=['POST'])
@login_required
@csrf_required
def rechazar(rid):
    coment = request.form.get('comentario', '').strip()
    if not coment:
        flash("Debe ingresar un motivo de rechazo.", "error")
        return redirect(url_for('encargado.detail', rid=rid))
    data, pdf_fname, email_func, nombre_func, _ = db_get_rendicion(rid)
    db_encargado_reject(rid, coment)
    smtp_conf = _get_smtp_config()
    if smtp_conf and email_func:
        subject = f"Rendición de Gastos RECHAZADA - {nombre_func}"
        body = (
            f"Estimado/a {nombre_func},\n\n"
            f"Su rendición de gastos #{rid} ha sido rechazada por el Encargado.\n\n"
            f"Motivo:\n{coment}\n\n"
            f"Saludos,\nSistema de Rendiciones HGT"
        )
        send_hgt_email(smtp_conf, email_func, subject, body)
    flash("Rendición rechazada y notificada.", "warning")
    return redirect(url_for('encargado.panel'))


@encargado_bp.route('/encargado/<int:rid>/reasignar', methods=['POST'])
@login_required
@csrf_required
def reasignar(rid):
    new_email = request.form.get('new_jefatura_email', '').strip()
    if not new_email:
        flash("Seleccione una jefatura.", "error")
        return redirect(url_for('encargado.detail', rid=rid))
    db_reassign_jefatura(rid, new_email)
    flash(f"Jefatura reasignada. Rendición #{rid} reiniciada a pendiente.", "success")
    return redirect(url_for('encargado.panel'))


@encargado_bp.route('/encargado/<int:rid>/update-cuentas', methods=['POST'])
@login_required
@csrf_required
def update_cuentas(rid):
    data, _, _, _, _ = db_get_rendicion(rid)
    if not data:
        flash("Rendición no encontrada.", "error")
        return redirect(url_for('encargado.panel'))
    df_comision = data.get('df_comision')
    if df_comision is not None and not df_comision.empty and 'Cuenta Contable' in df_comision.columns:
        for idx in range(len(df_comision)):
            key = f'cc_{idx}'
            new_val = request.form.get(key, '')
            if new_val:
                df_comision.at[df_comision.index[idx], 'Cuenta Contable'] = new_val
        data['df_comision'] = df_comision
    db_update_rendicion_data_json(rid, data)
    flash("Cuentas contables actualizadas.", "success")
    return redirect(url_for('encargado.detail', rid=rid))


@encargado_bp.route('/encargado/dashboard-data', methods=['GET'])
@login_required
def dashboard_data():
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')
    usuario_id = request.args.get('usuario_id', '')
    sucursal = request.args.get('sucursal', '')
    codigo_cc = request.args.get('codigo_cc', '')
    cuenta_id = request.args.get('cuenta_id', '')

    df_raw = db_get_dashboard_data(
        fecha_desde=desde or None, fecha_hasta=hasta or None,
        usuario_id=usuario_id or None, sucursal=sucursal or None,
        codigo_cc=codigo_cc or None, cuenta_id=cuenta_id or None
    )

    if not df_raw.empty:
        df_raw['codigo_cc'] = df_raw['codigo_cc'].fillna('Sin CC')
        df_raw['centro_costo'] = df_raw['centro_costo'].fillna('Sin CC asignado')
        df_raw['codigo_cuenta'] = df_raw['codigo_cuenta'].fillna('N/A')
        df_raw['cuenta_detalle'] = df_raw['cuenta_detalle'].fillna('Sin cuenta')
        df_raw['concepto_amigable'] = df_raw['concepto_amigable'].fillna('Sin cuenta')
        df_agrupado = df_raw.groupby(
            ['codigo_cc', 'centro_costo', 'codigo_cuenta', 'cuenta_detalle', 'concepto_amigable'],
            dropna=False
        ).agg(
            Transacciones=('id', 'count'),
            Monto_Total=('monto_total', 'sum')
        ).reset_index().sort_values(['codigo_cc', 'Monto_Total'], ascending=[True, False])
        records = df_agrupado.to_dict('records')
    else:
        records = []

    subtotales = {}
    for r in records:
        cc = r['codigo_cc']
        if cc not in subtotales:
            subtotales[cc] = {'monto': 0, 'transacciones': 0}
        subtotales[cc]['monto'] += r['Monto_Total']
        subtotales[cc]['transacciones'] += r['Transacciones']

    total_general = sum(s['monto'] for s in subtotales.values())
    total_transacciones = sum(s['transacciones'] for s in subtotales.values())

    usuarios = db_get_users().to_dict('records')
    terminales = db_get_terminales().to_dict('records')
    centros = db_get_centros_costos().to_dict('records')
    cuentas_list = db_get_cuentas_contables().to_dict('records')

    return render_template('encargado_dashboard.html',
                           dashboard_data=records,
                           subtotales=subtotales,
                           total_general=total_general,
                           total_transacciones=total_transacciones,
                           usuarios=usuarios, terminales=terminales,
                           centros_costo=centros, cuentas=cuentas_list,
                           filtros={'desde': desde, 'hasta': hasta, 'usuario_id': usuario_id,
                                    'sucursal': sucursal, 'codigo_cc': codigo_cc, 'cuenta_id': cuenta_id},
                           user=session)


@encargado_bp.route('/encargado/export-excel', methods=['GET'])
@login_required
def export_excel():
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')
    usuario_id = request.args.get('usuario_id', '')
    sucursal = request.args.get('sucursal', '')
    codigo_cc = request.args.get('codigo_cc', '')
    cuenta_id = request.args.get('cuenta_id', '')

    df_raw = db_get_dashboard_data(
        fecha_desde=desde or None, fecha_hasta=hasta or None,
        usuario_id=usuario_id or None, sucursal=sucursal or None,
        codigo_cc=codigo_cc or None, cuenta_id=cuenta_id or None
    )
    if not df_raw.empty:
        df_agrupado = df_raw.groupby(
            ['codigo_cc', 'centro_costo', 'codigo_cuenta', 'cuenta_detalle', 'concepto_amigable']
        ).agg(
            Transacciones=('id', 'count'),
            Monto_Total=('monto_total', 'sum')
        ).reset_index().sort_values(['codigo_cc', 'Monto_Total'], ascending=[True, False])
    else:
        df_agrupado = pd.DataFrame()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_agrupado.to_excel(writer, sheet_name='Resumen', index=False)
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='Resumen_Ejecutivo.xlsx')


def _get_smtp_config():
    host = os.environ.get('SMTP_HOST', '')
    port = os.environ.get('SMTP_PORT', '587')
    user = os.environ.get('SMTP_USER', '')
    password = os.environ.get('SMTP_PASSWORD', '')
    if host and user and password:
        return {'host': host, 'port': int(port), 'user': user, 'password': password}
    return None
