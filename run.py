import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, request, session
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')

    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        raise RuntimeError("SECRET_KEY no está configurada.")
    app.secret_key = secret_key

    secure_cookie = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    httponly_cookie = os.getenv('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    samesite_cookie = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    session_lifetime = int(os.getenv('PERMANENT_SESSION_LIFETIME', '3600'))
    session_type = os.getenv('SESSION_TYPE', 'filesystem')
    session_permanent = os.getenv('SESSION_PERMANENT', 'True').lower() == 'true'
    session_file_dir = os.getenv('SESSION_FILE_DIR', os.path.join(app.instance_path, 'flask_session'))

    app.config.update(
        SESSION_COOKIE_SECURE=secure_cookie,
        SESSION_COOKIE_HTTPONLY=httponly_cookie,
        SESSION_COOKIE_SAMESITE=samesite_cookie,
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=session_lifetime),
        SESSION_TYPE=session_type,
        SESSION_PERMANENT=session_permanent,
    )

    if session_type != 'null':
        if session_type == 'filesystem':
            app.config.update(
                SESSION_FILE_DIR=session_file_dir,
                SESSION_FILE_THRESHOLD=500,
            )
        Session(app)

    from app.utils.csrf import inject_csrf_token
    app.context_processor(inject_csrf_token)

    @app.context_processor
    def inject_now():
        return {'now': datetime.now}

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    @app.before_request
    def update_activity():
        if 'user_id' in session:
            session['last_activity'] = time.time()

    from app.routes.auth import auth_bp
    from app.routes.rendiciones import rendiciones_bp
    from app.routes.aprobaciones import aprobaciones_bp
    from app.routes.encargado import encargado_bp
    from app.routes.usuarios import usuarios_bp
    from app.routes.mantencion import mantencion_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(rendiciones_bp)
    app.register_blueprint(aprobaciones_bp)
    app.register_blueprint(encargado_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(mantencion_bp)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
