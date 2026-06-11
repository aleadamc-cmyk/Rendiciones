from flask import Blueprint, render_template, request, session, redirect, url_for, flash
import pandas as pd
from app.database import (
    db_get_trayectos, db_save_trayectos, db_get_jefaturas, db_save_jefaturas,
    db_get_terminales, db_save_terminales, db_get_cuentas_contables, db_save_cuentas_contables,
    db_get_centros_costos, db_save_centros_costos, db_get_centro_costo_cuentas,
    db_set_centro_costo_cuentas, db_get_topes_usd, db_save_topes_usd, _get_conn
)
from app.utils.security import login_required
from app.utils.csrf import csrf_required

mantencion_bp = Blueprint('mantencion', __name__)


@mantencion_bp.route('/mantencion', methods=['GET'])
@login_required
def panel():
    trayectos = db_get_trayectos().to_dict('records') if not db_get_trayectos().empty else []
    jefaturas = db_get_jefaturas().to_dict('records') if not db_get_jefaturas().empty else []
    terminales = db_get_terminales().to_dict('records') if not db_get_terminales().empty else []
    cuentas = db_get_cuentas_contables().to_dict('records') if not db_get_cuentas_contables().empty else []
    centros_costos = db_get_centros_costos().to_dict('records') if not db_get_centros_costos().empty else []
    topes_usd = db_get_topes_usd().to_dict('records') if not db_get_topes_usd().empty else []
    df_cc = db_get_centros_costos()
    cc_options = df_cc['codigo_cc'].tolist() if not df_cc.empty else []
    
    return render_template('mantencion.html', trayectos=trayectos, jefaturas=jefaturas,
                           terminales=terminales, cuentas=cuentas,
                           centros_costos=centros_costos, topes_usd=topes_usd,
                           cc_options=cc_options)


@mantencion_bp.route('/mantencion/trayectos', methods=['POST'])
@login_required
@csrf_required
def guardar_trayectos():
    df = _parse_df_from_form(request.form, 'trayecto',
                              ['id', 'origen', 'destino', 'km_base', 'multiplicador_peaje',
                               'monto_peaje_base', 'factor', 'alimentacion',
                               'alimentacion_desayuno', 'alimentacion_almuerzo', 'alimentacion_cena'])
    if not df.empty:
        df = df.drop(columns=['id'], errors='ignore')
        res = db_save_trayectos(df)
        if res is True:
            flash("Trayectos actualizados.", "success")
        else:
            flash(f"Error: {res}", "error")
    return redirect(url_for('mantencion.panel'))


@mantencion_bp.route('/mantencion/jefaturas', methods=['POST'])
@login_required
@csrf_required
def guardar_jefaturas():
    df = _parse_df_from_form(request.form, 'jefatura', ['id', 'nombre', 'email'])
    if not df.empty:
        df = df.drop(columns=['id'], errors='ignore')
        res = db_save_jefaturas(df)
        if res is True:
            flash("Jefaturas actualizadas.", "success")
        else:
            flash(f"Error: {res}", "error")
    return redirect(url_for('mantencion.panel'))


@mantencion_bp.route('/mantencion/terminales', methods=['POST'])
@login_required
@csrf_required
def guardar_terminales():
    df = _parse_df_from_form(request.form, 'terminal', ['id', 'nombre', 'codigo_interno', 'activo'])
    if not df.empty:
        df = df.drop(columns=['id'], errors='ignore')
        res = db_save_terminales(df)
        if res is True:
            flash("Terminales actualizados.", "success")
        else:
            flash(f"Error: {res}", "error")
    return redirect(url_for('mantencion.panel'))


@mantencion_bp.route('/mantencion/cuentas', methods=['POST'])
@login_required
@csrf_required
def guardar_cuentas():
    df = _parse_df_from_form(request.form, 'cuenta', ['id', 'codigo_cuenta', 'detalle_1', 'concepto_amigable'])
    if not df.empty:
        df = df.drop(columns=['id'], errors='ignore')
        res = db_save_cuentas_contables(df)
        if res is True:
            flash("Cuentas contables actualizadas.", "success")
        else:
            flash(f"Error: {res}", "error")
    return redirect(url_for('mantencion.panel'))


@mantencion_bp.route('/mantencion/centros-costos', methods=['POST'])
@login_required
@csrf_required
def guardar_centros_costos():
    df = _parse_df_from_form(request.form, 'cc', ['codigo_cc', 'detalle_cc'])
    if not df.empty:
        res = db_save_centros_costos(df)
        if res is True:
            flash("Centros de costo actualizados.", "success")
        else:
            flash(f"Error: {res}", "error")
    return redirect(url_for('mantencion.panel'))


@mantencion_bp.route('/mantencion/cc-cuentas', methods=['POST'])
@login_required
@csrf_required
def guardar_cc_cuentas():
    codigo_cc = request.form.get('codigo_cc', '')
    cuentas = request.form.getlist('cuentas')
    if codigo_cc:
        db_set_centro_costo_cuentas(codigo_cc, cuentas)
        flash(f"Asignación actualizada para {codigo_cc}.", "success")
    return redirect(url_for('mantencion.panel'))


@mantencion_bp.route('/mantencion/topes-usd', methods=['POST'])
@login_required
@csrf_required
def guardar_topes_usd():
    df = _parse_df_from_form(request.form, 'tope', ['id', 'concepto', 'tope_usd'])
    if not df.empty:
        df = df.drop(columns=['id'], errors='ignore')
        res = db_save_topes_usd(df)
        if res is True:
            flash("Topes USD actualizados.", "success")
        else:
            flash(f"Error: {res}", "error")
    return redirect(url_for('mantencion.panel'))


@mantencion_bp.route('/mantencion/terminal/agregar', methods=['POST'])
@login_required
@csrf_required
def agregar_terminal():
    nombre = request.form.get('nombre', '').strip()
    codigo = request.form.get('codigo_interno', '').strip()
    activo = request.form.get('activo', '1') == '1'
    if nombre and codigo:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO terminales (nombre, codigo_interno, activo) VALUES (?, ?, ?)",
                  (nombre, codigo, int(activo)))
        conn.commit()
        conn.close()
        flash("Terminal agregado.", "success")
    return redirect(url_for('mantencion.panel'))


@mantencion_bp.route('/mantencion/cuenta/agregar', methods=['POST'])
@login_required
@csrf_required
def agregar_cuenta():
    codigo = request.form.get('codigo_cuenta', '').strip()
    detalle = request.form.get('detalle_1', '').strip()
    concepto = request.form.get('concepto_amigable', '').strip()
    if codigo and detalle and concepto:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO cuentas_contables (codigo_cuenta, detalle_1, concepto_amigable) VALUES (?, ?, ?)",
                  (codigo, detalle, concepto))
        conn.commit()
        conn.close()
        flash("Cuenta contable agregada.", "success")
    return redirect(url_for('mantencion.panel'))


@mantencion_bp.route('/mantencion/centro-costo/agregar', methods=['POST'])
@login_required
@csrf_required
def agregar_centro_costo():
    codigo = request.form.get('codigo_cc', '').strip()
    detalle = request.form.get('detalle_cc', '').strip()
    if codigo and detalle:
        conn = _get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO centros_costos (codigo_cc, detalle_cc) VALUES (?, ?)", (codigo, detalle))
        conn.commit()
        conn.close()
        flash("Centro de costo agregado.", "success")
    return redirect(url_for('mantencion.panel'))


def _parse_df_from_form(form_data, prefix, columns):
    rows = []
    i = 0
    while True:
        row = {}
        has_data = False
        for col in columns:
            key = f"{prefix}_{i}_{col.replace(' ', '_')}"
            val = form_data.get(key, '')
            if val:
                has_data = True
            row[col] = val
        if not has_data:
            break
        rows.append(row)
        i += 1
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = ''
    df = df[columns]
    for num_col in ['km_base', 'multiplicador_peaje', 'monto_peaje_base', 'factor',
                     'alimentacion', 'alimentacion_desayuno', 'alimentacion_almuerzo',
                     'alimentacion_cena', 'tope_usd', 'activo']:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors='coerce').fillna(0)
    return df
