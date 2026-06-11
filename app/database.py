import os
import json
import base64
import hashlib
import re
import sqlite3
from datetime import datetime
from io import BytesIO
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "rendiciones_hgt.db")
LOGO_PATH = os.path.join(BASE_DIR, "logo_hgt.png")

SUPER_USERNAME = "Super"


def _get_conn():
    return sqlite3.connect(DB_PATH, timeout=20)


def _exec_query(query, params=None, fetch=None):
    conn = _get_conn()
    c = conn.cursor()
    try:
        if params:
            c.execute(query, params)
        else:
            c.execute(query)
        if fetch == 'one':
            result = c.fetchone()
        elif fetch == 'all':
            result = c.fetchall()
        else:
            result = None
        conn.commit()
        return result
    finally:
        conn.close()


def _exec_df_query(query, params=None):
    conn = _get_conn()
    try:
        return pd.read_sql_query(query, conn, params=params if params else None)
    finally:
        conn.close()


def _df_to_json(df):
    df2 = df.copy()
    for col in df2.select_dtypes(include=['datetime64[ns]', 'datetime64[ns, UTC]']).columns:
        df2[col] = df2[col].apply(lambda v: v.strftime('%Y-%m-%d') if pd.notna(v) else '')
    return df2.to_json()


def _read_df(json_str, date_cols=None, expected_cols=None):
    try:
        df = pd.read_json(BytesIO(json_str.encode()))
        if expected_cols:
            for c in expected_cols:
                if c not in df.columns:
                    df[c] = ""
            df = df[expected_cols]
        if date_cols:
            for col in date_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame(columns=expected_cols) if expected_cols else pd.DataFrame()


def serialize_data(data):
    return json.dumps({
        'nombre': data['nombre'],
        'rut': data['rut'],
        'email_funcionario': data.get('email_funcionario', ''),
        'email_jefatura': data.get('email_jefatura', ''),
        'user_id': data.get('user_id'),
        'user_sid': data.get('user_sid'),
        'jefe_id': data.get('jefe_id'),
        'jefe_sid': data.get('jefe_sid'),
        'jefe_rut': data.get('jefe_rut', ''),
        'jefe_nombre': data.get('jefe_nombre', ''),
        'fecha_aprobacion': data.get('fecha_aprobacion', ''),
        'centro_costo': data['centro_costo'],
        'moneda': data.get('moneda', 'CLP'),
        'anticipo': float(data['anticipo']),
        'fecha_anticipo': (data['fecha_anticipo'].isoformat()
                           if hasattr(data['fecha_anticipo'], 'isoformat')
                           else str(data['fecha_anticipo'])),
        'df_comision': _df_to_json(data['df_comision']),
        'df_alojamiento': _df_to_json(data['df_alojamiento']),
        'df_alimentacion': _df_to_json(data['df_alimentacion']),
        'df_otros': _df_to_json(data['df_otros']),
        'st_alojamiento': float(data['st_alojamiento']),
        'st_alimentacion': float(data['st_alimentacion']),
        'st_otros': float(data['st_otros']),
        'fecha_rendicion': data['fecha_rendicion'],
        'receipt_photos': [base64.b64encode(p).decode()
                           for p in data.get('receipt_photos', [])],
    })


def deserialize_data(json_str):
    sd = json.loads(json_str)
    try:
        fa = datetime.fromisoformat(sd.get('fecha_anticipo', '')).date()
    except Exception:
        fa = datetime.today().date()
    return {
        'nombre': sd['nombre'],
        'rut': sd['rut'],
        'email_funcionario': sd.get('email_funcionario', ''),
        'email_jefatura': sd.get('email_jefatura', ''),
        'user_id': sd.get('user_id'),
        'user_sid': sd.get('user_sid'),
        'jefe_id': sd.get('jefe_id'),
        'jefe_sid': sd.get('jefe_sid'),
        'jefe_rut': sd.get('jefe_rut', ''),
        'jefe_nombre': sd.get('jefe_nombre', ''),
        'fecha_aprobacion': sd.get('fecha_aprobacion', ''),
        'centro_costo': sd['centro_costo'],
        'moneda': sd.get('moneda', 'CLP'),
        'anticipo': sd['anticipo'],
        'fecha_anticipo': fa,
        'df_comision': _read_df(sd['df_comision'], ['Fecha Inicio', 'Fecha Término'],
                                ["Traslado", "Cuenta Contable", "Desde oficina", "A localidad", "Fecha Inicio", "Fecha Término"]),
        'df_alojamiento': _read_df(sd['df_alojamiento'], ['Fecha'],
                                   ["Detalle", "Fecha", "Doc", "Monto"]),
        'df_alimentacion': _read_df(sd['df_alimentacion'], ['Fecha'],
                                    ["Detalle", "Tipo", "Fecha", "Doc", "Monto"]),
        'df_otros': _read_df(sd['df_otros'], ['Fecha'],
                             ["Detalle", "Fecha", "Doc", "Monto"]),
        'st_alojamiento': sd['st_alojamiento'],
        'st_alimentacion': sd['st_alimentacion'],
        'st_otros': sd['st_otros'],
        'fecha_rendicion': sd['fecha_rendicion'],
        'receipt_photos': [base64.b64decode(p) for p in sd.get('receipt_photos', [])],
    }


def format_curr(val, moneda='CLP'):
    try:
        v = float(val)
        if moneda == 'USD':
            return f"US$ {v:,.2f}"
        return f"$ {v:,.0f}".replace(",", ".")
    except Exception:
        return "US$ 0.00" if moneda == 'USD' else "$ 0"


def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS rendiciones (
            id_rut TEXT PRIMARY KEY, nombre TEXT, fecha TEXT,
            mes INTEGER, año INTEGER, centro_costo TEXT, total REAL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS rendiciones_workflow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT, rut TEXT, email_funcionario TEXT,
            email_jefatura TEXT, centro_costo TEXT, fecha TEXT, 
            mes INTEGER, año INTEGER, total REAL, status TEXT DEFAULT 'pendiente',
            pdf_filename TEXT, data_json TEXT, pdf_aprobado BLOB,
            comentario_encargado TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_aprobacion TIMESTAMP,
            fecha_procesado_encargado TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE, password TEXT, role TEXT,
            nombre TEXT, email TEXT, rut TEXT, centro_costo TEXT,
            firma_bytes BLOB, email_jefatura TEXT, sid TEXT
        )
    """)
    for col in ['firma_bytes', 'email_jefatura', 'sid', 'terminal_asignado', 'empresa', 'cargo']:
        try:
            c.execute(f"ALTER TABLE usuarios ADD COLUMN {col} TEXT")
        except Exception:
            pass
    c.execute("""
        CREATE TABLE IF NOT EXISTS trayectos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origen TEXT, destino TEXT, km_base REAL, 
            multiplicador_peaje INTEGER, monto_peaje_base INTEGER,
            factor REAL DEFAULT 1.0,
            colacion REAL DEFAULT 0
        )
    """)
    for col in ['colacion', 'alimentacion', 'alimentacion_desayuno', 'alimentacion_almuerzo', 'alimentacion_cena']:
        try:
            c.execute(f"ALTER TABLE trayectos ADD COLUMN {col} REAL DEFAULT 0")
        except Exception:
            pass
    c.execute("""
        CREATE TABLE IF NOT EXISTS jefaturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT, email TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS terminales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            codigo_interno TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1
        )
    """)
    c.execute("SELECT count(*) FROM terminales")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO terminales (nombre, codigo_interno, activo) VALUES (?, ?, ?)", [
            ("Placilla (PLA)", "PLA", 1),
            ("San Antonio (SAI)", "SAI", 1),
            ("SCL Renca", "RENCA", 1),
        ])
    c.execute("DROP TABLE IF EXISTS cuentas_contables")
    c.execute("""
        CREATE TABLE cuentas_contables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_cuenta TEXT NOT NULL,
            detalle_1 TEXT NOT NULL,
            concepto_amigable TEXT NOT NULL
        )
    """)
    seed_cuentas = [
        ("500504", "Art Aseo y Abarrotes", "Churrascos / cenas / desayunos"),
        ("750504", "Abarrores", "Almuerzo gerencia"),
        ("500380", "Insumos Operativos", "Articulos Ferreteria"),
        ("500521", "Serv Traslado", "Traslado UBER"),
        ("500520", "Gastos Viaje", "Alojamiento"),
        ("750521", "Servicio Traslado", "Movilización particular + peajes"),
        ("500521", "Servicio Traslado", "Movilización particular + peajes"),
        ("500520", "Gastos Viaje", "Actividad planes de mejora"),
        ("500382", "Consumo Herramienta", "Herramienta"),
        ("500504", "Art Aseo y Abarrotes", "Huevos de pascua"),
        ("500569", "Reparaciones y contingencias", "Enchufe"),
        ("750520", "Gastos Viaje", "Alimentación"),
        ("500506", "Insumo Oficina", "Timbres"),
        ("500362", "Vehiculos Propios", "SOAP"),
        ("500362", "Vehiculos Propios", "Permiso Circulación"),
        ("500504", "Art Aseo y Abarrotes", "Tazas vasos cucharas galletas"),
        ("500504", "Art Aseo y Abarrotes", "Comida Perro"),
        ("500568", "Mantenimiento Infraestructura", "Materiales DEPOT"),
        ("750521", "Servicio Traslado", "Movilización particular"),
        ("500416", "Seguridad y prevencion", "BIDON DE AGUA"),
        ("750504", "Abarrores", "Galletas y jugos dia de la seguridad"),
        ("750535", "Otros gastos legales", "Boleta notaria finiquito"),
        ("750521", "Servicio Traslado", "Uso vehiculo + peaje"),
        ("750520", "Gastos Viaje", "Almuerzo viaje a scl y sai"),
        ("500387", "Gas grua horquilla", "Cilindro gas"),
        ("500416", "Seguridad y prevencion", "Auditoria SSO"),
    ]
    c.executemany("INSERT INTO cuentas_contables (codigo_cuenta, detalle_1, concepto_amigable) VALUES (?, ?, ?)", seed_cuentas)
    c.execute("""
        CREATE TABLE IF NOT EXISTS centros_costos (
            codigo_cc TEXT PRIMARY KEY,
            detalle_cc TEXT NOT NULL
        )
    """)
    c.execute("DELETE FROM centros_costos")
    seed_cc = [
        ("SMZSW1900", "WM COSTO FIJO SCL"),
        ("SMLG00210", "GAV OPERACIONES"),
        ("SMAS02002", "Manipuleo"),
        ("SMLG00295", "GAV HSE"),
        ("SMZNW1900", "WM COSTO FIJO SAI"),
        ("SMLG00265", "GAV COMERCIAL"),
        ("SMAN08022", "EQUIPOS SAN ANTONIO"),
        ("SMAI08022", "EQUIPOS IQUIQUE"),
        ("SMZPW1900", "COSTO FIJO PMC"),
        ("SMAS02000", "CF DEPOT SCL"),
        ("SMLG00275", "GAV RRHH"),
        ("SMLG00215", "GAV EQUIPOS"),
        ("SMAV08022", "EQUIPOS SANTIAGO"),
        ("SMAV02006", "MAESTRANZA Y LAVADO"),
    ]
    c.executemany("INSERT INTO centros_costos (codigo_cc, detalle_cc) VALUES (?, ?)", seed_cc)
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuario_centro_costo (
            usuario_id INTEGER,
            codigo_cc TEXT,
            PRIMARY KEY (usuario_id, codigo_cc)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS centro_costo_cuenta (
            codigo_cc TEXT,
            codigo_cuenta TEXT,
            PRIMARY KEY (codigo_cc, codigo_cuenta)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuario_centro_costo_cuenta (
            usuario_id INTEGER,
            codigo_cc TEXT,
            codigo_cuenta TEXT,
            PRIMARY KEY (usuario_id, codigo_cc, codigo_cuenta)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS rendiciones_detalles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rendicion_id INTEGER NOT NULL,
            colaborador_id INTEGER NOT NULL,
            centro_costo_codigo TEXT NOT NULL,
            cuenta_id INTEGER NOT NULL,
            ruta_id INTEGER,
            es_ida_vuelta INTEGER DEFAULT 0,
            lleva_acompanante INTEGER DEFAULT 0,
            detalle_gasto TEXT NOT NULL,
            monto_total REAL NOT NULL,
            fecha_gasto TEXT NOT NULL,
            FOREIGN KEY (rendicion_id) REFERENCES rendiciones_workflow(id),
            FOREIGN KEY (colaborador_id) REFERENCES usuarios(id),
            FOREIGN KEY (centro_costo_codigo) REFERENCES centros_costos(codigo_cc),
            FOREIGN KEY (cuenta_id) REFERENCES cuentas_contables(id)
        )
    """)
    c.execute("SELECT count(*) FROM usuarios WHERE username='admin'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios (username, password, role, nombre) VALUES (?, ?, ?, ?)",
                  ('admin', generate_password_hash('123'), 'admin', 'Administrador Sistema'))
    c.execute("SELECT count(*) FROM usuarios WHERE username='Super'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios (username, password, role, nombre, email, rut, centro_costo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  ('Super', generate_password_hash('1521.Azteca'), 'super_admin', 'Super', 'super@hgt.com', '', ''))
    c.execute("SELECT count(*) FROM trayectos")
    if c.fetchone()[0] == 0:
        seeds = [
            ("Placilla", "Renca", 105, 4, 2700),
            ("Renca", "Placilla", 105, 4, 2700),
            ("Placilla", "San Antonio", 78, 2, 0),
            ("San Antonio", "Placilla", 78, 2, 0),
            ("Renca", "San Antonio", 121, 2, 0),
            ("San Antonio", "Renca", 121, 2, 0),
            ("Renca", "Santiago", 121, 0, 0),
            ("Santiago", "Renca", 121, 0, 0),
        ]
        c.executemany("INSERT INTO trayectos (origen, destino, km_base, multiplicador_peaje, monto_peaje_base) VALUES (?, ?, ?, ?, ?)", seeds)
    c.execute("""
        CREATE TABLE IF NOT EXISTS topes_usd (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto TEXT NOT NULL UNIQUE,
            tope_usd REAL NOT NULL DEFAULT 0
        )
    """)
    c.execute("SELECT count(*) FROM topes_usd")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO topes_usd (concepto, tope_usd) VALUES (?, ?)",
                      [("Desayuno", 0), ("Almuerzo", 0), ("Cena", 0)])
    try:
        c.execute("ALTER TABLE rendiciones_workflow ADD COLUMN moneda TEXT DEFAULT 'CLP'")
    except Exception:
        pass
    conn.commit()
    conn.close()


# ── Auth ────────────────────────────────────────────────────────────────

def db_verify_user(username_or_name, password):
    row = _exec_query("""
        SELECT id, username, role, nombre, email, rut, centro_costo, password, email_jefatura, sid, empresa, cargo
        FROM usuarios 
        WHERE username=? OR nombre=?
    """, (username_or_name, username_or_name), fetch='one')
    if row and check_password_hash(row[7], password):
        return {
            'id': row[0], 'username': row[1], 'role': row[2],
            'nombre': row[3], 'email': row[4], 'rut': row[5], 'cc': row[6],
            'email_jefatura': row[8], 'sid': row[9],
            'empresa': row[10], 'cargo': row[11]
        }
    return None


def db_get_user_by_id(uid):
    row = _exec_query(
        "SELECT id, username, role, nombre, email, rut, centro_costo, email_jefatura, terminal_asignado, empresa, cargo "
        "FROM usuarios WHERE id=?", (uid,), fetch='one'
    )
    if not row:
        return None
    return {
        'id': row[0], 'username': row[1], 'role': row[2],
        'nombre': row[3], 'email': row[4], 'rut': row[5], 'cc': row[6],
        'email_jefatura': row[7], 'terminal_asignado': row[8],
        'empresa': row[9], 'cargo': row[10],
    }


def is_super_user(user):
    if not user:
        return False
    return user.get('username') == SUPER_USERNAME or user.get('nombre') == SUPER_USERNAME


def db_get_all_visible_users(current_user):
    df = _exec_df_query(
        "SELECT id, username, role, nombre, email, rut, centro_costo, terminal_asignado, empresa, cargo "
        "FROM usuarios ORDER BY nombre"
    )
    if is_super_user(current_user):
        return df
    return df[df['username'] != SUPER_USERNAME].reset_index(drop=True)


# ── Rendiciones CRUD ────────────────────────────────────────────────────

def db_submit_rendicion(data):
    conn = sqlite3.connect(DB_PATH, timeout=20)
    c = conn.cursor()
    now = datetime.now()
    total = float(data.get('st_alojamiento', 0)) + float(data.get('st_alimentacion', 0)) + float(data.get('st_otros', 0))
    pdf_filename = f"Rendicion_HGT_{data['nombre']}_{data['fecha_rendicion']}.pdf"
    moneda = data.get('moneda', 'CLP')
    c.execute("""
        INSERT INTO rendiciones_workflow
        (nombre, rut, email_funcionario, email_jefatura, centro_costo, fecha, mes, año,
         total, status, pdf_filename, data_json, moneda)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?, ?)
    """, (data['nombre'], data['rut'], data.get('email_funcionario', ''),
          data.get('email_jefatura', ''),
          data['centro_costo'], now.strftime("%Y-%m-%d"), now.month, now.year,
          float(total), pdf_filename, serialize_data(data), moneda))
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    try:
        _sync_rendicion_detalles(new_id, data)
    except Exception:
        pass
    return new_id


def db_get_pending():
    return _exec_df_query(
        "SELECT id, nombre, email_funcionario, centro_costo, total, fecha_registro, moneda "
        "FROM rendiciones_workflow WHERE status='pendiente' ORDER BY fecha_registro DESC"
    )


def db_get_all_rendiciones_workflow():
    return _exec_df_query(
        "SELECT id, nombre, rut, centro_costo, total, status, fecha_registro, moneda "
        "FROM rendiciones_workflow ORDER BY fecha_registro DESC"
    )


def db_get_rendiciones_by_status(status_list=None):
    if status_list:
        placeholders = ','.join(['?'] * len(status_list))
        query = f"SELECT id, nombre, rut, total, status, fecha_registro, email_jefatura, moneda FROM rendiciones_workflow WHERE status IN ({placeholders}) ORDER BY fecha_registro DESC"
        return _exec_df_query(query, params=status_list)
    else:
        return _exec_df_query("SELECT id, nombre, rut, total, status, fecha_registro, email_jefatura, moneda FROM rendiciones_workflow ORDER BY fecha_registro DESC")


def db_get_rendicion(rid):
    row = _exec_query("SELECT data_json, pdf_filename, email_funcionario, nombre, pdf_aprobado FROM rendiciones_workflow WHERE id=?", (rid,), fetch='one')
    if row:
        return deserialize_data(row[0]), row[1], row[2], row[3], row[4]
    return None, None, None, None, None


def db_approve(rid, pdf_bytes, data=None):
    if data:
        _exec_query("UPDATE rendiciones_workflow SET status='APROBADO_POR_JEFATURA', pdf_aprobado=?, fecha_aprobacion=CURRENT_TIMESTAMP, data_json=? WHERE id=?",
                    (pdf_bytes, serialize_data(data), rid))
    else:
        _exec_query("UPDATE rendiciones_workflow SET status='APROBADO_POR_JEFATURA', pdf_aprobado=?, fecha_aprobacion=CURRENT_TIMESTAMP WHERE id=?",
                    (pdf_bytes, rid))


def db_reject(rid, comentario):
    _exec_query("UPDATE rendiciones_workflow SET status='RECHAZADO_POR_JEFATURA', comentario_encargado=?, fecha_aprobacion=CURRENT_TIMESTAMP WHERE id=?", (comentario, rid))


def db_encargado_approve(rid):
    _exec_query("UPDATE rendiciones_workflow SET status='PROCESADO_ENCARGADO', fecha_procesado_encargado=CURRENT_TIMESTAMP WHERE id=?", (rid,))


def db_encargado_reject(rid, comentario):
    _exec_query("UPDATE rendiciones_workflow SET status='RECHAZADO_POR_ENCARGADO', comentario_encargado=?, fecha_procesado_encargado=CURRENT_TIMESTAMP WHERE id=?", (comentario, rid))


def db_update_rendicion_data_json(rid, data):
    _exec_query("UPDATE rendiciones_workflow SET data_json=? WHERE id=?", (serialize_data(data), rid))


def db_get_encargado_stats():
    return {
        'total': _exec_df_query("SELECT count(*) FROM rendiciones_workflow").iloc[0, 0],
        'aprobadas': _exec_df_query("SELECT count(*) FROM rendiciones_workflow WHERE status='PROCESADO_ENCARGADO'").iloc[0, 0],
        'espera': _exec_df_query("SELECT count(*) FROM rendiciones_workflow WHERE status='APROBADO_POR_JEFATURA'").iloc[0, 0]
    }


def db_get_user_rendiciones(email):
    return _exec_df_query(
        "SELECT id, total, status, fecha_registro, comentario_encargado, moneda "
        "FROM rendiciones_workflow WHERE email_funcionario = ? ORDER BY fecha_registro DESC", params=(email,))


def db_update_rendicion(rid, data):
    total = float(data.get('st_alojamiento', 0)) + float(data.get('st_alimentacion', 0)) + float(data.get('st_otros', 0))
    moneda = data.get('moneda', 'CLP')
    _exec_query("""
        UPDATE rendiciones_workflow SET 
        total=?, status='pendiente', data_json=?, moneda=?,
        fecha_registro=CURRENT_TIMESTAMP, comentario_encargado=NULL
        WHERE id=?
    """, (float(total), serialize_data(data), moneda, rid))
    try:
        _sync_rendicion_detalles(rid, data)
    except Exception:
        pass


def db_reassign_jefatura(rid, new_email_jefatura):
    _exec_query("""
        UPDATE rendiciones_workflow SET 
        email_jefatura=?, 
        status='pendiente',
        fecha_aprobacion=NULL,
        pdf_aprobado=NULL,
        comentario_encargado=NULL,
        fecha_registro=CURRENT_TIMESTAMP
        WHERE id=?
    """, (new_email_jefatura, rid))


# ── Usuarios CRUD ───────────────────────────────────────────────────────

def db_get_users():
    return _exec_df_query("SELECT id, username, role, nombre, email, rut, centro_costo, terminal_asignado, empresa, cargo FROM usuarios")


def db_register_user(nombre, email, password, roles_str, rut, cc, email_jefatura=None, terminal_asignado=None, centros_costo=None, cc_cuentas=None, empresa=None, cargo=None):
    conn = _get_conn()
    c = conn.cursor()
    try:
        hashed = generate_password_hash(password)
        timestamp = datetime.now().isoformat()
        raw_sid = f"{nombre}{rut}{timestamp}"
        sid = hashlib.sha256(raw_sid.encode()).hexdigest()
        c.execute("""
            INSERT INTO usuarios (username, password, role, nombre, email, rut, centro_costo, email_jefatura, sid, terminal_asignado, empresa, cargo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (email, hashed, roles_str, nombre, email, rut, cc, email_jefatura, sid, terminal_asignado, empresa, cargo))
        roles_list = [r.strip() for r in roles_str.split(',') if r.strip()]
        db_sync_jefatura_role(email, nombre, roles_list, conn=conn)
        uid = int(c.lastrowid)
        if centros_costo:
            db_set_usuario_centros_costos(uid, centros_costo, conn=conn)
        if cc_cuentas and centros_costo:
            db_set_usuario_cc_cuentas(uid, cc_cuentas, conn=conn)
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return "El email ya está registrado."
    except Exception as e:
        return str(e)
    finally:
        conn.close()


def db_delete_user(uid, email):
    row = _exec_query("SELECT username FROM usuarios WHERE id=?", (uid,), fetch='one')
    if row and row[0] == SUPER_USERNAME:
        raise PermissionError("El usuario Super no puede ser eliminado.")
    _exec_query("DELETE FROM usuarios WHERE id=?", (uid,))
    _exec_query("DELETE FROM jefaturas WHERE email=?", (email,))


def db_update_user_roles(uid, roles_str, email):
    row = _exec_query("SELECT nombre FROM usuarios WHERE id=?", (uid,), fetch='one')
    if row and row[0] == SUPER_USERNAME:
        raise PermissionError("Los roles del Super no pueden modificarse.")
    if row:
        nombre = row[0]
        _exec_query("UPDATE usuarios SET role=? WHERE id=?", (roles_str, uid))
        roles_list = [r.strip() for r in roles_str.split(',') if r.strip()]
        db_sync_jefatura_role(email, nombre, roles_list)


def db_update_password(uid, hashed_pw):
    row = _exec_query("SELECT username FROM usuarios WHERE id=?", (uid,), fetch='one')
    if row and row[0] == SUPER_USERNAME:
        raise PermissionError("La contraseña del Super no puede cambiarse desde la UI estándar.")
    _exec_query("UPDATE usuarios SET password=? WHERE id=?", (hashed_pw, uid))


def db_update_user_full(uid, nombre, email, rut, cc, roles_str, email_jefatura=None, terminal_asignado=None, centros_costo=None, cc_cuentas=None, empresa=None, cargo=None):
    conn = _get_conn()
    c = conn.cursor()
    try:
        uid = int(uid)
        c.execute("SELECT username FROM usuarios WHERE id=?", (uid,))
        row = c.fetchone()
        if row and row[0] == SUPER_USERNAME:
            raise PermissionError("El usuario Super no puede editarse desde la UI estándar.")
        c.execute("""
            UPDATE usuarios SET 
            nombre=?, email=?, rut=?, centro_costo=?, role=?, email_jefatura=?, username=?, terminal_asignado=?, empresa=?, cargo=?
            WHERE id=?
        """, (nombre, email, rut, cc, roles_str, email_jefatura, email, terminal_asignado, empresa, cargo, uid))
        if centros_costo is not None:
            db_set_usuario_centros_costos(uid, centros_costo, conn=conn)
        if cc_cuentas is not None:
            db_set_usuario_cc_cuentas(uid, cc_cuentas, conn=conn)
        roles_list = [r.strip() for r in roles_str.split(',') if r.strip()]
        db_sync_jefatura_role(email, nombre, roles_list, conn=conn)
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()


def db_sync_jefatura_role(email, nombre, roles_list, conn=None):
    local_conn = False
    if conn is None:
        conn = _get_conn()
        local_conn = True
    c = conn.cursor()
    try:
        is_jefe = 'jefatura' in roles_list
        if is_jefe:
            c.execute("SELECT 1 FROM jefaturas WHERE email = ?", (email,))
            if not c.fetchone():
                c.execute("INSERT INTO jefaturas (nombre, email) VALUES (?, ?)", (nombre, email))
        else:
            c.execute("DELETE FROM jefaturas WHERE email = ?", (email,))
        if local_conn:
            conn.commit()
    finally:
        if local_conn:
            conn.close()


# ── Trayectos ───────────────────────────────────────────────────────────

def db_get_trayectos():
    return _exec_df_query("SELECT id, origen, destino, km_base, multiplicador_peaje, monto_peaje_base, factor, alimentacion, alimentacion_desayuno, alimentacion_almuerzo, alimentacion_cena FROM trayectos")


def db_get_trayectos_dict():
    rows = _exec_query("SELECT origen, destino, km_base, multiplicador_peaje, monto_peaje_base, factor, alimentacion, alimentacion_desayuno, alimentacion_almuerzo, alimentacion_cena FROM trayectos", fetch='all')
    return {f"{r[0]} a {r[1]}": (r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]) for r in rows} if rows else {}


def db_save_trayectos(df):
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM trayectos")
        c.executemany("""
            INSERT INTO trayectos (origen, destino, km_base, multiplicador_peaje, monto_peaje_base, factor, alimentacion, alimentacion_desayuno, alimentacion_almuerzo, alimentacion_cena)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [(row['origen'], row['destino'], row['km_base'], row['multiplicador_peaje'],
               row['monto_peaje_base'], float(row.get('factor') or 1.0), float(row.get('alimentacion') or 0),
               float(row.get('alimentacion_desayuno') or 0), float(row.get('alimentacion_almuerzo') or 0),
               float(row.get('alimentacion_cena') or 0)) for _, row in df.iterrows()])
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()


# ── Jefaturas ───────────────────────────────────────────────────────────

def db_get_jefaturas():
    return _exec_df_query("SELECT id, nombre, email FROM jefaturas")


def db_save_jefaturas(df):
    conn = _get_conn()
    c = conn.cursor()
    try:
        new_emails = df['email'].tolist()
        c.execute("DELETE FROM jefaturas")
        for _, row in df.iterrows():
            c.execute("INSERT INTO jefaturas (nombre, email) VALUES (?, ?)", (row['nombre'], row['email']))
        c.execute("SELECT id, role, email FROM usuarios WHERE role LIKE '%jefatura%'")
        current_jefes = c.fetchall()
        for uid, role_str, email in current_jefes:
            if email not in new_emails:
                roles = [r.strip() for r in role_str.split(',') if r.strip() and r.strip() != 'jefatura']
                c.execute("UPDATE usuarios SET role=? WHERE id=?", (",".join(roles), uid))
        for email in new_emails:
            c.execute("SELECT id, role FROM usuarios WHERE email=?", (email,))
            u = c.fetchone()
            if u:
                uid, role_str = u
                roles = [r.strip() for r in role_str.split(',') if r.strip()]
                if 'jefatura' not in roles:
                    roles.append('jefatura')
                    c.execute("UPDATE usuarios SET role=? WHERE id=?", (",".join(roles), uid))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()


# ── Terminales ──────────────────────────────────────────────────────────

def db_get_terminales():
    return _exec_df_query("SELECT id, nombre, codigo_interno, activo FROM terminales")


def db_save_terminales(df):
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM terminales")
        for _, row in df.iterrows():
            c.execute("INSERT INTO terminales (nombre, codigo_interno, activo) VALUES (?, ?, ?)",
                      (row['nombre'], row['codigo_interno'], int(row['activo'])))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()


# ── Cuentas Contables ───────────────────────────────────────────────────

def db_get_cuentas_contables():
    return _exec_df_query("SELECT id, codigo_cuenta, detalle_1, concepto_amigable FROM cuentas_contables")


def db_get_cuentas_by_usuario(usuario_id):
    df = db_get_cuentas_contables()
    ccs = db_get_usuario_centros_costos(usuario_id)
    if not ccs:
        return df
    codigos_set = set()
    for cc in ccs:
        for cod in db_get_centro_costo_cuentas(cc):
            codigos_set.add(cod)
    if codigos_set:
        df = df[df['codigo_cuenta'].isin(codigos_set)]
    return df


def db_save_cuentas_contables(df):
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM cuentas_contables")
        for _, row in df.iterrows():
            c.execute("INSERT INTO cuentas_contables (codigo_cuenta, detalle_1, concepto_amigable) VALUES (?, ?, ?)",
                      (row['codigo_cuenta'], row['detalle_1'], row['concepto_amigable']))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()


# ── Centros de Costo ────────────────────────────────────────────────────

def db_get_centros_costos():
    return _exec_df_query("SELECT codigo_cc, detalle_cc FROM centros_costos")


def db_save_centros_costos(df):
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM centros_costos")
        for _, row in df.iterrows():
            c.execute("INSERT INTO centros_costos (codigo_cc, detalle_cc) VALUES (?, ?)",
                      (row['codigo_cc'], row['detalle_cc']))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()


def db_get_usuario_centros_costos(usuario_id):
    rows = _exec_query("SELECT codigo_cc FROM usuario_centro_costo WHERE usuario_id=?", (usuario_id,), fetch='all')
    return [r[0] for r in rows] if rows else []


def db_set_usuario_centros_costos(usuario_id, codigos_cc, conn=None):
    local_conn = False
    if conn is None:
        conn = _get_conn()
        local_conn = True
    c = conn.cursor()
    try:
        usuario_id = int(usuario_id)
        c.execute("DELETE FROM usuario_centro_costo WHERE usuario_id=?", (usuario_id,))
        for cod in codigos_cc:
            c.execute("INSERT OR IGNORE INTO usuario_centro_costo (usuario_id, codigo_cc) VALUES (?, ?)", (usuario_id, cod))
        if local_conn:
            conn.commit()
    finally:
        if local_conn:
            conn.close()


def db_get_centro_costo_cuentas(codigo_cc):
    rows = _exec_query("SELECT codigo_cuenta FROM centro_costo_cuenta WHERE codigo_cc=?", (codigo_cc,), fetch='all')
    return [r[0] for r in rows] if rows else []


def db_set_centro_costo_cuentas(codigo_cc, codigos_cuenta):
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM centro_costo_cuenta WHERE codigo_cc=?", (codigo_cc,))
        for cod in codigos_cuenta:
            c.execute("INSERT OR IGNORE INTO centro_costo_cuenta (codigo_cc, codigo_cuenta) VALUES (?, ?)", (codigo_cc, cod))
        conn.commit()
    finally:
        conn.close()


def db_get_all_centro_costo_cuentas():
    return _exec_df_query("SELECT codigo_cc, codigo_cuenta FROM centro_costo_cuenta ORDER BY codigo_cc, codigo_cuenta")


def db_get_usuario_cc_cuentas(usuario_id):
    rows = _exec_query("SELECT codigo_cc, codigo_cuenta FROM usuario_centro_costo_cuenta WHERE usuario_id=?", (usuario_id,), fetch='all')
    result = {}
    for cc, cta in (rows or []):
        result.setdefault(cc, []).append(cta)
    return result


def db_set_usuario_cc_cuentas(usuario_id, cc_cuentas_dict, conn=None):
    local_conn = False
    if conn is None:
        conn = _get_conn()
        local_conn = True
    c = conn.cursor()
    try:
        usuario_id = int(usuario_id)
        c.execute("DELETE FROM usuario_centro_costo_cuenta WHERE usuario_id=?", (usuario_id,))
        for cc, cuentas in cc_cuentas_dict.items():
            for cta in cuentas:
                c.execute("INSERT OR IGNORE INTO usuario_centro_costo_cuenta (usuario_id, codigo_cc, codigo_cuenta) VALUES (?, ?, ?)",
                          (usuario_id, cc, cta))
        if local_conn:
            conn.commit()
    finally:
        if local_conn:
            conn.close()


# ── Topes USD ───────────────────────────────────────────────────────────

def db_get_topes_usd():
    return _exec_df_query("SELECT id, concepto, tope_usd FROM topes_usd ORDER BY id")


def db_save_topes_usd(df):
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM topes_usd")
        for _, row in df.iterrows():
            c.execute("INSERT INTO topes_usd (concepto, tope_usd) VALUES (?, ?)",
                      (row['concepto'], float(row['tope_usd'])))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()


def db_get_topes_usd_dict():
    rows = _exec_query("SELECT concepto, tope_usd FROM topes_usd", fetch='all')
    return {r[0]: r[1] for r in rows} if rows else {}


# ── Dashboard / Sync ────────────────────────────────────────────────────

def _sync_rendicion_detalles(rendicion_id, data):
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM rendiciones_detalles WHERE rendicion_id=?", (rendicion_id,))
        colaborador_id = data.get('user_id')
        cc = data.get('centro_costo')
        global_cuenta_id = data.get('cuenta_id')
        if global_cuenta_id:
            try:
                global_cuenta_id = int(global_cuenta_id)
            except (ValueError, TypeError):
                global_cuenta_id = None
        c.execute("SELECT id FROM cuentas_contables LIMIT 1")
        fallback_row = c.fetchone()
        fallback_cta = fallback_row[0] if fallback_row else 1
        items = []
        for df_key in ["df_alojamiento", "df_alimentacion", "df_otros", "df_comision"]:
            df = data.get(df_key)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    monto = row.get('Monto', 0)
                    fecha = row.get('Fecha')
                    detalle = row.get('Detalle', '')
                    row_cuenta = row.get('cuenta_id')
                    if pd.notna(row_cuenta):
                        try:
                            cuenta_id = int(float(row_cuenta))
                        except (ValueError, TypeError):
                            cuenta_id = None
                    else:
                        cuenta_id = None
                    if not cuenta_id:
                        if global_cuenta_id:
                            cuenta_id = global_cuenta_id
                        else:
                            cuenta_id = fallback_cta
                    if pd.notna(fecha):
                        fecha_str = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha)[:10]
                    else:
                        fecha_str = datetime.now().strftime('%Y-%m-%d')
                    items.append({
                        'rendicion_id': rendicion_id,
                        'colaborador_id': colaborador_id,
                        'centro_costo_codigo': cc,
                        'cuenta_id': cuenta_id,
                        'ruta_id': None,
                        'es_ida_vuelta': 0,
                        'lleva_acompanante': 0,
                        'detalle_gasto': str(detalle) if pd.notna(detalle) else '',
                        'monto_total': float(monto) if pd.notna(monto) else 0,
                        'fecha_gasto': fecha_str
                    })
        for item in items:
            if item['monto_total'] == 0:
                continue
            c.execute("""
                INSERT INTO rendiciones_detalles 
                (rendicion_id, colaborador_id, centro_costo_codigo, cuenta_id, ruta_id,
                 es_ida_vuelta, lleva_acompanante, detalle_gasto, monto_total, fecha_gasto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item['rendicion_id'], item['colaborador_id'], item['centro_costo_codigo'],
                  item['cuenta_id'], item['ruta_id'], item['es_ida_vuelta'],
                  item['lleva_acompanante'], item['detalle_gasto'], item['monto_total'],
                  item['fecha_gasto']))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ── Aprobadores ───────────────────────────────────────────────────────

def db_get_usuarios_aprobadores():
    """Retorna usuarios con rol 'jefatura' (aprobadores) para el Paso 5."""
    df = _exec_df_query(
        "SELECT id, nombre, email, rut FROM usuarios WHERE role LIKE '%jefatura%' ORDER BY nombre"
    )
    return df


# ── Borrador (Draft) ──────────────────────────────────────────────────

def db_save_draft(user_id, data_json):
    """Guarda un borrador de rendición para el usuario."""
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS rendiciones_borrador (
                user_id INTEGER PRIMARY KEY,
                data_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            INSERT OR REPLACE INTO rendiciones_borrador (user_id, data_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (user_id, data_json))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def db_load_draft(user_id):
    """Carga el borrador de rendición del usuario."""
    row = _exec_query(
        "SELECT data_json FROM rendiciones_borrador WHERE user_id=?",
        (user_id,), fetch='one'
    )
    if row:
        return row[0]
    return None


def db_delete_draft(user_id):
    """Elimina el borrador de rendición del usuario."""
    _exec_query("DELETE FROM rendiciones_borrador WHERE user_id=?", (user_id,))


# ── Dashboard / Sync ────────────────────────────────────────────────────

def db_get_dashboard_data(fecha_desde=None, fecha_hasta=None, usuario_id=None,
                          sucursal=None, codigo_cc=None, cuenta_id=None):
    where_clauses = []
    params = []
    if fecha_desde:
        where_clauses.append("rd.fecha_gasto >= ?")
        params.append(fecha_desde)
    if fecha_hasta:
        where_clauses.append("rd.fecha_gasto <= ?")
        params.append(fecha_hasta)
    if usuario_id:
        where_clauses.append("rd.colaborador_id = ?")
        params.append(int(usuario_id))
    if sucursal:
        where_clauses.append("u.terminal_asignado = ?")
        params.append(sucursal)
    if codigo_cc:
        where_clauses.append("rd.centro_costo_codigo = ?")
        params.append(codigo_cc)
    if cuenta_id:
        where_clauses.append("rd.cuenta_id = ?")
        params.append(int(cuenta_id))
    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = f"""
        SELECT 
            rd.id, rd.fecha_gasto, rd.colaborador_id,
            COALESCE(u.nombre, rw.nombre) AS colaborador, u.rut, u.terminal_asignado,
            t.nombre AS sucursal,
            cc.codigo_cc, cc.detalle_cc AS centro_costo,
            ct.codigo_cuenta, ct.detalle_1 AS cuenta_detalle, ct.concepto_amigable,
            rd.detalle_gasto, rd.monto_total, rd.rendicion_id
        FROM rendiciones_detalles rd
        LEFT JOIN rendiciones_workflow rw ON rd.rendicion_id = rw.id
        LEFT JOIN usuarios u ON rd.colaborador_id = u.id
        LEFT JOIN terminales t ON u.terminal_asignado = t.nombre
        LEFT JOIN centros_costos cc ON rd.centro_costo_codigo = cc.codigo_cc
        LEFT JOIN cuentas_contables ct ON rd.cuenta_id = ct.id
        {where}
        ORDER BY rd.fecha_gasto DESC, rd.id
    """
    return _exec_df_query(sql, params)

