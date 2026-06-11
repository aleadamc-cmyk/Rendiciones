import time
import re
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from app.database import db_verify_user, init_db
from app.utils.csrf import generate_csrf_token, validate_csrf_token, csrf_required

auth_bp = Blueprint('auth', __name__)


def validate_username(username):
    if not username or len(username) > 50:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_.@-]+$', username))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    init_db()
    csrf_token_val = generate_csrf_token()

    if request.method == 'POST':
        token = request.form.get('csrf_token', '')
        if not validate_csrf_token(token):
            flash("Credenciales inválidas", "error")
            return render_template('login.html', csrf_token=generate_csrf_token())

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not validate_username(username):
            flash("Credenciales inválidas", "error")
            return render_template('login.html', csrf_token=generate_csrf_token())

        user = db_verify_user(username, password)
        if user:
            session.clear()
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['fullname'] = user['nombre']
            session['email'] = user['email']
            session['rut'] = user['rut']
            session['centro_costo'] = user['cc']
            session['last_activity'] = time.time()
            session['login_time'] = time.time()

            roles = [r.strip() for r in user['role'].split(',') if r.strip()]
            session['permissions'] = {
                'rendiciones': 'usuario' in roles,
                'aprobaciones': 'jefatura' in roles or 'admin' in roles,
                'encargado': 'encargado' in roles or 'admin' in roles,
                'usuarios': 'admin' in roles,
                'mantencion': 'admin' in roles,
                'is_super': user.get('username') == 'Super' or user.get('nombre') == 'Super',
            }
            return redirect(url_for('rendiciones.listar'))
        else:
            time.sleep(1)
            flash("Credenciales inválidas", "error")

    return render_template('login.html', csrf_token=csrf_token_val)


@auth_bp.route('/logout', methods=['POST'])
@csrf_required
def logout():
    session.clear()
    response = redirect(url_for('auth.login'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
