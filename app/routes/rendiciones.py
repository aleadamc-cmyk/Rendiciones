import json
import base64
import os
from datetime import datetime
from io import BytesIO
import pandas as pd
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from app.database import (
    db_submit_rendicion, db_update_rendicion, db_get_user_rendiciones, db_get_rendicion,
    db_get_trayectos_dict, db_get_jefaturas, db_get_cuentas_contables,
    db_get_usuario_centros_costos, db_get_centros_costos, db_get_centro_costo_cuentas,
    db_get_all_centro_costo_cuentas, db_get_usuario_cc_cuentas, db_get_topes_usd_dict,
    format_curr, serialize_data, deserialize_data
)
from app.utils.security import login_required
from app.utils.csrf import csrf_required
from app.utils.pdf_generator import generate_hgt_pdf
from app.utils.email_service import send_hgt_email, get_smtp_config
from app.utils.ai_service import process_receipt_with_ai, process_id_card_with_ai

rendiciones_bp = Blueprint('rendiciones', __name__)


@rendiciones_bp.route('/rendiciones', methods=['GET', 'POST'])
@login_required
def listar():
    user = {
        'id': session['user_id'], 'nombre': session['fullname'],
        'email': session['email'], 'role': session['role'],
        'username': session['username'],
        'rut': session.get('rut', ''),
        'centro_costo': session.get('centro_costo', ''),
    }
    df_mine = db_get_user_rendiciones(user['email'])
    rendiciones_list = df_mine.to_dict('records') if not df_mine.empty else []
    jefaturas = db_get_jefaturas().to_dict('records') if not db_get_jefaturas().empty else []
    user_ccs = db_get_usuario_centros_costos(session['user_id'])
    df_ccs = db_get_centros_costos()
    if user_ccs and not df_ccs.empty:
        df_ccs = df_ccs[df_ccs['codigo_cc'].isin(user_ccs)]
    centros_costo = df_ccs.to_dict('records') if not df_ccs.empty else []
    user_cc_asignado = user_ccs[0] if user_ccs else ''
    cuentas = db_get_cuentas_contables().to_dict('records') if not db_get_cuentas_contables().empty else []
    df_all_cc_cuentas = db_get_all_centro_costo_cuentas()
    cc_cuentas_map = {}
    if not df_all_cc_cuentas.empty:
        for _, row in df_all_cc_cuentas.iterrows():
            cc_cuentas_map.setdefault(row['codigo_cc'], []).append(row['codigo_cuenta'])
    trayectos = db_get_trayectos_dict()

    is_super = session.get('permissions', {}).get('is_super', False)

    return render_template('rendiciones.html',
                           user=user, rendiciones=rendiciones_list,
                           jefaturas=jefaturas, centros_costo=centros_costo,
                           cuentas=cuentas, cc_cuentas_map=json.dumps(cc_cuentas_map),
                           trayectos_json=json.dumps(trayectos, default=str),
                           is_super=is_super, user_cc_asignado=user_cc_asignado)


@rendiciones_bp.route('/rendiciones/submit', methods=['POST'])
@login_required
@csrf_required
def submit():
    user = {
        'id': session['user_id'], 'nombre': session['fullname'],
        'email': session['email'], 'role': session['role'],
        'username': session['username'], 'sid': session.get('sid', ''),
    }
    data = request.form
    nombre = data.get('nombre', user['nombre'])
    rut = data.get('rut', '')
    moneda = data.get('moneda', 'CLP')
    centro_costo = data.get('centro_costo', '')
    email_jefe = data.get('email_jefe', '')
    anticipo = float(data.get('anticipo', 0))
    editing_rid = data.get('editing_rid')

    df_comision = _parse_df_from_form(data, 'comision', ['Traslado', 'Desde oficina', 'A localidad', 'Fecha Inicio', 'Fecha Término', 'Num_acompanantes', 'Nombres_acompanantes'])
    df_aloj = _parse_df_from_form(data, 'aloj', ['Detalle', 'Fecha', 'Doc', 'Monto'])
    df_alim = _parse_df_from_form(data, 'alim', ['Detalle', 'Tipo', 'Fecha', 'Doc', 'Monto'])
    df_otros = _parse_df_from_form(data, 'otros', ['Detalle', 'Fecha', 'Doc', 'Monto'])

    trayectos = db_get_trayectos_dict()
    df_vehicle = _calc_vehicle_costs(df_comision, trayectos, centro_costo)
    if not df_vehicle.empty:
        df_otros = pd.concat([df_otros, df_vehicle], ignore_index=True)

    receipt_photos = []
    for f in request.files.getlist('receipt_files'):
        if f.filename:
            receipt_photos.append(f.read())

    def calc_subtotals(d_aloj, d_alim, d_ot):
        return {
            'st_alojamiento': pd.to_numeric(d_aloj['Monto'], errors='coerce').fillna(0).sum(),
            'st_alimentacion': pd.to_numeric(d_alim['Monto'], errors='coerce').fillna(0).sum(),
            'st_otros': pd.to_numeric(d_ot['Monto'], errors='coerce').fillna(0).sum(),
        }

    subtotals = calc_subtotals(df_aloj, df_alim, df_otros)

    data_dict = {
        'nombre': nombre, 'rut': rut, 'centro_costo': centro_costo,
        'email_funcionario': user['email'], 'email_jefatura': email_jefe,
        'anticipo': anticipo, 'fecha_anticipo': data.get('fecha_anticipo', datetime.today()),
        'user_id': user.get('id'), 'user_sid': user.get('sid'),
        'df_comision': df_comision, 'df_alojamiento': df_aloj,
        'df_alimentacion': df_alim, 'df_otros': df_otros,
        'fecha_rendicion': datetime.now().strftime("%d/%m/%Y"),
        'receipt_photos': receipt_photos, 'moneda': moneda,
        'cuenta_id': data.get('cuenta_id'),
        **subtotals
    }

    total = sum(subtotals.values())
    if editing_rid:
        db_update_rendicion(int(editing_rid), data_dict)
        rid = int(editing_rid)
        flash(f"Rendición #{rid} actualizada.", "success")
    else:
        rid = db_submit_rendicion(data_dict)
        flash(f"Rendición #{rid} enviada exitosamente.", "success")

    smtp_conf = get_smtp_config()
    if smtp_conf and email_jefe:
        subject = f"Nueva Rendición de Gastos Pendiente - {nombre}"
        body = (
            f"Estimado/a Jefe/a,\n\n"
            f"Se ha ingresado una nueva rendición de gastos pendiente de su aprobación.\n\n"
            f"Funcionario: {nombre}\n"
            f"RUT: {rut}\n"
            f"Centro de Costo: {centro_costo}\n"
            f"Moneda: {moneda}\n"
            f"Monto Total: {format_curr(total, moneda)}\n\n"
            f"Por favor, ingrese al sistema para revisar y aprobar o rechazar la rendición.\n\n"
            f"Saludos cordiales,\nSistema de Rendiciones HGT"
        )
        send_hgt_email(smtp_conf, email_jefe, subject, body)

    return redirect(url_for('rendiciones.listar'))


@rendiciones_bp.route('/rendiciones/cuentas/<codigo_cc>', methods=['GET'])
@login_required
def cuentas_por_cc(codigo_cc):
    from app.database import db_get_centro_costo_cuentas
    codigos = db_get_centro_costo_cuentas(codigo_cc)
    if not codigos:
        return jsonify([])
    df = db_get_cuentas_contables()
    if not df.empty:
        df = df[df['codigo_cuenta'].isin(codigos)]
    result = df.to_dict('records') if not df.empty else []
    return jsonify(result)


@rendiciones_bp.route('/rendiciones/preview', methods=['POST'])
@login_required
@csrf_required
def preview():
    user = {
        'id': session['user_id'], 'nombre': session['fullname'],
        'email': session['email'], 'role': session['role'],
        'username': session['username'], 'sid': session.get('sid', ''),
    }
    data = request.form
    nombre = data.get('nombre', user['nombre'])
    rut = data.get('rut', '')
    moneda = data.get('moneda', 'CLP')
    centro_costo = data.get('centro_costo', '')
    email_jefe = data.get('email_jefe', '')
    anticipo = float(data.get('anticipo', 0))

    df_comision = _parse_df_from_form(data, 'comision', ['Traslado', 'Desde oficina', 'A localidad', 'Fecha Inicio', 'Fecha Término', 'Num_acompanantes', 'Nombres_acompanantes'])
    df_aloj = _parse_df_from_form(data, 'aloj', ['Detalle', 'Fecha', 'Doc', 'Monto'])
    df_alim = _parse_df_from_form(data, 'alim', ['Detalle', 'Tipo', 'Fecha', 'Doc', 'Monto'])
    df_otros = _parse_df_from_form(data, 'otros', ['Detalle', 'Fecha', 'Doc', 'Monto'])

    trayectos = db_get_trayectos_dict()
    df_vehicle = _calc_vehicle_costs(df_comision, trayectos, centro_costo)
    if not df_vehicle.empty:
        df_otros = pd.concat([df_otros, df_vehicle], ignore_index=True)

    def calc_subtotals(d_aloj, d_alim, d_ot):
        return {
            'st_alojamiento': pd.to_numeric(d_aloj['Monto'], errors='coerce').fillna(0).sum(),
            'st_alimentacion': pd.to_numeric(d_alim['Monto'], errors='coerce').fillna(0).sum(),
            'st_otros': pd.to_numeric(d_ot['Monto'], errors='coerce').fillna(0).sum(),
        }

    subtotals = calc_subtotals(df_aloj, df_alim, df_otros)

    data_dict = {
        'nombre': nombre, 'rut': rut, 'centro_costo': centro_costo,
        'email_funcionario': user['email'], 'email_jefatura': email_jefe,
        'anticipo': anticipo, 'fecha_anticipo': data.get('fecha_anticipo', datetime.today()),
        'user_id': user.get('id'), 'user_sid': user.get('sid'),
        'df_comision': df_comision, 'df_alojamiento': df_aloj,
        'df_alimentacion': df_alim, 'df_otros': df_otros,
        'fecha_rendicion': datetime.now().strftime("%d/%m/%Y"),
        'moneda': moneda,
        'cuenta_id': data.get('cuenta_id'),
        'receipt_photos': [f.read() for f in request.files.getlist('receipt_files') if f.filename],
        **subtotals
    }

    pdf_bytes = generate_hgt_pdf(data_dict)
    from flask import Response
    return Response(pdf_bytes, mimetype='application/pdf',
                    headers={'Content-Disposition': 'inline; filename=preview_rentabilidad.pdf'})


@rendiciones_bp.route('/rendiciones/<int:rid>/data', methods=['GET'])
@login_required
def get_rendicion_data(rid):
    data, pdf_fname, email_func, nombre_func, pdf_aprobado = db_get_rendicion(rid)
    if not data:
        return jsonify({'error': 'No encontrada'}), 404
    return jsonify({'data': serialize_data(data), 'pdf_filename': pdf_fname,
                    'email_funcionario': email_func, 'nombre': nombre_func})


@rendiciones_bp.route('/rendiciones/<int:rid>/pdf', methods=['GET'])
@login_required
def get_rendicion_pdf(rid):
    data, pdf_fname, _, _, pdf_aprobado = db_get_rendicion(rid)
    if not data:
        flash("Rendición no encontrada.", "error")
        return redirect(url_for('rendiciones.listar'))
    if pdf_aprobado:
        pdf_bytes = pdf_aprobado
    else:
        pdf_bytes = generate_hgt_pdf(data)
    from flask import Response
    return Response(pdf_bytes, mimetype='application/pdf',
                    headers={'Content-Disposition': f'inline; filename={pdf_fname or "rendicion.pdf"}'})


@rendiciones_bp.route('/rendiciones/ai-scan', methods=['POST'])
@login_required
@csrf_required
def ai_scan():
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    result = process_receipt_with_ai(api_key, f.read(), f.content_type or 'image/png')
    return jsonify(result)


def _parse_df_from_form(data, prefix, columns):
    rows = []
    i = 0
    while True:
        row = {}
        for col in columns:
            key = f"{prefix}_{i}_{col.replace(' ', '_')}"
            if key in data:
                row[col] = data.get(key, '')
        if not row:
            break
        if any(v for v in row.values()):
            rows.append(row)
        i += 1
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    for c in columns:
        if c not in df.columns:
            df[c] = ''
    df = df[columns]
    for date_col in ['Fecha', 'Fecha Inicio', 'Fecha Término']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    for num_col in ['Monto']:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors='coerce').fillna(0)
    return df


def _calc_vehicle_costs(df_comision, trayectos, codigo_cc=None):
    vehicle_cuenta_id = None
    vehicle_cuenta_code = None
    uber_cuenta_id = None
    uber_cuenta_code = None
    if codigo_cc:
        df_ctas = db_get_cuentas_contables()
        codigos = db_get_centro_costo_cuentas(codigo_cc)
        if codigos:
            df_ctas = df_ctas[df_ctas['codigo_cuenta'].isin(codigos)]
        for _, c in df_ctas.iterrows():
            cc_code = str(c.get('codigo_cuenta', ''))
            ca = str(c.get('concepto_amigable', '')).lower()
            d1 = str(c.get('detalle_1', '')).lower()
            if cc_code == '750521':
                if not vehicle_cuenta_id or 'movilizacion particular' in ca:
                    vehicle_cuenta_id = c['id']
                    vehicle_cuenta_code = cc_code
            elif 'movilizacion particular' in ca or 'servicio traslado' in d1:
                if not vehicle_cuenta_id:
                    vehicle_cuenta_id = c['id']
                    vehicle_cuenta_code = cc_code
            if 'uber' in ca:
                uber_cuenta_id = c['id']
                uber_cuenta_code = cc_code

    for idx, row in df_comision.iterrows():
        traslado = str(row.get('Traslado', '')).strip()
        if traslado == 'Vehículo propio':
            df_comision.at[idx, 'cuenta_id'] = vehicle_cuenta_id
            df_comision.at[idx, 'Cuenta Contable'] = vehicle_cuenta_code or ''
        elif 'Uber' in traslado:
            df_comision.at[idx, 'cuenta_id'] = uber_cuenta_id
            df_comision.at[idx, 'Cuenta Contable'] = uber_cuenta_code or ''

    vehicle_rows = []
    for _, row in df_comision.iterrows():
        traslado = str(row.get('Traslado', '')).strip()
        desde = str(row.get('Desde oficina', '')).strip()
        hasta = str(row.get('A localidad', '')).strip()
        fecha_inicio = row.get('Fecha Inicio', '')
        num_acomp_raw = row.get('Num_acompanantes', '')
        nombres_acomp = str(row.get('Nombres_acompanantes', '')).strip()

        if traslado != 'Vehículo propio':
            continue

        route_key = f"{desde} a {hasta}"
        if route_key not in trayectos:
            continue

        t = trayectos[route_key]
        km_base = float(t[0])
        mult_peaje = int(t[1])
        monto_peaje_base = float(t[2])
        factor = float(t[3]) if len(t) > 3 and t[3] else 1.0

        base_monto = km_base * 2 * factor
        fecha_str = fmt_date(fecha_inicio) if hasattr(fecha_inicio, 'strftime') else str(fecha_inicio) if fecha_inicio else datetime.now().strftime("%Y-%m-%d")

        vehicle_rows.append({
            'Detalle': f"Traslado {route_key} ({int(km_base * 2)} km)",
            'Fecha': fecha_str,
            'Doc': '',
            'Monto': base_monto,
            'cuenta_id': vehicle_cuenta_id,
            'Cuenta Contable': vehicle_cuenta_code or ''
        })

        if monto_peaje_base > 0 and mult_peaje > 0:
            v_peaje_total = monto_peaje_base * mult_peaje
            vehicle_rows.append({
                'Detalle': f"Peajes {route_key} ({mult_peaje} peajes x ${int(monto_peaje_base)})",
                'Fecha': fecha_str,
                'Doc': '',
                'Monto': v_peaje_total,
                'cuenta_id': vehicle_cuenta_id,
                'Cuenta Contable': vehicle_cuenta_code or ''
            })

        n_acomp = 0
        try:
            n_acomp = int(float(num_acomp_raw))
        except (ValueError, TypeError):
            pass

        if n_acomp > 0:
            monto_acomp = base_monto * 0.2 * n_acomp
            label = nombres_acomp if nombres_acomp else f"{n_acomp} personas"
            if len(label) > 40:
                label = label[:37] + '...'
            vehicle_rows.append({
                'Detalle': f"Acompañantes {route_key}: {label} (20% x{n_acomp})",
                'Fecha': fecha_str,
                'Doc': '',
                'Monto': monto_acomp,
                'cuenta_id': vehicle_cuenta_id,
                'Cuenta Contable': vehicle_cuenta_code or ''
            })

    if vehicle_rows:
        df_vehicle = pd.DataFrame(vehicle_rows)
        for c in ['Detalle', 'Fecha', 'Doc', 'Monto', 'cuenta_id', 'Cuenta Contable']:
            if c not in df_vehicle.columns:
                df_vehicle[c] = ''
        return df_vehicle
    return pd.DataFrame(columns=['Detalle', 'Fecha', 'Doc', 'Monto', 'cuenta_id', 'Cuenta Contable'])


def fmt_date(val):
    if hasattr(val, 'strftime'):
        try:
            if pd.isnull(val):
                return ''
        except Exception:
            pass
        return val.strftime('%d/%m/%Y')
    return str(val) if val else ''
