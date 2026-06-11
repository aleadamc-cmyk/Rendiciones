from functools import wraps
from flask import session, redirect, url_for, flash, jsonify, request


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Unauthorized'}), 401
            flash("Debe iniciar sesión para acceder.", "error")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def permission_required(perm):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            perms = session.get('permissions', {})
            if not perms.get(perm):
                if request.is_json:
                    return jsonify({'error': 'Forbidden'}), 403
                flash("No tiene permisos para esta acción.", "error")
                return redirect(url_for('rendiciones.listar'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


ALLOWED_EXTENSIONS = {
    'pdf': [b'%PDF'],
    'xlsx': [b'PK\x03\x04'],
    'xls': [b'\xd0\xcf\x11\xe0', b'PK\x03\x04'],
}

ALLOWED_MIMETYPES = {
    'pdf': ['application/pdf'],
    'xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
             'application/octet-stream'],
    'xls': ['application/vnd.ms-excel', 'application/octet-stream'],
}
