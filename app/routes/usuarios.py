import re
import hashlib
from datetime import datetime
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash
from app.database import (
    db_get_all_visible_users, db_register_user, db_delete_user, db_update_user_full,
    db_update_password, db_get_jefaturas, db_get_terminales, db_get_centros_costos,
    db_get_usuario_centros_costos, db_get_cuentas_contables, db_get_usuario_cc_cuentas,
    db_get_user_by_id, is_super_user, SUPER_USERNAME,
    db_get_centro_costo_cuentas, db_get_all_centro_costo_cuentas
)
from app.utils.security import login_required, permission_required
from app.utils.csrf import csrf_required
from app.utils.ai_service import process_id_card_with_ai
import os

usuarios_bp = Blueprint('usuarios', __name__)


@usuarios_bp.route('/usuarios', methods=['GET'])
@login_required
def listar():
    current_user = {'id': session.get('user_id'), 'nombre': session.get('fullname'),
                    'email': session.get('email'), 'username': session.get('username'),
                    'role': session.get('role')}
    df_users = db_get_all_visible_users(current_user)
    users_list = df_users.to_dict('records') if not df_users.empty else []
    jefaturas = db_get_jefaturas().to_dict('records') if not db_get_jefaturas().empty else []
    terminales = db_get_terminales().to_dict('records') if not db_get_terminales().empty else []
    centros_costo = db_get_centros_costos().to_dict('records') if not db_get_centros_costos().empty else []
    cuentas = db_get_cuentas_contables().to_dict('records') if not db_get_cuentas_contables().empty else []
    is_super = is_super_user(current_user)

    df_cc_cuentas = db_get_all_centro_costo_cuentas()
    cc_cuentas_map = {}
    if not df_cc_cuentas.empty:
        for _, row in df_cc_cuentas.iterrows():
            cc_cuentas_map.setdefault(row['codigo_cc'], []).append(row['codigo_cuenta'])

    return render_template('usuarios.html', users=users_list, jefaturas=jefaturas,
                           terminales=terminales, centros_costo=centros_costo,
                           cuentas=cuentas, is_super=is_super,
                           user=current_user, SUPER_USERNAME=SUPER_USERNAME,
                           cc_cuentas_map=cc_cuentas_map)


@usuarios_bp.route('/usuarios/crear', methods=['POST'])
@login_required
@csrf_required
def crear():
    current_user = {'username': session.get('username'), 'nombre': session.get('fullname')}
    nombre = request.form.get('nombre', '').strip()
    email = request.form.get('email', '').strip()
    rut = request.form.get('rut', '').strip()
    password = request.form.get('password', '').strip()
    roles_list = request.form.getlist('roles')
    roles_str = ','.join(roles_list) if roles_list else 'usuario'
    email_jefatura = request.form.get('email_jefatura', '') or None
    terminal_asignado = request.form.get('terminal_asignado', '') or None
    empresa = request.form.get('empresa', '').strip() or None
    cargo = request.form.get('cargo', '').strip() or None
    centros_costo = request.form.getlist('centros_costo')
    cc_cuentas = {}
    for cc in centros_costo:
        cuentas_for_cc = request.form.getlist(f'cc_cuentas[{cc}]')
        if cuentas_for_cc:
            cc_cuentas[cc] = cuentas_for_cc

    if not nombre or not email or not password:
        flash("Nombre, Email y Contraseña son obligatorios.", "error")
        return redirect(url_for('usuarios.listar'))
    if rut and not re.match(r'^[\d\-kK]+$', rut):
        flash("El RUT solo puede contener números, guión (-) y la letra K.", "error")
        return redirect(url_for('usuarios.listar'))

    if 'super_admin' in roles_list and not is_super_user(current_user):
        flash("Solo el Super admin puede asignar super_admin.", "error")
        return redirect(url_for('usuarios.listar'))

    res = db_register_user(nombre, email, password, roles_str, rut, '',
                           email_jefatura=email_jefatura,
                           terminal_asignado=terminal_asignado,
                           centros_costo=centros_costo if centros_costo else None,
                           cc_cuentas=cc_cuentas if cc_cuentas else None,
                           empresa=empresa, cargo=cargo)
    if res is True:
        flash(f"Usuario {nombre} creado con éxito.", "success")
    else:
        flash(f"Error: {res}", "error")
    return redirect(url_for('usuarios.listar'))


@usuarios_bp.route('/usuarios/<int:uid>/editar', methods=['POST'])
@login_required
@permission_required('usuarios')
@csrf_required
def editar(uid):
    current_user = {'username': session.get('username')}
    nombre = request.form.get('nombre', '').strip()
    email = request.form.get('email', '').strip()
    rut = request.form.get('rut', '').strip()
    roles_list = request.form.getlist('roles')
    roles_str = ','.join(roles_list) if roles_list else ''
    email_jefatura = request.form.get('email_jefatura', '') or None
    terminal_asignado = request.form.get('terminal_asignado', '') or None
    empresa = request.form.get('empresa', '').strip() or None
    cargo = request.form.get('cargo', '').strip() or None
    centros_costo = request.form.getlist('centros_costo')
    cc_cuentas = {}
    for cc in centros_costo:
        cuentas_for_cc = request.form.getlist(f'cc_cuentas[{cc}]')
        if cuentas_for_cc:
            cc_cuentas[cc] = cuentas_for_cc

    if rut and not re.match(r'^[\d\-kK]+$', rut):
        flash("El RUT solo puede contener números, guión (-) y la letra K.", "error")
        return redirect(url_for('usuarios.listar'))

    try:
        res = db_update_user_full(uid, nombre, email, rut, '', roles_str,
                                  email_jefatura=email_jefatura,
                                  terminal_asignado=terminal_asignado,
                                  centros_costo=centros_costo if centros_costo else None,
                                  cc_cuentas=cc_cuentas if cc_cuentas else None,
                                  empresa=empresa, cargo=cargo)
        if res is True:
            if email == session.get('email'):
                session['fullname'] = nombre
                session['email'] = email
            flash("Usuario actualizado.", "success")
        else:
            flash(f"Error: {res}", "error")
    except PermissionError as e:
        flash(str(e), "error")
    return redirect(url_for('usuarios.listar'))


@usuarios_bp.route('/usuarios/<int:uid>/password', methods=['POST'])
@login_required
@permission_required('usuarios')
@csrf_required
def cambiar_password(uid):
    new_pw = request.form.get('password', '').strip()
    if not new_pw:
        flash("Ingrese una contraseña.", "error")
        return redirect(url_for('usuarios.listar'))
    try:
        db_update_password(uid, generate_password_hash(new_pw))
        flash("Contraseña actualizada.", "success")
    except PermissionError as e:
        flash(str(e), "error")
    return redirect(url_for('usuarios.listar'))


@usuarios_bp.route('/usuarios/<int:uid>/eliminar', methods=['POST'])
@login_required
@permission_required('usuarios')
@csrf_required
def eliminar(uid):
    if uid == session.get('user_id'):
        flash("No puedes eliminar tu propio usuario.", "error")
        return redirect(url_for('usuarios.listar'))
    u = db_get_user_by_id(uid)
    if not u:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for('usuarios.listar'))
    try:
        db_delete_user(uid, u['email'])
        flash("Usuario eliminado.", "success")
    except PermissionError as e:
        flash(str(e), "error")
    return redirect(url_for('usuarios.listar'))


@usuarios_bp.route('/usuarios/ocr-id', methods=['POST'])
@login_required
@csrf_required
def ocr_id():
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    result = process_id_card_with_ai(api_key, f.read(), f.content_type or 'image/png')
    return jsonify(result)


@usuarios_bp.route('/usuarios/<int:uid>/data', methods=['GET'])
@login_required
def user_data(uid):
    u = db_get_user_by_id(uid)
    if not u:
        return jsonify({'error': 'Not found'}), 404
    cc_list = db_get_usuario_centros_costos(uid)
    cc_ctas = db_get_usuario_cc_cuentas(uid)
    return jsonify({'user': u, 'centros_costo': cc_list, 'cc_cuentas': cc_ctas})
