"""
utils.py — Módulo compartido: PDF, email, base de datos
HGT Chile Logistics · Rendición de Gastos
"""
import os, json, base64, sqlite3, smtplib, hashlib, re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.header import Header
from io import BytesIO
import pandas as pd
import streamlit as st
import google.generativeai as genai
from fpdf import FPDF

# ── Rutas globales ──────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo_hgt.png")
DB_PATH   = os.path.join(BASE_DIR, "rendiciones_hgt.db")

# ── Helpers ─────────────────────────────────────────────────────────────────
def format_curr(val):
    try:
        return f"$ {float(val):,.0f}".replace(",", ".")
    except Exception:
        return "$ 0"

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_pw(password, hashed):
    return hash_pw(password) == hashed

def _get_conn():
    """Obtiene conexión SQLite con timeout optimizado."""
    return sqlite3.connect(DB_PATH, timeout=20)

def _exec_query(query, params=None, fetch=None):
    """Ejecuta una consulta SQL y devuelve resultados."""
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
    """Ejecuta consulta y devuelve DataFrame."""
    conn = _get_conn()
    try:
        return pd.read_sql_query(query, conn, params=params if params else None)
    finally:
        conn.close()

# ── Clase PDF ─────────────────────────────────────────────────────────────
class PDFHGT(FPDF):
    def header(self):
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, 13, 8, 30)
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'RENDICIÓN DE GASTOS', 0, 0, 'C')
        self.set_font('Helvetica', 'B', 7)
        self.cell(0, 10, 'PESOS CHILENOS', 0, 1, 'R')
        self.ln(2)
        self.set_xy(13, 33)
        self.set_font('Helvetica', 'B', 8)
        self.cell(0, 5, 'HGT Chile Logistics', 0, 1, 'L')
        self.ln(2)


    def draw_section_header(self, title):
        self.set_fill_color(240, 240, 240)
        self.set_font('Helvetica', 'B', 9)
        self.cell(0, 6, title, 1, 1, 'L', fill=True)


# ── Generación de PDF ──────────────────────────────────────────────────────
def generate_hgt_pdf(data):
    tr = (len(data['df_comision']) + len(data['df_alojamiento'])
          + len(data['df_alimentacion']) + len(data['df_otros']))
    p_format = 'letter' if tr <= 25 else (216, 330)

    pdf = PDFHGT(orientation='P', unit='mm', format=p_format)
    pdf.set_left_margin(13); pdf.set_right_margin(13)
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()

    def clean(t):
        return str(t).replace('→', ' a ').encode('latin-1', 'replace').decode('latin-1')

    def fmt_date(val):
        if hasattr(val, 'strftime'):
            try:
                if pd.isnull(val):
                    return ''
            except Exception:
                pass
            return val.strftime('%d/%m/%Y')
        return str(val)

    # -- Funcionario --
    pdf.draw_section_header('Funcionario que rinde')
    pdf.set_font('Helvetica', '', 8)
    # Ajustar anchos para evitar traslape en nombres largos
    pdf.cell(20, 6, 'Nombre:', 'LTB')
    pdf.cell(75, 6, clean(data['nombre']), 'RTB')
    pdf.cell(20, 6, 'Rut:', 'LTB')
    pdf.cell(75, 6, clean(data['rut']), 'RTB', 1)
    pdf.cell(20, 6, 'C. Costo:', 'LTB')
    pdf.cell(0, 6, clean(data['centro_costo']), 'RTB', 1)
    pdf.ln(4)

    # -- Comisión --
    pdf.draw_section_header('Detalle de Comisión de Servicios')
    pdf.set_font('Helvetica', 'B', 7)
    for label, w in [('desde oficina / a localidad / traslado', 60), ('desde oficina', 43.3),
                      ('a localidad', 43.3), ('Fecha Inicio', 21.7), ('Fecha Término', 21.7)]:
        pdf.cell(w, 5, label, 1, 0, 'C', fill=True)
    pdf.ln(); pdf.set_font('Helvetica', '', 7)
    for _, row in data['df_comision'].iterrows():
        pdf.cell(60, 5, clean(row.get('Traslado', '')), 1)
        pdf.cell(43.3, 5, clean(row.get('Desde oficina', '')), 1)
        pdf.cell(43.3, 5, clean(row.get('A localidad', '')), 1)
        pdf.cell(21.7, 5, fmt_date(row.get('Fecha Inicio', '')), 1, 0, 'C')
        pdf.cell(21.7, 5, fmt_date(row.get('Fecha Término', '')), 1, 1, 'C')
    pdf.ln(4)

    # -- Anticipo --
    pdf.set_font('Helvetica', 'B', 9)
    curr_y = pdf.get_y()
    pdf.cell(100, 10, 'Anticipo sujeto a rendición', 1, 0, 'L')
    pdf.cell(40, 5, 'Fecha Egreso', 1, 0, 'C')
    pdf.cell(30, 10, 'Total (A)', 1, 0, 'C', fill=True)
    pdf.cell(20, 10, format_curr(data['anticipo']), 1, 1, 'R')
    pdf.set_xy(113, curr_y + 5); pdf.set_font('Helvetica', '', 7)
    pdf.cell(40, 5, fmt_date(data.get('fecha_anticipo', '')), 1, 1, 'C')
    pdf.ln(4)

    # -- Tablas de gastos --
    def draw_concept_table(title, items, total_label, total_val, include_doc=True):
        pdf.draw_section_header(title); pdf.set_font('Helvetica', 'B', 8)
        if include_doc:
            pdf.cell(70, 5, 'Lugar / Detalle', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, 'Fecha Docto', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, 'N° Documento', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, 'Monto $', 1, 1, 'C', fill=True)
        else:
            pdf.cell(110, 5, 'Lugar / Detalle', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, 'Fecha Docto', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, 'Monto $', 1, 1, 'C', fill=True)
            
        pdf.set_font('Helvetica', '', 8)
        for _, row in items.iterrows():
            detalle = row.get('Detalle') or row.get('detalle') or row.get('Lugar') or ""
            monto = row.get('Monto') or row.get('monto') or 0
            fecha = row.get('Fecha') or row.get('fecha') or ""
            doc = row.get('Doc') or row.get('doc') or ""

            if not str(detalle).strip() and not monto:
                continue

            if include_doc:
                pdf.cell(70, 5, clean(detalle), 1)
                pdf.cell(40, 5, fmt_date(fecha), 1, 0, 'C')
                pdf.cell(40, 5, clean(doc), 1, 0, 'C')
                pdf.cell(40, 5, format_curr(monto), 1, 1, 'R')
            else:
                pdf.cell(110, 5, clean(detalle), 1)
                pdf.cell(40, 5, fmt_date(fecha), 1, 0, 'C')
                pdf.cell(40, 5, format_curr(monto), 1, 1, 'R')
                
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(150, 6, total_label, 1, 0, 'R', fill=True)
        pdf.cell(40, 6, format_curr(total_val), 1, 1, 'R')
        pdf.ln(3)

    draw_concept_table('ALOJAMIENTO',   data['df_alojamiento'],  'SUBTOTAL (B)', data['st_alojamiento'])
    draw_concept_table('ALIMENTACIÓN',  data['df_alimentacion'], 'SUBTOTAL (C)', data['st_alimentacion'])
    draw_concept_table('OTROS GASTOS',  data['df_otros'],        'SUBTOTAL (D)', data['st_otros'])

    td    = float(data.get('st_alojamiento', 0)) + float(data.get('st_alimentacion', 0)) + float(data.get('st_otros', 0))
    delta = data['anticipo'] - td
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(150, 6, 'Total Desembolsos (B+C+D)', 1, 0, 'R')
    pdf.cell(40, 6, format_curr(td), 1, 1, 'R', fill=True)
    pdf.ln(1)
    pdf.cell(120, 6, 'Diferencia a favor de HGT CHILE LOGISTICS', 'LT', 0, 'L')
    pdf.cell(30, 6, '[ A - (B+C+D) ]', 'TR', 0, 'C')
    pdf.cell(40, 6, format_curr(max(0, delta)) if delta >= 0 else "-", 1, 1, 'R')
    pdf.cell(150, 6, 'Diferencia a favor de Funcionario ( - )', 1, 0, 'L')
    pdf.cell(40, 6, format_curr(abs(delta)) if delta < 0 else "-", 1, 1, 'R')
    pdf.ln(5)

    # -- Firmas Digitales --
    pdf.set_auto_page_break(False) # Evitar saltos de página en el pie
    firma_y = pdf.h - 28
    pdf.set_text_color(0, 0, 0)

    # 1. Funcionario (Stack vertical: QR, Nombre, RUT)
    # RUT (Justo sobre la línea)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.set_xy(88, firma_y - 4)
    pdf.cell(65, 4, clean(data['rut']), 0, 0, 'C')
    
    # Nombre (Sobre el RUT)
    pdf.set_xy(88, firma_y - 8)
    pdf.cell(65, 4, clean(data['nombre']), 0, 0, 'C')

    # 2. Jefe (Si aplica)
    is_approved = data.get('status') in ['APROBADO_POR_JEFATURA', 'PROCESADO_FINAL', 'PROCESADO_ENCARGADO'] or data.get('fecha_aprobacion')
    if is_approved:
        j_nom = data.get('jefe_nombre', 'Jefatura')
        j_rut = data.get('jefe_rut', '')
        
        # RUT Jefe
        pdf.set_xy(163, firma_y - 4)
        pdf.cell(40, 4, clean(j_rut), 0, 0, 'C')
        # Nombre Jefe
        pdf.set_xy(163, firma_y - 8)
        pdf.cell(40, 4, clean(j_nom), 0, 0, 'C')

    # Líneas de Firma y Etiquetas
    pdf.set_xy(13, firma_y)
    pdf.set_font('Helvetica', '', 8)
    pdf.cell(65, 5, data.get('fecha_rendicion', ''), 'T', 0, 'C')
    pdf.cell(10, 5, '', 0, 0)
    pdf.cell(65, 5, 'Firma Funcionario', 'T', 0, 'C')
    pdf.cell(10, 5, '', 0, 0)
    pdf.cell(40, 5, 'Firma Jefe Directo', 'T', 1, 'C')

    if data.get('fecha_aprobacion') and data.get('jefe_rut'):
        jefe_rut = data.get('jefe_rut')
        fecha_hora = data.get('fecha_aprobacion')
        texto_validacion = f"El documento fue aprobado mediante firma digital vinculada a la Cédula {jefe_rut} en fecha {fecha_hora}"
        pdf.set_xy(13, pdf.h - 12)
        pdf.set_font('Helvetica', 'I', 7)
        pdf.cell(0, 4, texto_validacion, 0, 0, 'C')

    # -- QR de Validación de Firma Digital Segura --
    try:
        import qrcode
        user_sid = data.get('user_sid', '')
        qr = qrcode.QRCode(version=1, box_size=2, border=1)
        qr_data = f"Firma Digital Segura HGT\nFuncionario: {data.get('nombre')}\nID Funcionario: {user_sid[:8] if user_sid else 'N/A'}"
        if is_approved:
            qr_data += f"\nAprobado por Jefatura\nFecha: {data.get('fecha_aprobacion', 'OK')}"
            
        qr.add_data(qr_data)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        qr_bytes = BytesIO()
        img_qr.save(qr_bytes, format='PNG')
        qr_bytes.seek(0)
        
        # Colocar el QR sobre la firma del funcionario (centrado y arriba de todo)
        pdf.image(qr_bytes, x=112.5, y=firma_y - 26, w=16)
        
        if is_approved:
            # También colocar el QR sobre la firma de jefatura
            pdf.image(qr_bytes, x=175, y=firma_y - 26, w=16)
    except ImportError:
        pass # Si falla qrcode, no se genera el QR pero no rompe el PDF


    # -- Comprobantes --
    receipt_images = data.get('receipt_photos', [])
    if receipt_images:
        from PIL import Image
        positions = [(18, 60), (113, 60), (18, 168), (113, 168)]
        max_w, max_h = 85, 95
        for i in range(0, len(receipt_images), 4):
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Documentos de Respaldo / Comprobantes de Gasto', 0, 1, 'C')
            for idx, img_b in enumerate(receipt_images[i:i + 4]):
                try:
                    s = BytesIO(img_b)
                    with Image.open(s) as img:
                        iw, ih = img.size
                    sc = min(max_w / iw, max_h / ih)
                    fw3, fh3 = iw * sc, ih * sc
                    x, y = positions[idx]
                    s.seek(0)
                    pdf.image(s, x=x + (max_w - fw3) / 2, y=y, w=fw3, h=fh3)
                except Exception as e:
                    x, y = positions[idx]
                    pdf.set_xy(x, y); pdf.set_font('Helvetica', 'I', 8)
                    pdf.cell(max_w, 10, f"Error imagen: {str(e)[:20]}", 0, 0)

    return bytes(pdf.output())


# ── Email ─────────────────────────────────────────────────────────────────
def send_hgt_email(smtp_conf, to_email, subject, body, pdf_bytes=None, pdf_name=None):
    try:
        msg = MIMEMultipart()
        msg['From']    = smtp_conf["user"]
        msg['To']      = to_email
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
        srv.starttls(); srv.login(smtp_conf["user"], smtp_conf["password"])
        srv.send_message(msg); srv.quit()
        return True
    except Exception as e:
        return str(e)


# ── Base de Datos ──────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    c = conn.cursor()
    # Tabla legacy (historial antiguo)
    c.execute("""
        CREATE TABLE IF NOT EXISTS rendiciones (
            id_rut TEXT PRIMARY KEY, nombre TEXT, fecha TEXT,
            mes INTEGER, año INTEGER, centro_costo TEXT, total REAL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Tabla de workflow con aprobaciones
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
    # Tabla de Usuarios (Actualizada con Firma, Jefatura y SID)
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE, password TEXT, role TEXT,
            nombre TEXT, email TEXT, rut TEXT, centro_costo TEXT,
            firma_bytes BLOB, email_jefatura TEXT, sid TEXT
        )
    """)
    # Verificar si las columnas nuevas existen (migración simple)
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN firma_bytes BLOB")
    except: pass
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN email_jefatura TEXT")
    except: pass
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN sid TEXT")
    except: pass
    # Tabla de Trayectos (Mantención)
    c.execute("""
        CREATE TABLE IF NOT EXISTS trayectos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origen TEXT, destino TEXT, km_base REAL, 
            multiplicador_peaje INTEGER, monto_peaje_base INTEGER,
            factor REAL DEFAULT 1.0,
            colacion REAL DEFAULT 0
        )
    """)
    # Verificar si la columna colacion existe (migración)
    try:
        c.execute("ALTER TABLE trayectos ADD COLUMN colacion REAL DEFAULT 0")
    except: pass
    # Tabla: valor alimentación por persona
    try:
        c.execute("ALTER TABLE trayectos ADD COLUMN alimentacion REAL DEFAULT 0")
    except: pass
    # Tabla de Jefaturas (Mantención)
    c.execute("""
        CREATE TABLE IF NOT EXISTS jefaturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT, email TEXT
        )
    """)
    
    # Usuario admin inicial si no existe
    c.execute("SELECT count(*) FROM usuarios WHERE username='admin'")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO usuarios (username, password, role, nombre) 
            VALUES (?, ?, ?, ?)
        """, ('admin', hash_pw('123'), 'admin', 'Administrador Sistema'))
        
    # Seed de trayectos iniciales si está vacía
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
        c.executemany("""
            INSERT INTO trayectos (origen, destino, km_base, multiplicador_peaje, monto_peaje_base)
            VALUES (?, ?, ?, ?, ?)
        """, seeds)

    conn.commit(); conn.close()


def _df_to_json(df):
    df2 = df.copy()
    for col in df2.select_dtypes(include=['datetime64[ns]', 'datetime64[ns, UTC]']).columns:
        df2[col] = df2[col].apply(lambda v: v.strftime('%Y-%m-%d') if pd.notna(v) else '')
    return df2.to_json()


def _read_df(json_str, date_cols=None, expected_cols=None):
    try:
        df = pd.read_json(json_str)
        if expected_cols:
            # Si el DF viene con nombres de columnas numéricos o faltantes, remapear
            if len(df.columns) == len(expected_cols):
                df.columns = expected_cols
        if date_cols:
            for col in date_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame(columns=expected_cols) if expected_cols else pd.DataFrame()


def serialize_data(data):
    return json.dumps({
        'nombre':           data['nombre'],
        'rut':              data['rut'],
        'email_funcionario':data.get('email_funcionario', ''),
        'email_jefatura':   data.get('email_jefatura', ''),
        'user_id':          data.get('user_id'),
        'user_sid':         data.get('user_sid'),
        'jefe_id':          data.get('jefe_id'),
        'jefe_sid':         data.get('jefe_sid'),
        'jefe_rut':         data.get('jefe_rut', ''),
        'jefe_nombre':      data.get('jefe_nombre', ''),
        'fecha_aprobacion': data.get('fecha_aprobacion', ''),
        'centro_costo':     data['centro_costo'],
        'anticipo':         float(data['anticipo']),
        'fecha_anticipo':   (data['fecha_anticipo'].isoformat()
                             if hasattr(data['fecha_anticipo'], 'isoformat')
                             else str(data['fecha_anticipo'])),
        'df_comision':      _df_to_json(data['df_comision']),
        'df_alojamiento':   _df_to_json(data['df_alojamiento']),
        'df_alimentacion':  _df_to_json(data['df_alimentacion']),
        'df_otros':         _df_to_json(data['df_otros']),
        'st_alojamiento':   float(data['st_alojamiento']),
        'st_alimentacion':  float(data['st_alimentacion']),
        'st_otros':         float(data['st_otros']),
        'fecha_rendicion':  data['fecha_rendicion'],
        'receipt_photos':   [base64.b64encode(p).decode()
                             for p in data.get('receipt_photos', [])],
    })


def deserialize_data(json_str):
    sd = json.loads(json_str)
    try:
        fa = datetime.fromisoformat(sd.get('fecha_anticipo', '')).date()
    except Exception:
        fa = datetime.today().date()
    return {
        'nombre':           sd['nombre'],
        'rut':              sd['rut'],
        'email_funcionario':sd.get('email_funcionario', ''),
        'user_id':          sd.get('user_id'),
        'user_sid':         sd.get('user_sid'),
        'jefe_id':          sd.get('jefe_id'),
        'jefe_sid':         sd.get('jefe_sid'),
        'jefe_rut':         sd.get('jefe_rut', ''),
        'jefe_nombre':      sd.get('jefe_nombre', ''),
        'fecha_aprobacion': sd.get('fecha_aprobacion', ''),
        'centro_costo':     sd['centro_costo'],
        'anticipo':         sd['anticipo'],
        'fecha_anticipo':   fa,
        'df_comision':      _read_df(sd['df_comision'],     ['Fecha Inicio', 'Fecha Término'], ["Traslado", "Desde oficina", "A localidad", "Fecha Inicio", "Fecha Término"]),
        'df_alojamiento':   _read_df(sd['df_alojamiento'],  ['Fecha'], ["Detalle", "Fecha", "Doc", "Monto"]),
        'df_alimentacion':  _read_df(sd['df_alimentacion'], ['Fecha'], ["Detalle", "Fecha", "Doc", "Monto"]),
        'df_otros':         _read_df(sd['df_otros'],        ['Fecha'], ["Detalle", "Fecha", "Doc", "Monto"]),
        'st_alojamiento':   sd['st_alojamiento'],
        'st_alimentacion':  sd['st_alimentacion'],
        'st_otros':         sd['st_otros'],
        'fecha_rendicion':  sd['fecha_rendicion'],
        'receipt_photos':   [base64.b64decode(p) for p in sd.get('receipt_photos', [])],
    }


def db_submit_rendicion(data):
    """Guarda una rendición en estado 'pendiente' y devuelve el ID."""
    conn = sqlite3.connect(DB_PATH, timeout=20)
    c    = conn.cursor()
    now  = datetime.now()
    total = float(data.get('st_alojamiento', 0)) + float(data.get('st_alimentacion', 0)) + float(data.get('st_otros', 0))
    pdf_filename = f"Rendicion_HGT_{data['nombre']}_{data['fecha_rendicion']}.pdf"
    c.execute("""
        INSERT INTO rendiciones_workflow
        (nombre, rut, email_funcionario, email_jefatura, centro_costo, fecha, mes, año,
         total, status, pdf_filename, data_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?)
    """, (data['nombre'], data['rut'], data.get('email_funcionario', ''),
          data.get('email_jefatura', ''),
          data['centro_costo'], now.strftime("%Y-%m-%d"), now.month, now.year,
          float(total), pdf_filename, serialize_data(data)))
    new_id = c.lastrowid
    conn.commit(); conn.close()
    return new_id


def db_get_pending():
    return _exec_df_query(
        "SELECT id, nombre, rut, email_funcionario, centro_costo, total, fecha_registro "
        "FROM rendiciones_workflow WHERE status='pendiente' ORDER BY fecha_registro DESC")


def db_get_all_rendiciones_workflow():
    return _exec_df_query(
        "SELECT id, nombre, rut, centro_costo, total, status, fecha_registro "
        "FROM rendiciones_workflow ORDER BY fecha_registro DESC")

def db_get_rendiciones_by_status(status_list=None):
    if status_list:
        placeholders = ','.join(['?'] * len(status_list))
        query = f"SELECT id, nombre, rut, total, status, fecha_registro, email_jefatura FROM rendiciones_workflow WHERE status IN ({placeholders}) ORDER BY fecha_registro DESC"
        return _exec_df_query(query, params=status_list)
    else:
        return _exec_df_query("SELECT id, nombre, rut, total, status, fecha_registro, email_jefatura FROM rendiciones_workflow ORDER BY fecha_registro DESC")


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
    _exec_query("UPDATE rendiciones_workflow SET status='PROCESADO_FINAL', fecha_procesado_encargado=CURRENT_TIMESTAMP WHERE id=?", (rid,))

def db_encargado_reject(rid, comentario):
    _exec_query("UPDATE rendiciones_workflow SET status='RECHAZADO_POR_ENCARGADO', comentario_encargado=?, fecha_procesado_encargado=CURRENT_TIMESTAMP WHERE id=?", 
               (comentario, rid))

def db_get_encargado_stats():
    return {
        'total': _exec_df_query("SELECT count(*) FROM rendiciones_workflow").iloc[0,0],
        'aprobadas': _exec_df_query("SELECT count(*) FROM rendiciones_workflow WHERE status='PROCESADO_FINAL'").iloc[0,0],
        'espera': _exec_df_query("SELECT count(*) FROM rendiciones_workflow WHERE status='APROBADO_POR_JEFATURA'").iloc[0,0]
    }

def db_get_pending_encargado():
    return _exec_df_query(
        "SELECT id, nombre, rut, total, fecha_registro "
        "FROM rendiciones_workflow WHERE status='APROBADO_POR_JEFATURA' ORDER BY fecha_registro DESC")

def db_get_user_rendiciones(email):
    return _exec_df_query(
        "SELECT id, total, status, fecha_registro, comentario_encargado "
        "FROM rendiciones_workflow WHERE email_funcionario = ? ORDER BY fecha_registro DESC", params=(email,))

def db_update_rendicion(rid, data):
    """Actualiza una rendición existente y reinicia su estado a pendiente."""
    total = float(data.get('st_alojamiento', 0)) + float(data.get('st_alimentacion', 0)) + float(data.get('st_otros', 0))
    _exec_query("""
        UPDATE rendiciones_workflow SET 
        total=?, status='pendiente', data_json=?, 
        fecha_registro=CURRENT_TIMESTAMP, comentario_encargado=NULL
        WHERE id=?
    """, (float(total), serialize_data(data), rid))

def db_reassign_jefatura(rid, new_email_jefatura):
    """Reasigna la jefatura que debe aprobar una rendición."""
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

def db_sync_jefatura_role(email, nombre, roles_list, conn=None):
    """Sincroniza el rol jefatura con la tabla jefaturas."""
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

def db_verify_user(username_or_name, password):
    row = _exec_query("""
        SELECT id, username, role, nombre, email, rut, centro_costo, password, email_jefatura, sid 
        FROM usuarios 
        WHERE username=? OR nombre=?
    """, (username_or_name, username_or_name), fetch='one')
    if row and verify_pw(password, row[7]):
        return {
            'id': row[0], 'username': row[1], 'role': row[2],
            'nombre': row[3], 'email': row[4], 'rut': row[5], 'cc': row[6],
            'email_jefatura': row[8], 'sid': row[9]
        }
    return None

def db_get_users():
    return _exec_df_query("SELECT id, username, role, nombre, email, rut, centro_costo FROM usuarios")

def db_get_trayectos():
    return _exec_df_query("SELECT id, origen, destino, km_base, multiplicador_peaje, monto_peaje_base, factor, alimentacion FROM trayectos")

def db_get_trayectos_dict():
    rows = _exec_query("SELECT origen, destino, km_base, multiplicador_peaje, monto_peaje_base, factor, alimentacion FROM trayectos", fetch='all')
    return {f"{r[0]} a {r[1]}": (r[2], r[3], r[4], r[5], r[6]) for r in rows} if rows else {}

def db_get_jefaturas():
    return _exec_df_query("SELECT id, nombre, email FROM jefaturas")

def db_save_jefaturas(df):
    """Guarda las jefaturas y sincroniza los roles en la tabla de usuarios."""
    conn = sqlite3.connect(DB_PATH, timeout=20)
    c = conn.cursor()
    try:
        new_emails = df['email'].tolist()
        
        # 1. Actualizar tabla jefaturas
        c.execute("DELETE FROM jefaturas")
        for _, row in df.iterrows():
            c.execute("INSERT INTO jefaturas (nombre, email) VALUES (?, ?)", (row['nombre'], row['email']))
        
        # 2. Quitar rol 'jefatura' a quienes ya no están en la lista
        c.execute("SELECT id, role, email FROM usuarios WHERE role LIKE '%jefatura%'")
        current_jefes = c.fetchall()
        for uid, role_str, email in current_jefes:
            if email not in new_emails:
                roles = [r.strip() for r in role_str.split(',') if r.strip() and r.strip() != 'jefatura']
                new_roles_str = ",".join(roles)
                c.execute("UPDATE usuarios SET role=? WHERE id=?", (new_roles_str, uid))
        
        # 3. Agregar rol 'jefatura' a quienes fueron añadidos (si tienen usuario)
        for email in new_emails:
            c.execute("SELECT id, role FROM usuarios WHERE email=?", (email,))
            u = c.fetchone()
            if u:
                uid, role_str = u
                roles = [r.strip() for r in role_str.split(',') if r.strip()]
                if 'jefatura' not in roles:
                    roles.append('jefatura')
                    new_roles_str = ",".join(roles)
                    c.execute("UPDATE usuarios SET role=? WHERE id=?", (new_roles_str, uid))

        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()

def db_register_user(nombre, email, password, roles_str, rut, cc, email_jefatura=None):
    """Registra un nuevo usuario y sincroniza si es jefatura."""
    conn = _get_conn()
    c = conn.cursor()
    try:
        hashed = hash_pw(password)
        timestamp = datetime.now().isoformat()
        raw_sid = f"{nombre}{rut}{timestamp}"
        sid = hashlib.sha256(raw_sid.encode()).hexdigest()

        c.execute("""
            INSERT INTO usuarios (username, password, role, nombre, email, rut, centro_costo, email_jefatura, sid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (email, hashed, roles_str, nombre, email, rut, cc, email_jefatura, sid))
        
        roles_list = [r.strip() for r in roles_str.split(',') if r.strip()]
        db_sync_jefatura_role(email, nombre, roles_list, conn=conn)
        
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return "El email ya está registrado."
    except Exception as e:
        return str(e)
    finally:
        conn.close()

def db_delete_user(uid, email):
    _exec_query("DELETE FROM usuarios WHERE id=?", (uid,))
    _exec_query("DELETE FROM jefaturas WHERE email=?", (email,))

def db_update_user_roles(uid, roles_str, email):
    row = _exec_query("SELECT nombre FROM usuarios WHERE id=?", (uid,), fetch='one')
    if row:
        nombre = row[0]
        _exec_query("UPDATE usuarios SET role=? WHERE id=?", (roles_str, uid))
        roles_list = [r.strip() for r in roles_str.split(',') if r.strip()]
        db_sync_jefatura_role(email, nombre, roles_list)

def db_update_password(uid, hashed_pw):
    _exec_query("UPDATE usuarios SET password=? WHERE id=?", (hashed_pw, uid))

def db_get_all(table):
    return _exec_df_query(f"SELECT * FROM {table}")

def db_save_trayectos(df):
    """Guarda los trayectos manteniendo el esquema de la tabla."""
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM trayectos")
        c.executemany("""
            INSERT INTO trayectos (origen, destino, km_base, multiplicador_peaje, monto_peaje_base, factor, alimentacion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [(row['origen'], row['destino'], row['km_base'], row['multiplicador_peaje'], 
               row['monto_peaje_base'], float(row.get('factor', 1.0)), float(row.get('alimentacion', 0))) for _, row in df.iterrows()])
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()



# ── AI Configuration & Gemini ──────────────────────────────────────────────
def init_ai():
    """Inicializa la configuración de Gemini AI si la API Key está presente."""
    if "ai" in st.secrets and "gemini_api_key" in st.secrets["ai"]:
        genai.configure(api_key=st.secrets["ai"]["gemini_api_key"])
        return True
    return False

def process_receipt_with_ai(uploaded_file):
    """Procesa una imagen de boleta usando Gemini para extraer datos estructurados."""
    if not init_ai():
        return {"error": "API AI no configurada"}
    
    if not uploaded_file:
        return {"error": "No hay archivo cargado"}
    
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        img_bytes = uploaded_file.getvalue()
        
        prompt = """
        Analiza esta imagen de una boleta o factura chilena.
        Extrae la siguiente información y entrégala ÚNICAMENTE en formato JSON:
        {
            "Detalle": "Nombre del comercio o razón social",
            "Fecha": "YYYY-MM-DD",
            "Doc": "Número de boleta o factura",
            "Monto": número_entero_sin_puntos_ni_simbolos
        }
        Si no encuentras algún dato, deja el campo vacío o en 0 para el monto.
        """
        
        response = model.generate_content([
            prompt,
            {"mime_type": uploaded_file.type, "data": img_bytes}
        ])
        
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        data = json.loads(text.strip())
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}

def process_id_card_with_ai(uploaded_file):
    """Procesa una cédula de identidad para extraer nombre y rut."""
    if not init_ai():
        return {"success": False, "error": "API AI no configurada"}
    
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        img_bytes = uploaded_file.getvalue()
        
        prompt = """
        Analiza esta Cédula de Identidad chilena. 
        1. Extrae el nombre completo.
        2. Extrae el RUT.
        
        Entrega la respuesta ÚNICAMENTE en este formato JSON:
        {
            "nombre": "Nombre Apellido",
            "rut": "12.345.678-9"
        }
        """
        
        response = model.generate_content([
            prompt,
            {"mime_type": uploaded_file.type, "data": img_bytes}
        ])
        
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        res = json.loads(text.strip())
        
        return {"success": True, "data": res}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def db_update_user_full(uid, nombre, email, rut, cc, roles_str, email_jefatura=None):
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE usuarios SET 
            nombre=?, email=?, rut=?, centro_costo=?, role=?, email_jefatura=?, username=?
            WHERE id=?
        """, (nombre, email, rut, cc, roles_str, email_jefatura, email, uid))
        
        roles_list = [r.strip() for r in roles_str.split(',') if r.strip()]
        db_sync_jefatura_role(email, nombre, roles_list, conn=conn)
        
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()

