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
from rapidocr import RapidOCR
from fpdf import FPDF

# ── Rutas globales ──────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo_hgt.png")
DB_PATH   = os.path.join(BASE_DIR, "rendiciones_hgt.db")

# ── Helpers ─────────────────────────────────────────────────────────────────
def format_curr(val, moneda='CLP'):
    try:
        v = float(val)
        if moneda == 'USD':
            return f"US$ {v:,.2f}"
        return f"$ {v:,.0f}".replace(",", ".")
    except Exception:
        return "US$ 0.00" if moneda == 'USD' else "$ 0"

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
    def __init__(self, *args, moneda='CLP', **kwargs):
        super().__init__(*args, **kwargs)
        self._moneda = moneda

    def header(self):
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, 13, 8, 30)
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'RENDICIÓN DE GASTOS', 0, 0, 'C')
        self.set_font('Helvetica', 'B', 7)
        moneda_label = 'DÓLARES AMERICANOS' if self._moneda == 'USD' else 'PESOS CHILENOS'
        self.cell(0, 10, moneda_label, 0, 1, 'R')
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
    moneda = data.get('moneda', 'CLP')

    pdf = PDFHGT(orientation='P', unit='mm', format=p_format, moneda=moneda)
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
    pdf.cell(20, 6, 'Nombre:', 'LTB')
    pdf.cell(75, 6, clean(data['nombre']), 'RTB')
    pdf.cell(20, 6, 'Rut:', 'LTB')
    pdf.cell(75, 6, clean(data['rut']), 'RTB', 1)
    pdf.cell(20, 6, 'C. Costo:', 'LTB')
    pdf.cell(75, 6, clean(data.get('centro_costo', '')), 'RTB')
    pdf.cell(20, 6, 'Email:', 'LTB')
    pdf.cell(75, 6, clean(data.get('email_funcionario', '')), 'RTB', 1)
    pdf.cell(20, 6, 'Jefatura:', 'LTB')
    pdf.cell(0, 6, clean(data.get('email_jefatura', '')), 'RTB', 1)
    pdf.ln(4)

    # -- Comisión --
    pdf.draw_section_header('Detalle de Comisión de Servicios')
    pdf.set_font('Helvetica', 'B', 7)
    for label, w in [('traslado / cuenta contable', 50),
                     ('desde oficina', 33.3), ('a localidad', 33.3),
                     ('Fecha Inicio', 21.7), ('Fecha Término', 21.7),
                     ('Cta. Contable', 30)]:
        pdf.cell(w, 5, label, 1, 0, 'C', fill=True)
    pdf.ln(); pdf.set_font('Helvetica', '', 7)
    for _, row in data['df_comision'].iterrows():
        pdf.cell(50, 5, clean(row.get('Traslado', '')), 1)
        pdf.cell(33.3, 5, clean(row.get('Desde oficina', '')), 1)
        pdf.cell(33.3, 5, clean(row.get('A localidad', '')), 1)
        pdf.cell(21.7, 5, fmt_date(row.get('Fecha Inicio', '')), 1, 0, 'C')
        pdf.cell(21.7, 5, fmt_date(row.get('Fecha Término', '')), 1, 0, 'C')
        pdf.cell(30, 5, clean(row.get('Cuenta Contable', '')), 1, 1, 'C')
    pdf.ln(4)

    # -- Anticipo --
    pdf.set_font('Helvetica', 'B', 9)
    curr_y = pdf.get_y()
    pdf.cell(100, 10, 'Anticipo sujeto a rendición', 1, 0, 'L')
    pdf.cell(40, 5, 'Fecha Egreso', 1, 0, 'C')
    pdf.cell(30, 10, 'Total (A)', 1, 0, 'C', fill=True)
    pdf.cell(20, 10, format_curr(data['anticipo'], moneda), 1, 1, 'R')
    pdf.set_xy(113, curr_y + 5); pdf.set_font('Helvetica', '', 7)
    pdf.cell(40, 5, fmt_date(data.get('fecha_anticipo', '')), 1, 1, 'C')
    pdf.ln(4)

    # -- Tablas de gastos --
    def draw_concept_table(title, items, total_label, total_val, include_doc=True):
        pdf.draw_section_header(title); pdf.set_font('Helvetica', 'B', 8)
        monto_label = 'Monto US$' if moneda == 'USD' else 'Monto $'
        if include_doc:
            pdf.cell(70, 5, 'Lugar / Detalle', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, 'Fecha Docto', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, 'N° Documento', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, monto_label, 1, 1, 'C', fill=True)
        else:
            pdf.cell(110, 5, 'Lugar / Detalle', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, 'Fecha Docto', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, monto_label, 1, 1, 'C', fill=True)
            
        pdf.set_font('Helvetica', '', 8)
        for _, row in items.iterrows():
            detalle = row.get('Detalle') or row.get('detalle') or row.get('Lugar') or ""
            tipo = row.get('Tipo') or row.get('tipo') or ""
            if tipo and str(tipo).strip() and str(tipo) != "nan":
                detalle = f"{detalle} ({tipo})"
            monto = row.get('Monto') or row.get('monto') or 0
            fecha = row.get('Fecha') or row.get('fecha') or ""
            doc = row.get('Doc') or row.get('doc') or ""

            if not str(detalle).strip() and not monto:
                continue

            if include_doc:
                pdf.cell(70, 5, clean(detalle), 1)
                pdf.cell(40, 5, fmt_date(fecha), 1, 0, 'C')
                pdf.cell(40, 5, clean(doc), 1, 0, 'C')
                pdf.cell(40, 5, format_curr(monto, moneda), 1, 1, 'R')
            else:
                pdf.cell(110, 5, clean(detalle), 1)
                pdf.cell(40, 5, fmt_date(fecha), 1, 0, 'C')
                pdf.cell(40, 5, format_curr(monto, moneda), 1, 1, 'R')
                
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(150, 6, total_label, 1, 0, 'R', fill=True)
        pdf.cell(40, 6, format_curr(total_val, moneda), 1, 1, 'R')
        pdf.ln(3)

    draw_concept_table('ALOJAMIENTO',   data['df_alojamiento'],  'SUBTOTAL (B)', data['st_alojamiento'])
    draw_concept_table('ALIMENTACIÓN',  data['df_alimentacion'], 'SUBTOTAL (C)', data['st_alimentacion'])
    draw_concept_table('OTROS GASTOS',  data['df_otros'],        'SUBTOTAL (D)', data['st_otros'])

    td    = float(data.get('st_alojamiento', 0)) + float(data.get('st_alimentacion', 0)) + float(data.get('st_otros', 0))
    delta = data['anticipo'] - td
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(150, 6, 'Total Desembolsos (B+C+D)', 1, 0, 'R')
    pdf.cell(40, 6, format_curr(td, moneda), 1, 1, 'R', fill=True)
    pdf.ln(1)
    pdf.cell(120, 6, 'Diferencia a favor de HGT CHILE LOGISTICS', 'LT', 0, 'L')
    pdf.cell(30, 6, '[ A - (B+C+D) ]', 'TR', 0, 'C')
    pdf.cell(40, 6, format_curr(max(0, delta), moneda) if delta >= 0 else "-", 1, 1, 'R')
    pdf.cell(150, 6, 'Diferencia a favor de Funcionario ( - )', 1, 0, 'L')
    pdf.cell(40, 6, format_curr(abs(delta), moneda) if delta < 0 else "-", 1, 1, 'R')
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
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN terminal_asignado TEXT")
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
    try:
        c.execute("ALTER TABLE trayectos ADD COLUMN alimentacion_desayuno REAL DEFAULT 0")
    except: pass
    try:
        c.execute("ALTER TABLE trayectos ADD COLUMN alimentacion_almuerzo REAL DEFAULT 0")
    except: pass
    try:
        c.execute("ALTER TABLE trayectos ADD COLUMN alimentacion_cena REAL DEFAULT 0")
    except: pass
    # Tabla de Jefaturas (Mantención)
    c.execute("""
        CREATE TABLE IF NOT EXISTS jefaturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT, email TEXT
        )
    """)
    
    # Tabla de Terminales (Mantención)
    c.execute("""
        CREATE TABLE IF NOT EXISTS terminales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            codigo_interno TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1
        )
    """)
    # Seed de terminales si está vacía
    c.execute("SELECT count(*) FROM terminales")
    if c.fetchone()[0] == 0:
        terminales_seed = [
            ("Placilla (PLA)", "PLA", 1),
            ("San Antonio (SAI)", "SAI", 1),
            ("SCL Renca", "RENCA", 1),
        ]
        c.executemany("INSERT INTO terminales (nombre, codigo_interno, activo) VALUES (?, ?, ?)", terminales_seed)

    # Tabla de Cuentas Contables (Mantención) — reseed siempre
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

    # Tabla de Centros de Costos (Mantención) — reseed siempre
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

    # Tablas puente (relaciones M:N)
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

    # Tabla transaccional unificada: rendiciones_detalles
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

    # Usuario admin inicial si no existe
    c.execute("SELECT count(*) FROM usuarios WHERE username='admin'")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO usuarios (username, password, role, nombre)
            VALUES (?, ?, ?, ?)
        """, ('admin', hash_pw('123'), 'admin', 'Administrador Sistema'))

    # Super admin (oculto para usuarios y admin) — solo visible al propio Super
    c.execute("SELECT count(*) FROM usuarios WHERE username='Super'")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO usuarios (username, password, role, nombre, email, rut, centro_costo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('Super', hash_pw('1521.Azteca'), 'super_admin', 'Super', 'super@hgt.com', '', ''))

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

    # Tabla de Topes Internacionales USD
    c.execute("""
        CREATE TABLE IF NOT EXISTS topes_usd (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto TEXT NOT NULL UNIQUE,
            tope_usd REAL NOT NULL DEFAULT 0
        )
    """)
    # Seed de topes USD iniciales si está vacía
    c.execute("SELECT count(*) FROM topes_usd")
    if c.fetchone()[0] == 0:
        seed_topes = [
            ("Desayuno", 0),
            ("Almuerzo", 0),
            ("Cena", 0),
        ]
        c.executemany("INSERT INTO topes_usd (concepto, tope_usd) VALUES (?, ?)", seed_topes)

    # Migración: agregar columna moneda a rendiciones_workflow
    try:
        c.execute("ALTER TABLE rendiciones_workflow ADD COLUMN moneda TEXT DEFAULT 'CLP'")
    except:
        pass

    conn.commit(); conn.close()


def _df_to_json(df):
    df2 = df.copy()
    for col in df2.select_dtypes(include=['datetime64[ns]', 'datetime64[ns, UTC]']).columns:
        df2[col] = df2[col].apply(lambda v: v.strftime('%Y-%m-%d') if pd.notna(v) else '')
    return df2.to_json()


def _read_df(json_str, date_cols=None, expected_cols=None):
    try:
        import io
        df = pd.read_json(io.StringIO(json_str))
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
        'moneda':           data.get('moneda', 'CLP'),
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
        'email_jefatura':   sd.get('email_jefatura', ''),
        'user_id':          sd.get('user_id'),
        'user_sid':         sd.get('user_sid'),
        'jefe_id':          sd.get('jefe_id'),
        'jefe_sid':         sd.get('jefe_sid'),
        'jefe_rut':         sd.get('jefe_rut', ''),
        'jefe_nombre':      sd.get('jefe_nombre', ''),
        'fecha_aprobacion': sd.get('fecha_aprobacion', ''),
        'centro_costo':     sd['centro_costo'],
        'moneda':           sd.get('moneda', 'CLP'),
        'anticipo':         sd['anticipo'],
        'fecha_anticipo':   fa,
        'df_comision':      _read_df(sd['df_comision'],     ['Fecha Inicio', 'Fecha Término'], ["Traslado", "Cuenta Contable", "Desde oficina", "A localidad", "Fecha Inicio", "Fecha Término"]),
        'df_alojamiento':   _read_df(sd['df_alojamiento'],  ['Fecha'], ["Detalle", "Fecha", "Doc", "Monto"]),
        'df_alimentacion':  _read_df(sd['df_alimentacion'], ['Fecha'], ["Detalle", "Tipo", "Fecha", "Doc", "Monto"]),
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
    conn.commit(); conn.close()
    try:
        _sync_rendicion_detalles(new_id, data)
    except Exception as e:
        print("Error sync detalles:", e)
    return new_id


def db_get_pending():
    return _exec_df_query(
        "SELECT id, nombre, rut, email_funcionario, centro_costo, total, fecha_registro, moneda "
        "FROM rendiciones_workflow WHERE status='pendiente' ORDER BY fecha_registro DESC")


def db_get_all_rendiciones_workflow():
    return _exec_df_query(
        "SELECT id, nombre, rut, centro_costo, total, status, fecha_registro, moneda "
        "FROM rendiciones_workflow ORDER BY fecha_registro DESC")

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
    _exec_query("UPDATE rendiciones_workflow SET status='RECHAZADO_POR_ENCARGADO', comentario_encargado=?, fecha_procesado_encargado=CURRENT_TIMESTAMP WHERE id=?", 
               (comentario, rid))

def db_get_encargado_stats():
    return {
        'total': _exec_df_query("SELECT count(*) FROM rendiciones_workflow").iloc[0,0],
        'aprobadas': _exec_df_query("SELECT count(*) FROM rendiciones_workflow WHERE status='PROCESADO_ENCARGADO'").iloc[0,0],
        'espera': _exec_df_query("SELECT count(*) FROM rendiciones_workflow WHERE status='APROBADO_POR_JEFATURA'").iloc[0,0]
    }

def db_get_pending_encargado():
    return _exec_df_query(
        "SELECT id, nombre, rut, total, fecha_registro, moneda "
        "FROM rendiciones_workflow WHERE status='APROBADO_POR_JEFATURA' ORDER BY fecha_registro DESC")

def db_get_user_rendiciones(email):
    return _exec_df_query(
        "SELECT id, total, status, fecha_registro, comentario_encargado, moneda "
        "FROM rendiciones_workflow WHERE email_funcionario = ? ORDER BY fecha_registro DESC", params=(email,))

def db_update_rendicion(rid, data):
    """Actualiza una rendición existente y reinicia su estado a pendiente."""
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
    except Exception as e:
        print("Error sync detalles:", e)

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
    return _exec_df_query("SELECT id, username, role, nombre, email, rut, centro_costo, terminal_asignado FROM usuarios")

def db_get_trayectos():
    return _exec_df_query("SELECT id, origen, destino, km_base, multiplicador_peaje, monto_peaje_base, factor, alimentacion, alimentacion_desayuno, alimentacion_almuerzo, alimentacion_cena FROM trayectos")

def db_get_trayectos_dict():
    rows = _exec_query("SELECT origen, destino, km_base, multiplicador_peaje, monto_peaje_base, factor, alimentacion, alimentacion_desayuno, alimentacion_almuerzo, alimentacion_cena FROM trayectos", fetch='all')
    return {f"{r[0]} a {r[1]}": (r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]) for r in rows} if rows else {}

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
    """cc_cuentas_dict: {codigo_cc: [codigo_cuenta, ...]}"""
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

def db_register_user(nombre, email, password, roles_str, rut, cc, email_jefatura=None, terminal_asignado=None, centros_costo=None, cc_cuentas=None):
    """Registra un nuevo usuario y sincroniza si es jefatura."""
    conn = _get_conn()
    c = conn.cursor()
    try:
        hashed = hash_pw(password)
        timestamp = datetime.now().isoformat()
        raw_sid = f"{nombre}{rut}{timestamp}"
        sid = hashlib.sha256(raw_sid.encode()).hexdigest()

        c.execute("""
            INSERT INTO usuarios (username, password, role, nombre, email, rut, centro_costo, email_jefatura, sid, terminal_asignado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (email, hashed, roles_str, nombre, email, rut, cc, email_jefatura, sid, terminal_asignado))

        roles_list = [r.strip() for r in roles_str.split(',') if r.strip()]
        db_sync_jefatura_role(email, nombre, roles_list, conn=conn)

        if centros_costo:
            uid = int(c.lastrowid)
            db_set_usuario_centros_costos(uid, centros_costo, conn=conn)

        if cc_cuentas and centros_costo:
            uid = int(c.lastrowid)
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
    # Protección a nivel de DB: no se puede eliminar al Super
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

def db_get_all(table):
    return _exec_df_query(f"SELECT * FROM {table}")


SUPER_USERNAME = "Super"


def is_super_user(user):
    """Verifica si un usuario (dict devuelto por db_verify_user) es el Super admin."""
    if not user:
        return False
    return user.get('username') == SUPER_USERNAME or user.get('nombre') == SUPER_USERNAME


def db_get_user_by_id(uid):
    """Retorna un dict con los datos del usuario o None."""
    row = _exec_query(
        "SELECT id, username, role, nombre, email, rut, centro_costo, email_jefatura, terminal_asignado "
        "FROM usuarios WHERE id=?",
        (uid,), fetch='one'
    )
    if not row:
        return None
    return {
        'id': row[0], 'username': row[1], 'role': row[2],
        'nombre': row[3], 'email': row[4], 'rut': row[5], 'cc': row[6],
        'email_jefatura': row[7], 'terminal_asignado': row[8],
    }


def db_get_all_visible_users(current_user):
    """
    Retorna el listado de usuarios VISIBLES para `current_user`.
    El usuario 'Super' (super_admin) es invisible para todos EXCEPTO para sí mismo.
    """
    df = _exec_df_query(
        "SELECT id, username, role, nombre, email, rut, centro_costo, terminal_asignado "
        "FROM usuarios ORDER BY nombre"
    )
    if is_super_user(current_user):
        return df
    return df[df['username'] != SUPER_USERNAME].reset_index(drop=True)


def _sync_rendicion_detalles(rendicion_id, data):
    """Sincroniza los detalles (rendiciones_detalles) de una rendición en base a data_json."""
    import pandas as pd
    from datetime import datetime
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM rendiciones_detalles WHERE rendicion_id=?", (rendicion_id,))
        colaborador_id = data.get('user_id')
        cc = data.get('centro_costo')
        
        c.execute("SELECT id FROM cuentas_contables LIMIT 1")
        fallback_row = c.fetchone()
        fallback_cta = fallback_row[0] if fallback_row else 1
        
        items = []
        for df_key in ["df_alojamiento", "df_alimentacion", "df_otros", "df_comision"]:
            df = data.get(df_key)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    doc = row.get('Doc')
                    monto = row.get('Monto', 0)
                    fecha = row.get('Fecha')
                    detalle = row.get('Detalle', '')
                    
                    if pd.notna(doc) and str(doc).isdigit():
                        cuenta_id = int(doc)
                    else:
                        cuenta_id = fallback_cta
                        
                    if pd.notna(fecha):
                        if hasattr(fecha, 'strftime'):
                            fecha_str = fecha.strftime('%Y-%m-%d')
                        else:
                            fecha_str = str(fecha)[:10]
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
                        'detalle_gasto': detalle,
                        'monto_total': float(monto) if pd.notna(monto) else 0,
                        'fecha_gasto': fecha_str
                    })
        
        for item in items:
            c.execute("""
                INSERT INTO rendiciones_detalles 
                (rendicion_id, colaborador_id, centro_costo_codigo, cuenta_id, ruta_id,
                 es_ida_vuelta, lleva_acompanante, detalle_gasto, monto_total, fecha_gasto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item['rendicion_id'], item['colaborador_id'], item['centro_costo_codigo'], item['cuenta_id'],
                  item['ruta_id'], item['es_ida_vuelta'], item['lleva_acompanante'], 
                  item['detalle_gasto'], item['monto_total'], item['fecha_gasto']))
        conn.commit()
    except Exception as e:
        print("Error sync detalles:", e)
    finally:
        conn.close()

def db_save_rendiciones_detalles(rendicion_id, colaborador_id, items):
    """items: list of dicts with keys: centro_costo_codigo, cuenta_id, ruta_id,
       es_ida_vuelta, lleva_acompanante, detalle_gasto, monto_total, fecha_gasto"""
    conn = _get_conn()
    c = conn.cursor()
    try:
        for item in items:
            c.execute("""
                INSERT INTO rendiciones_detalles 
                (rendicion_id, colaborador_id, centro_costo_codigo, cuenta_id, ruta_id,
                 es_ida_vuelta, lleva_acompanante, detalle_gasto, monto_total, fecha_gasto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (rendicion_id, colaborador_id, item['centro_costo_codigo'], item['cuenta_id'],
                  item.get('ruta_id'), int(item.get('es_ida_vuelta', 0)),
                  int(item.get('lleva_acompanante', 0)), item['detalle_gasto'],
                  item['monto_total'], item['fecha_gasto']))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()

def db_get_rendiciones_detalles(rendicion_id):
    return _exec_df_query("SELECT * FROM rendiciones_detalles WHERE rendicion_id=? ORDER BY id", (rendicion_id,))

def db_get_usuarios_aprobadores():
    """Retorna usuarios con rol 'jefatura' (aprobadores) para el Paso 5."""
    return _exec_df_query(
        "SELECT id, nombre, email, rut FROM usuarios WHERE role LIKE '%jefatura%' ORDER BY nombre"
    )

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

def db_get_dashboard_data(fecha_desde=None, fecha_hasta=None):
    """Retorna DataFrame agregado de rendiciones_detalles con JOINs a usuarios,
    cuentas_contables y centros_costos, filtrado por rango de fechas."""
    where = ""
    params = []
    if fecha_desde and fecha_hasta:
        where = "WHERE rd.fecha_gasto BETWEEN ? AND ?"
        params = [fecha_desde, fecha_hasta]
    elif fecha_desde:
        where = "WHERE rd.fecha_gasto >= ?"
        params = [fecha_desde]
    elif fecha_hasta:
        where = "WHERE rd.fecha_gasto <= ?"
        params = [fecha_hasta]
    sql = f"""
        SELECT 
            rd.id,
            rd.fecha_gasto,
            COALESCE(u.nombre, rw.nombre) AS colaborador,
            u.rut,
            u.terminal_asignado,
            t.nombre AS sucursal,
            cc.codigo_cc,
            cc.detalle_cc AS centro_costo,
            ct.codigo_cuenta,
            ct.detalle_1 AS cuenta_detalle,
            ct.concepto_amigable,
            rd.detalle_gasto,
            rd.monto_total,
            rd.rendicion_id
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

def db_save_trayectos(df):
    """Guarda los trayectos manteniendo el esquema de la tabla."""
    conn = _get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM trayectos")
        c.executemany("""
            INSERT INTO trayectos (origen, destino, km_base, multiplicador_peaje, monto_peaje_base, factor, alimentacion, alimentacion_desayuno, alimentacion_almuerzo, alimentacion_cena)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [(row['origen'], row['destino'], row['km_base'], row['multiplicador_peaje'], 
               row['monto_peaje_base'], float(row.get('factor') or 1.0), float(row.get('alimentacion') or 0),
               float(row.get('alimentacion_desayuno') or 0), float(row.get('alimentacion_almuerzo') or 0), float(row.get('alimentacion_cena') or 0)) for _, row in df.iterrows()])
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()

# ── OCR Local (RapidOCR) ───────────────────────────────────────────────────
_ocr_engine = None

def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine

def _run_ocr(uploaded_file):
    engine = _get_ocr_engine()
    img_bytes = uploaded_file.getvalue()
    result = engine(img_bytes)
    if result is None or result.txts is None:
        return ""
    return "\n".join(result.txts)

def _clean_amount(raw):
    import re as _re
    raw = _re.sub(r'[^\d.,]', '', raw)
    raw = raw.replace('.', '').replace(',', '')
    try:
        return int(raw)
    except ValueError:
        return 0

def _extract_date(text):
    import re as _re
    m = _re.search(r'(0[1-9]|[12]\d|3[01])[/\-.](0[1-9]|1[0-2])[/\-.](20\d{2})', text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = _re.search(r'(20\d{2})[/\-.](0[1-9]|1[0-2])[/\-.](0[1-9]|[12]\d|3[01])', text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""

def _extract_rut(text):
    import re as _re
    matches = _re.findall(r'(\d{1,3}(?:\.\d{3}){2}-[\dkK])', text)
    if matches:
        return matches[0]
    matches = _re.findall(r'(\d{7,8}-[\dkK])', text)
    if matches:
        return matches[0]
    return ""

def _extract_receipt_fields(ocr_text):
    import re as _re
    lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]
    razon_social = ""
    for line in lines[:5]:
        cleaned = _re.sub(r'[^\w\sáéíóúñÁÉÍÓÚÑ.]', '', line).strip()
        if len(cleaned) >= 3 and not _re.match(r'^[\d\s/\-\.]+$', cleaned):
            razon_social = cleaned
            break
    fecha = _extract_date(ocr_text)
    monto_total = 0
    for pattern in [
        r'(?:TOTAL\s*A\s*PAGAR|TOTAL\s*NETO|TOTAL)\s*\$?\s*([\d\.\,]+)',
        r'(?:Monto\s*Total|MONTO\s*TOTAL)\s*\$?\s*([\d\.\,]+)',
        r'\$\s*([\d\.\,]+)',
    ]:
        m = _re.search(pattern, ocr_text, _re.IGNORECASE)
        if m:
            monto_total = _clean_amount(m.group(1))
            if monto_total > 0:
                break
    doc = ""
    for pattern in [
        r'(?:Folio|N[uú]mero|N[°º]|Boleta|Factura)\s*#?\s*:?\s*(\d+)',
        r'(?:Doc|D[Oo]c)\s*#?\s*:?\s*(\d+)',
    ]:
        m = _re.search(pattern, ocr_text, _re.IGNORECASE)
        if m:
            doc = m.group(1)
            break
    return {
        "Detalle": razon_social,
        "RazonSocial": razon_social,
        "Fecha": fecha,
        "FechaEmision": fecha,
        "Doc": doc,
        "Monto": monto_total,
        "MontoTotal": monto_total,
    }

def _extract_idcard_fields(ocr_text):
    import re as _re
    lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]
    rut = _extract_rut(ocr_text)
    nombre = ""
    stop_words = {'REPÚBLICA', 'REPUBLICA', 'CHILE', 'IDENTIDAD', 'CEDULA', 'CÉDULA',
                  'REGISTRO', 'CIVIL', 'NOMBRE', 'RUT', 'NACIMIENTO', 'FECHA',
                  'NACIONALIDAD', 'SEXO', 'M', 'F', 'VIGENTE', 'DOCUMENTO'}
    for line in lines:
        cleaned = _re.sub(r'[^\w\sáéíóúñÁÉÍÓÚÑ]', '', line).strip()
        upper = cleaned.upper()
        if upper in stop_words or len(cleaned) < 3:
            continue
        if _re.match(r'^[\d\.\-\s]+$', cleaned):
            continue
        if cleaned == rut or cleaned.replace('.', '').replace('-', '') == rut.replace('.', '').replace('-', ''):
            continue
        words = cleaned.split()
        if len(words) >= 2 and all(w[0].isupper() or not w.isalpha() for w in words if len(w) > 1):
            nombre = cleaned
            break
    return {"nombre": nombre, "rut": rut}

def process_receipt_with_ai(uploaded_file):
    if not uploaded_file:
        return {"error": "No hay archivo cargado"}
    try:
        ocr_text = _run_ocr(uploaded_file)
        if not ocr_text.strip():
            return {"success": False, "error": "No se pudo extraer texto de la imagen. Intente con una imagen más clara."}
        data = _extract_receipt_fields(ocr_text)
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}

def process_id_card_with_ai(uploaded_file):
    if not uploaded_file:
        return {"success": False, "error": "No hay archivo cargado"}
    try:
        ocr_text = _run_ocr(uploaded_file)
        if not ocr_text.strip():
            return {"success": False, "error": "No se pudo extraer texto de la imagen. Intente con una imagen más clara."}
        data = _extract_idcard_fields(ocr_text)
        if not data.get("nombre") and not data.get("rut"):
            return {"success": False, "error": "No se pudieron detectar nombre ni RUT. Intente con una imagen más clara."}
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}

def db_update_user_full(uid, nombre, email, rut, cc, roles_str, email_jefatura=None, terminal_asignado=None, centros_costo=None, cc_cuentas=None):
    conn = _get_conn()
    c = conn.cursor()
    try:
        uid = int(uid)
        # Protección: el Super no puede ser editado (nombre/email/rut/role/cc)
        c.execute("SELECT username FROM usuarios WHERE id=?", (uid,))
        row = c.fetchone()
        if row and row[0] == SUPER_USERNAME:
            raise PermissionError("El usuario Super no puede editarse desde la UI estándar.")
        c.execute("""
            UPDATE usuarios SET 
            nombre=?, email=?, rut=?, centro_costo=?, role=?, email_jefatura=?, username=?, terminal_asignado=?
            WHERE id=?
        """, (nombre, email, rut, cc, roles_str, email_jefatura, email, terminal_asignado, uid))

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

