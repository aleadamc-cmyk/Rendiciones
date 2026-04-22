"""
utils.py — Módulo compartido: PDF, email, base de datos
HGT Chile Logistics · Rendición de Gastos
"""
import os, json, base64, sqlite3, smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.header import Header
from io import BytesIO
import pandas as pd
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

# ── Clase PDF ─────────────────────────────────────────────────────────────
class PDFHGT(FPDF):
    def header(self):
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, 13, 8, 40)
        self.set_y(25)
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'RENDICIÓN DE GASTOS', 0, 1, 'C')
        self.set_font('Helvetica', 'B', 9)
        self.set_xy(163, 25)
        self.cell(40, 10, 'PESOS CHILENOS', 0, 1, 'R')
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
    p_format = 'letter' if tr <= 18 else (216, 330)

    pdf = PDFHGT(orientation='P', unit='mm', format=p_format)
    pdf.set_left_margin(13); pdf.set_right_margin(13)
    pdf.set_auto_page_break(auto=True, margin=15)
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
    pdf.cell(47.5, 6, 'Nombre:', 'LTB'); pdf.cell(47.5, 6, clean(data['nombre']), 'RTB')
    pdf.cell(47.5, 6, 'Rut:', 'LTB'); pdf.cell(47.5, 6, clean(data['rut']), 'RTB', 1)
    pdf.cell(47.5, 6, 'Centro de costo:', 'LTB'); pdf.cell(0, 6, clean(data['centro_costo']), 'RTB', 1)
    pdf.ln(4)

    # -- Comisión --
    pdf.draw_section_header('Detalle de Comisión de Servicios')
    pdf.set_font('Helvetica', 'B', 7)
    for label, w in [('desde oficina / a localidad / traslado', 60), ('desde oficina', 43.3),
                      ('a localidad', 43.3), ('Fecha Inicio', 21.7), ('Fecha Término', 21.7)]:
        pdf.cell(w, 5, label, 1, 0, 'C')
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
    def draw_concept_table(title, items, total_label, total_val):
        pdf.draw_section_header(title); pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(70, 5, 'Lugar / Detalle', 1)
        pdf.cell(40, 5, 'Fecha Docto', 1, 0, 'C')
        pdf.cell(40, 5, 'N° Documento', 1, 0, 'C')
        pdf.cell(40, 5, 'Monto $', 1, 1, 'C')
        pdf.set_font('Helvetica', '', 8)
        for _, row in items.iterrows():
            if not str(row.get('Detalle', '')).strip() and not row.get('Monto'):
                continue
            pdf.cell(70, 5, clean(row.get('Detalle', '')), 1)
            pdf.cell(40, 5, fmt_date(row.get('Fecha', '')), 1, 0, 'C')
            pdf.cell(40, 5, clean(row.get('Doc', '')), 1, 0, 'C')
            pdf.cell(40, 5, format_curr(row.get('Monto', 0)), 1, 1, 'R')
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(150, 6, total_label, 1, 0, 'R', fill=True)
        pdf.cell(40, 6, format_curr(total_val), 1, 1, 'R')
        pdf.ln(3)

    draw_concept_table('ALOJAMIENTO',   data['df_alojamiento'],  'SUBTOTAL (B)', data['st_alojamiento'])
    draw_concept_table('ALIMENTACIÓN',  data['df_alimentacion'], 'SUBTOTAL (C)', data['st_alimentacion'])
    draw_concept_table('OTROS GASTOS',  data['df_otros'],        'SUBTOTAL (D)', data['st_otros'])

    td    = data['st_alojamiento'] + data['st_alimentacion'] + data['st_otros']
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

    # -- Firmas --
    firma_y = pdf.h - 22

    # Firma Funcionario (x=13, celda 65mm)
    firma_bytes = data.get('firma_bytes')
    if firma_bytes:
        try:
            from PIL import Image
            fs = BytesIO(firma_bytes)
            with Image.open(fs) as fimg:
                fw, fh = fimg.size
            scale = min(55 / fw, 18 / fh)
            fw2, fh2 = fw * scale, fh * scale
            fs.seek(0)
            pdf.image(fs, x=13 + (65 - fw2) / 2, y=firma_y - fh2 - 1, w=fw2, h=fh2)
        except Exception:
            pass

    # Firma Jefe Directo (x=163, celda 40mm)
    firma_jefe_bytes = data.get('firma_jefe_bytes')
    if firma_jefe_bytes:
        try:
            from PIL import Image
            js = BytesIO(firma_jefe_bytes)
            with Image.open(js) as jimg:
                jw, jh = jimg.size
            scale = min(30 / jw, 18 / jh)
            jw2, jh2 = jw * scale, jh * scale
            js.seek(0)
            pdf.image(js, x=163 + (40 - jw2) / 2, y=firma_y - jh2 - 1, w=jw2, h=jh2)
        except Exception:
            pass

    pdf.set_xy(13, firma_y); pdf.set_font('Helvetica', '', 8)
    pdf.cell(65, 5, data.get('fecha_rendicion', ''), 'T', 0, 'C')
    pdf.cell(10, 5, '', 0, 0)
    pdf.cell(65, 5, 'Firma funcionario', 'T', 0, 'C')
    pdf.cell(10, 5, '', 0, 0)
    pdf.cell(40, 5, 'Firma Jefe Directo', 'T', 1, 'C')

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
    conn = sqlite3.connect(DB_PATH)
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
            centro_costo TEXT, fecha TEXT, mes INTEGER, año INTEGER,
            total REAL, status TEXT DEFAULT 'pendiente',
            pdf_filename TEXT, data_json TEXT, pdf_aprobado BLOB,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_aprobacion TIMESTAMP
        )
    """)
    conn.commit(); conn.close()


def _df_to_json(df):
    df2 = df.copy()
    for col in df2.select_dtypes(include=['datetime64[ns]', 'datetime64[ns, UTC]']).columns:
        df2[col] = df2[col].apply(lambda v: v.strftime('%Y-%m-%d') if pd.notna(v) else '')
    return df2.to_json()


def _read_df(json_str, date_cols=None):
    try:
        df = pd.read_json(json_str)
        if date_cols:
            for col in date_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame()


def serialize_data(data):
    return json.dumps({
        'nombre':           data['nombre'],
        'rut':              data['rut'],
        'email_funcionario':data.get('email_funcionario', ''),
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
        'firma_bytes':      (base64.b64encode(data['firma_bytes']).decode()
                             if data.get('firma_bytes') else None),
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
        'centro_costo':     sd['centro_costo'],
        'anticipo':         sd['anticipo'],
        'fecha_anticipo':   fa,
        'df_comision':      _read_df(sd['df_comision'],     ['Fecha Inicio', 'Fecha Término']),
        'df_alojamiento':   _read_df(sd['df_alojamiento'],  ['Fecha']),
        'df_alimentacion':  _read_df(sd['df_alimentacion'], ['Fecha']),
        'df_otros':         _read_df(sd['df_otros'],        ['Fecha']),
        'st_alojamiento':   sd['st_alojamiento'],
        'st_alimentacion':  sd['st_alimentacion'],
        'st_otros':         sd['st_otros'],
        'fecha_rendicion':  sd['fecha_rendicion'],
        'firma_bytes':      (base64.b64decode(sd['firma_bytes'])
                             if sd.get('firma_bytes') else None),
        'receipt_photos':   [base64.b64decode(p) for p in sd.get('receipt_photos', [])],
    }


def db_submit_rendicion(data):
    """Guarda una rendición en estado 'pendiente' y devuelve el ID."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    now  = datetime.now()
    total = data['st_alojamiento'] + data['st_alimentacion'] + data['st_otros']
    pdf_filename = f"Rendicion_HGT_{data['nombre']}_{data['fecha_rendicion']}.pdf"
    c.execute("""
        INSERT INTO rendiciones_workflow
        (nombre, rut, email_funcionario, centro_costo, fecha, mes, año,
         total, status, pdf_filename, data_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?)
    """, (data['nombre'], data['rut'], data.get('email_funcionario', ''),
          data['centro_costo'], now.strftime("%Y-%m-%d"), now.month, now.year,
          float(total), pdf_filename, serialize_data(data)))
    new_id = c.lastrowid
    conn.commit(); conn.close()
    return new_id


def db_get_pending():
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql_query(
        "SELECT id, nombre, rut, email_funcionario, centro_costo, total, fecha_registro "
        "FROM rendiciones_workflow WHERE status='pendiente' ORDER BY fecha_registro DESC", conn)
    conn.close()
    return df


def db_get_all():
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql_query(
        "SELECT id, nombre, rut, centro_costo, total, status, fecha_registro "
        "FROM rendiciones_workflow ORDER BY fecha_registro DESC", conn)
    conn.close()
    return df


def db_get_rendicion(rid):
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT data_json, pdf_filename, email_funcionario, nombre "
              "FROM rendiciones_workflow WHERE id=?", (rid,))
    row = c.fetchone()
    conn.close()
    if row:
        return deserialize_data(row[0]), row[1], row[2], row[3]
    return None, None, None, None


def db_approve(rid, pdf_bytes):
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("UPDATE rendiciones_workflow SET status='aprobado', "
              "pdf_aprobado=?, fecha_aprobacion=CURRENT_TIMESTAMP WHERE id=?",
              (pdf_bytes, rid))
    conn.commit(); conn.close()


def db_reject(rid):
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("UPDATE rendiciones_workflow SET status='rechazado', "
              "fecha_aprobacion=CURRENT_TIMESTAMP WHERE id=?", (rid,))
    conn.commit(); conn.close()
