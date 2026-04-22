import streamlit as st
import pandas as pd
from fpdf import FPDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.header import Header

from datetime import datetime
import os
import json
import google.generativeai as genai
import sqlite3
import base64


# --- AI Configuration ---
def init_ai():
    if "ai" in st.secrets and "gemini_api_key" in st.secrets["ai"]:
        genai.configure(api_key=st.secrets["ai"]["gemini_api_key"])
        return True
    return False

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect("rendiciones_hgt.db")
    cursor = conn.cursor()
    # Usaremos el RUT como PRIMARY KEY tal como se solicitó para que sea el identificador único.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rendiciones (
            id_rut TEXT PRIMARY KEY,
            nombre TEXT,
            fecha TEXT,
            mes INTEGER,
            año INTEGER,
            centro_costo TEXT,
            total REAL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def db_save_rendicion(nombre, rut, centro_costo, total, fecha_dt):
    try:
        conn = sqlite3.connect("rendiciones_hgt.db")
        cursor = conn.cursor()
        
        # Limpiar RUT (quitar puntos y guión) para usar como ID
        rut_id = rut.replace(".", "").replace("-", "").strip()
        
        # Extraer mes y año de la fecha de rendición
        mes = fecha_dt.month
        año = fecha_dt.year
        fecha_str = fecha_dt.strftime("%Y-%m-%d")
        
        # Guardar (REPLACE para que el RUT sea el identificador único)
        cursor.execute("""
            INSERT OR REPLACE INTO rendiciones (id_rut, nombre, fecha, mes, año, centro_costo, total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (rut_id, nombre, fecha_str, mes, año, centro_costo, float(total)))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"⚠️ Error al guardar en base de datos: {e}")
        return False

# Inicializar DB al cargar
init_db()

def process_receipt_with_ai(uploaded_file):
    if not init_ai():
        st.error("❌ No se encontró la GEMINI_API_KEY en secrets.toml")
        return None
    
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        
        # Prepare the image
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
        
        # Extract JSON from response
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        return json.loads(text.strip())
    except Exception as e:
        st.error(f"❌ Error al procesar con IA: {e}")
        return None

# Page configuration
st.set_page_config(page_title="HGT - Rendición de Gastos", page_icon="🏢", layout="wide")

# --- Constants & Fixed Data ---
BANK_DETAILS = {
    "Banco": "BCI",
    "Cuenta corriente": "10670505",
    "Rut": "76729932-K",
    "Mail": "pagos@hgt.cl"
}

# Localización del logo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo_hgt.png")

# --- CSS for modern and responsive look ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

    /* Tipografía Corporativa y Estructura general */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    .main { background-color: #ffffff; }
    
    /* Minimizar espacios y paddings nativos de Streamlit */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    header[data-testid="stHeader"] { display: none !important; }
    
    /* Comprimir elementos verticales */
    hr { margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; }
    div[data-testid="stExpander"] { margin-bottom: 0.2rem !important; }
    h3 { padding-bottom: 0.2rem !important; margin-bottom: 0px !important; }
    
    /* Botones más grandes para pantallas táctiles */
    .stButton>button, .stDownloadButton>button { 
        border-radius: 6px; 
        font-weight: bold; 
        padding: 0.5rem 1rem;
        min-height: 45px;
        width: 100%;
        border: 1px solid #212a37;
    }
    
    .stButton>button { background-color: #212a37; color: white; }
    .stButton>button[kind="primary"] { background-color: #ff6600; color: white; border-color: #ff6600; }
    .stDownloadButton>button { background-color: #ff6600; color: white; border-color: #ff6600; }
    
    /* Métricas con mejor contraste */
    .stMetric { 
        background-color: #ffffff; 
        padding: 5px 15px; 
        border-radius: 10px; 
        border: 1px solid #dadadf;
        margin-bottom: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Ajustes específicos para móviles */
    @media (max-width: 768px) {
        .stTitle { 
            font-size: 1.6rem !important; 
            text-align: center; 
        }
        .stImage {
            display: flex;
            justify-content: center;
            margin-bottom: -20px;
        }
        div[data-testid="stExpander"] {
            margin-left: -5px;
            margin-right: -5px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

class PDFHGT(FPDF):
    def header(self):
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, 13, 8, 40) # Logo más pequeño y alineado con margen
        
        # Título centrado
        self.set_y(25) 
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'RENDICIÓN DE GASTOS', 0, 1, 'C')
        
        # Información "PESOS CHILENOS" a la derecha
        self.set_font('Helvetica', 'B', 9)
        self.set_xy(163, 25) 
        self.cell(40, 10, 'PESOS CHILENOS', 0, 1, 'R')
        
        # Subtítulo empresa
        self.set_xy(13, 33)
        self.set_font('Helvetica', 'B', 8)
        self.cell(0, 5, 'HGT Chile Logistics', 0, 1, 'L')
        self.ln(2)

    def draw_section_header(self, title):
        self.set_fill_color(240, 240, 240); self.set_font('Helvetica', 'B', 9); self.cell(0, 6, title, 1, 1, 'L', fill=True)

def format_curr(val):
    try: return f"$ {float(val):,.0f}".replace(",", ".")
    except: return "$ 0"

def generate_hgt_pdf(data):
    # Calcular filas totales para elegir tamaño de hoja
    tr = len(data['df_comision']) + len(data['df_alojamiento']) + len(data['df_alimentacion']) + len(data['df_otros'])
    # Si hay muchas filas (>18), usamos Oficio (216x330mm), sino Carta (216x279mm)
    p_format = 'letter' if tr <= 18 else (216, 330)
    
    pdf = PDFHGT(orientation='P', unit='mm', format=p_format)
    # Margen izquierdo de 13mm para centrar tablas de 190mm en Letter/Oficio (216mm)
    pdf.set_left_margin(13)
    pdf.set_right_margin(13)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    # Utility to clean text for FPDF standard fonts
    def clean(t):
        return str(t).replace('→', ' a ').encode('latin-1', 'replace').decode('latin-1')

    pdf.draw_section_header('Funcionario que rinde')
    pdf.set_font('Helvetica', '', 8)
    pdf.cell(47.5, 6, 'Nombre:', 'LTB'); pdf.cell(47.5, 6, clean(data['nombre']), 'RTB'); pdf.cell(47.5, 6, 'Rut:', 'LTB'); pdf.cell(47.5, 6, clean(data['rut']), 'RTB', 1)
    pdf.cell(47.5, 6, 'Centro de costo:', 'LTB'); pdf.cell(0, 6, clean(data['centro_costo']), 'RTB', 1)
    pdf.ln(4)
    
    pdf.draw_section_header('Detalle de Comisión de Servicios')
    pdf.set_font('Helvetica', 'B', 7)
    cols = [('desde oficina / a localidad / traslado', 60), ('desde oficina', 43.3), ('a localidad', 43.3), ('Fecha Inicio', 21.7), ('Fecha Término', 21.7)]
    for label, w in cols: pdf.cell(w, 5, label, 1, 0, 'C')
    pdf.ln()
    pdf.set_font('Helvetica', '', 7)
    for _, row in data['df_comision'].iterrows():
        pdf.cell(60, 5, clean(row.get('Traslado','')), 1)
        pdf.cell(43.3, 5, clean(row.get('Desde oficina','')), 1)
        pdf.cell(43.3, 5, clean(row.get('A localidad','')), 1)
        f_i = row['Fecha Inicio'].strftime('%d/%m/%Y') if hasattr(row['Fecha Inicio'], 'strftime') and not pd.isnull(row['Fecha Inicio']) else str(row['Fecha Inicio'])
        f_t = row['Fecha Término'].strftime('%d/%m/%Y') if hasattr(row['Fecha Término'], 'strftime') and not pd.isnull(row['Fecha Término']) else str(row['Fecha Término'])
        pdf.cell(21.7, 5, f_i, 1, 0, 'C'); pdf.cell(21.7, 5, f_t, 1, 1, 'C')
    pdf.ln(4)
    
    pdf.set_font('Helvetica', 'B', 9)
    # Tabla Anticipo (Total 190mm)
    curr_y = pdf.get_y()
    pdf.cell(100, 10, 'Anticipo sujeto a rendición', 1, 0, 'L')
    pdf.cell(40, 5, 'Fecha Egreso', 1, 0, 'C')
    pdf.cell(30, 10, 'Total (A)', 1, 0, 'C', fill=True)
    pdf.cell(20, 10, format_curr(data['anticipo']), 1, 1, 'R')
    
    # Celda de fecha debajo de 'Fecha Egreso'
    pdf.set_xy(113, curr_y + 5) # x=113 es margen 13 + 100
    pdf.set_font('Helvetica', '', 7)
    f_e = data['fecha_anticipo'].strftime('%d/%m/%Y') if hasattr(data['fecha_anticipo'], 'strftime') and not pd.isnull(data['fecha_anticipo']) else str(data['fecha_anticipo'])
    pdf.cell(40, 5, f_e, 1, 1, 'C'); pdf.ln(4)
    
    def draw_concept_table(title, items, total_label, total_val):
        pdf.draw_section_header(title); pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(70, 5, 'Lugar / Detalle', 1); pdf.cell(40, 5, 'Fecha Docto', 1, 0, 'C'); pdf.cell(40, 5, 'N° Documento', 1, 0, 'C'); pdf.cell(40, 5, 'Monto $', 1, 1, 'C')
        pdf.set_font('Helvetica', '', 8)
        for _, row in items.iterrows():
            if not str(row.get('Detalle','')).strip() and not row.get('Monto'): continue
            pdf.cell(70, 5, clean(row.get('Detalle','')), 1)
            f_d = row['Fecha'].strftime('%d/%m/%Y') if hasattr(row['Fecha'], 'strftime') and not pd.isnull(row['Fecha']) else str(row['Fecha'])
            pdf.cell(40, 5, f_d, 1, 0, 'C'); pdf.cell(40, 5, clean(row.get('Doc','')), 1, 0, 'C'); pdf.cell(40, 5, format_curr(row.get('Monto',0)), 1, 1, 'R')
        pdf.set_font('Helvetica', 'B', 8); pdf.cell(150, 6, total_label, 1, 0, 'R', fill=True); pdf.cell(40, 6, format_curr(total_val), 1, 1, 'R'); pdf.ln(3)

    draw_concept_table('ALOJAMIENTO', data['df_alojamiento'], 'SUBTOTAL (B)', data['st_alojamiento'])
    draw_concept_table('ALIMENTACIÓN', data['df_alimentacion'], 'SUBTOTAL (C)', data['st_alimentacion'])
    draw_concept_table('OTROS GASTOS', data['df_otros'], 'SUBTOTAL (D)', data['st_otros'])
    
    td = data['st_alojamiento'] + data['st_alimentacion'] + data['st_otros']
    pdf.set_font('Helvetica', 'B', 9); pdf.cell(150, 6, 'Total Desembolsos (B+C+D)', 1, 0, 'R'); pdf.cell(40, 6, format_curr(td), 1, 1, 'R', fill=True); pdf.ln(1)
    delta = data['anticipo'] - td
    pdf.cell(120, 6, 'Diferencia a favor de HGT CHILE LOGISTICS', 'LT', 0, 'L'); pdf.cell(30, 6, '[ A - (B+C+D) ]', 'TR', 0, 'C'); pdf.cell(40, 6, format_curr(max(0, delta)) if delta >= 0 else "-", 1, 1, 'R')
    pdf.cell(150, 6, 'Diferencia a favor de Funcionario ( - )', 1, 0, 'L'); pdf.cell(40, 6, format_curr(abs(delta)) if delta < 0 else "-", 1, 1, 'R')
    pdf.ln(5)
    

    
    # Firmas al final de la página (dinámico según altura de hoja)
    pdf.set_xy(13, pdf.h - 22); pdf.set_font('Helvetica', '', 8)
    pdf.cell(65, 5, data['fecha_rendicion'], 'T', 0, 'C'); pdf.cell(10, 5, '', 0, 0); pdf.cell(65, 5, 'Firma funcionario', 'T', 0, 'C'); pdf.cell(10, 5, '', 0, 0); pdf.cell(40, 5, 'Firma Jefe Directo', 'T', 1, 'C')
    
    # --- Append Scanned Receipts (4 per page) ---
    receipt_images = data.get('receipt_photos', [])
    if receipt_images:
        from PIL import Image
        from io import BytesIO
        
        # Grid positions for 4 images: Top-Left, Top-Right, Bottom-Left, Bottom-Right
        # Shifting 'y' down to clear header and title (y=60)
        # Using centered X positions for Letter width
        positions = [(18, 60), (113, 60), (18, 168), (113, 168)]
        max_w, max_h = 85, 95
        
        for i in range(0, len(receipt_images), 4):
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Documentos de Respaldo / Comprobantes de Gasto', 0, 1, 'C')
            
            chunk = receipt_images[i:i+4]
            for idx, img_bytes in enumerate(chunk):
                try:
                    img_stream = BytesIO(img_bytes)
                    with Image.open(img_stream) as img:
                        img_w, img_h = img.size
                    
                    # Scale to fit constraint box
                    scale = min(max_w / img_w, max_h / img_h)
                    final_w = img_w * scale
                    final_h = img_h * scale
                    
                    x, y = positions[idx]
                    # Center strictly inside the block width
                    x_offset = x + (max_w - final_w) / 2
                    
                    # fpdf needs a fresh stream to render
                    img_stream.seek(0)
                    pdf.image(img_stream, x=x_offset, y=y, w=final_w, h=final_h)
                except Exception as e:
                    pdf.set_font('Helvetica', 'I', 8)
                    x, y = positions[idx]
                    pdf.set_xy(x, y)
                    pdf.cell(max_w, 10, f"Error imagen: {str(e)[:20]}", 0, 0)
    
    return bytes(pdf.output())

def send_hgt_email(to_email, subject, body, pdf_bytes, pdf_name):
    try:
        conf = st.secrets["smtp"]
        msg = MIMEMultipart()
        msg['From'] = conf["user"]
        msg['To'] = to_email
        msg['Subject'] = Header(subject, 'utf-8').encode()
        
        # Formato de correo corporativo HGT: Arial
        html_body = f"""
        <html>
            <body style="font-family: Arial, Helvetica, sans-serif; color: #212a37;">
                <p>{body.replace(chr(10), '<br>')}</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={pdf_name}')
        msg.attach(part)
        
        server = smtplib.SMTP(conf["host"], conf["port"])
        server.starttls()
        server.login(conf["user"], conf["password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Error al enviar correo: {e}")
        return False

# --- STREAMLIT UI ---
# --- Header with Logo ---
if os.path.exists(LOGO_PATH):
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 20px; padding: 10px 0; border-bottom: 2px solid #f0f2f6; margin-bottom: 25px;">
            <img src="data:image/png;base64,{}" width="180">
            <h1 style="margin: 0; color: #212a37; font-size: 2.2rem; font-weight: 700;">Rendición de Gastos</h1>
        </div>
    """.format(base64.b64encode(open(LOGO_PATH, "rb").read()).decode()), unsafe_allow_html=True)
else:
    st.title("🏢 Rendición de Gastos - HGT")


# Session state initialization
if 'receipt_photos' not in st.session_state:
    st.session_state.receipt_photos = []

for df_key in ['df_comision', 'df_aloj', 'df_alim', 'df_otros']:
    if df_key not in st.session_state or not isinstance(st.session_state[df_key], pd.DataFrame):
        if df_key == 'df_comision':
            st.session_state[df_key] = pd.DataFrame(columns=["Traslado", "Desde oficina", "A localidad", "Fecha Inicio", "Fecha Término"]).astype({
                "Fecha Inicio": "datetime64[ns]", "Fecha Término": "datetime64[ns]"
            })
        else:
            st.session_state[df_key] = pd.DataFrame(columns=["Detalle", "Fecha", "Doc", "Monto"]).astype({
                "Fecha": "datetime64[ns]", "Monto": "float"
            })

with st.container():
    st.subheader("1. Funcionario que rinde")
    c1, c2, c3 = st.columns(3)
    nombre = c1.text_input("Nombre", value="")
    if nombre and not all(c.isalpha() or c.isspace() for c in nombre):
        c1.warning("⚠️ Solo se permiten letras")
    rut = c2.text_input("RUT", value="")
    if rut and not all(c.isdigit() or c == "-" for c in rut):
        c2.warning("⚠️ Solo números y guion (-)")
    cc = c3.text_input("Centro de costo")


with st.container():
    st.subheader("2. Detalle de Comisión de Servicios")
    
    TRAYECTO_CONFIG = {
        "Placilla a Renca":       (105, 4, 2700),
        "Renca a Placilla":       (105, 4, 2700),
        "Placilla a San Antonio": (78,  2, 0),
        "San Antonio a Placilla": (78,  2, 0),
        "Renca a San Antonio":    (121, 2, 0),
        "San Antonio a Renca":    (121, 2, 0),
        "Renca a Santiago":       (121, 0, 0),
        "Santiago a Renca":       (121, 0, 0),
    }

    with st.expander("➕ Añadir Nueva Comisión", expanded=True):
        col_c1, col_c2, col_c3 = st.columns(3)
        c_traslado = col_c1.selectbox("Traslado", ["Uber", "Vehículo propio"], key="c_tras")
        c_desde = col_c2.selectbox("Desde oficina", ["Placilla", "Renca", "San Antonio", "Santiago"], key="c_des")
        c_hacia = col_c3.selectbox("A localidad", ["Placilla", "Renca", "San Antonio", "Santiago"], key="c_hac")
        
        col_c4, col_c5 = st.columns(2)
        c_f_inicio = col_c4.date_input("Fecha Inicio", value=datetime.today(), key="c_fi", format="DD/MM/YYYY")
        c_f_termino = col_c5.date_input("Fecha Término", value=datetime.today(), key="c_ft", format="DD/MM/YYYY")
        
        if c_traslado == "Vehículo propio":
            st.markdown("##### 🚗 Cálculo Automático (Vehículo Propio)")
            _tsel = f"{c_desde} a {c_hacia}"
            
            c_f, c_ps, c_psa = st.columns([1, 1.5, 1.5])
            if _tsel in TRAYECTO_CONFIG:
                _kb, _, _pdef = TRAYECTO_CONFIG[_tsel]
                v_fac = c_f.number_input("Factor", min_value=0.0, value=1.0, step=0.5, key="c_fac")
                v_pstgo = c_ps.number_input("Valor Peajes Santiago ($)", min_value=0, value=_pdef if "Renca" in _tsel else 0, step=100, key="c_pstgo")
                v_psa = c_psa.number_input("Valor Peaje San Antonio ($)", min_value=0, value=0, step=100, key="c_psa")
            else:
                st.warning("⚠️ Ruta no pre-configurada. Solo se agregará a la tabla de comisión.")
                v_fac = 0; v_pstgo = 0; v_psa = 0
            
            st.markdown("###### Adicionales del viaje")
            ca1, ca2 = st.columns([2, 1])
            con_acompañante = ca1.checkbox("¿Incluye Acompañante(s)? (20% de la base c/u)", value=False, key="ac_chk")
            n_acompaantes = ca2.number_input("Cantidad", min_value=1, value=1, step=1, key="ac_num") if con_acompañante else 0
            con_equipos = st.checkbox("¿Incluye Traslado de equipos? (20% de la base)", value=False, key="eq_chk")
        else:
            st.info("ℹ️ **Uber seleccionado**: Usa la opción '📸 Escáner de Boletas con IA' en la sección inferior para escanear y agregar el recibo de Uber.")

        st.write("") # espaciador
        if st.button("Añadir Comisión", use_container_width=True, type="primary"):
            nuevo_item = {"Traslado": c_traslado, "Desde oficina": c_desde, "A localidad": c_hacia, "Fecha Inicio": pd.to_datetime(c_f_inicio), "Fecha Término": pd.to_datetime(c_f_termino)}
            st.session_state.df_comision = pd.concat([st.session_state.df_comision, pd.DataFrame([nuevo_item])], ignore_index=True)
            
            # Autocompletar Otros Gastos
            if c_traslado == "Vehículo propio":
                _tsi = f"{c_desde} a {c_hacia}"
                if _tsi in TRAYECTO_CONFIG:
                    gastos_auto = []
                    _kb, _, _ = TRAYECTO_CONFIG[_tsi]
                    
                    if _tsi in ["Renca a Placilla", "Placilla a Renca"]:
                        # Criterio especial: Separar y multiplicar el peaje de Santiago por 4
                        gastos_auto.append({"Detalle": f"Traslado {_tsi}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(_kb * 2 * v_fac)})
                        if v_pstgo > 0:
                            gastos_auto.append({"Detalle": "Peaje Santiago", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(v_pstgo * 4)})
                    elif _tsi in ["Renca a San Antonio", "San Antonio a Renca"]:
                        # Criterio especial: Stgo x4 y San Antonio x2
                        gastos_auto.append({"Detalle": f"Traslado {_tsi}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(_kb * 2 * v_fac)})
                        if v_pstgo > 0:
                            gastos_auto.append({"Detalle": "Peaje Santiago", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(v_pstgo * 4)})
                        if v_psa > 0:
                            gastos_auto.append({"Detalle": "Peaje San Antonio", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(v_psa * 2)})
                    elif _tsi in ["Placilla a San Antonio", "San Antonio a Placilla"]:
                        # Criterio especial: San Antonio x2
                        gastos_auto.append({"Detalle": f"Traslado {_tsi}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(_kb * 2 * v_fac)})
                        if v_psa > 0:
                            gastos_auto.append({"Detalle": "Peaje San Antonio", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(v_psa * 2)})
                    else:
                        # Resto de los tramos: agrupado en un solo valor
                        costo_total = float((_kb * 2 * v_fac) + v_pstgo + v_psa)
                        gastos_auto.append({"Detalle": f"Traslado {_tsi}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": costo_total})
                    
                    # Adicionales
                    base_calc = float(_kb * 2 * v_fac)
                    if con_equipos:
                        gastos_auto.append({"Detalle": "Traslado de equipos (20%)", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(base_calc * 0.2)})
                    if con_acompañante and n_acompaantes > 0:
                        gastos_auto.append({"Detalle": f"Acompañantes x{n_acompaantes} (20% c/u)", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(base_calc * 0.2 * n_acompaantes)})
                    
                    st.session_state.df_otros = pd.concat([st.session_state.df_otros, pd.DataFrame(gastos_auto)], ignore_index=True)
            st.rerun()

    # Tabla para ver y editar registros
    df_c_edit = st.session_state.df_comision.copy()
    if not df_c_edit.empty:
        df_c_edit["Fecha Inicio"] = pd.to_datetime(df_c_edit["Fecha Inicio"])
        df_c_edit["Fecha Término"] = pd.to_datetime(df_c_edit["Fecha Término"])
    
    df_comision = st.data_editor(df_c_edit, num_rows="dynamic", use_container_width=True, key="comision_editor", column_config={
        "Traslado": st.column_config.SelectboxColumn("Traslado", options=["Uber", "Vehículo propio"], required=True),
        "Desde oficina": st.column_config.SelectboxColumn("Desde oficina", options=["Placilla", "Renca", "San Antonio", "Santiago"], required=True),
        "A localidad": st.column_config.SelectboxColumn("A localidad", options=["Placilla", "Renca", "San Antonio", "Santiago"], required=True),
        "Fecha Inicio": st.column_config.DateColumn("Fecha Inicio", format="DD/MM/YYYY"),
        "Fecha Término": st.column_config.DateColumn("Fecha Término", format="DD/MM/YYYY")
    })
    st.session_state.df_comision = df_comision

with st.container():
    st.subheader("3. Anticipo sujeto a rendición (A)")
    c1, c2 = st.columns(2)
    fecha_anticipo = c1.date_input("Fecha Egreso", value=datetime.today())
    anticipo = c2.number_input("Monto Anticipo (A)", min_value=0, step=1, value=0)

# 4. Tables
st.subheader("4. Detalle de Gastos")

# --- AI SCANNER ---
with st.expander("📸 Escáner de Boletas con IA", expanded=True):
    st.write("Sube una imagen o captura una foto desde tu gestor de archivos para extraer los datos automáticamente.")
    dest_table = st.selectbox("Tipo de gasto", ["Alimentación", "Alojamiento", "Otros"])
    
    uploaded_file = st.file_uploader("Selecciona o captura imagen/PDF", type=["jpg", "jpeg", "png", "pdf"], key="uploader")
    active_file = uploaded_file
    
    if st.button("🔍 Escanear y Agregar", type="primary", use_container_width=True):
        if not active_file:
            st.warning("⚠️ Por favor, sube un archivo o toma una foto primero.")
        else:
            with st.spinner("IA analizando boleta..."):
                res = process_receipt_with_ai(active_file)
                if res:
                    try:
                        new_row = {
                            "Detalle": res.get("Detalle", "Sin detalle"),
                            "Fecha": datetime.strptime(res["Fecha"], "%Y-%m-%d").date() if res.get("Fecha") else datetime.today().date(),
                            "Doc": str(res.get("Doc", "")),
                            "Monto": float(res.get("Monto", 0))
                        }
                        # Map table choice to state key
                        mapping = {"Alimentación": "df_alim", "Alojamiento": "df_aloj", "Otros": "df_otros"}
                        state_key = mapping[dest_table]
                        
                        # Store data and image
                        st.session_state[state_key] = pd.concat([st.session_state[state_key], pd.DataFrame([new_row])], ignore_index=True)
                        st.session_state.receipt_photos.append(active_file.getvalue())
                        
                        st.success(f"✅ Agregado a {dest_table}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al procesar datos extraídos: {e}")

    c_img1, c_img2 = st.columns([1, 1])
    c_img1.write(f"📎 Boletas adjuntas: **{len(st.session_state.receipt_photos)}**")
    if len(st.session_state.receipt_photos) > 0:
        if c_img2.button("🗑️ Limpiar Boletas Adjuntas"):
            st.session_state.receipt_photos = []
            st.rerun()

st.markdown("#### ALOJAMIENTO (B)")
c_aloj = st.data_editor(st.session_state.df_aloj, num_rows="dynamic", use_container_width=True, key="aloj_ed", column_config={
    "Detalle": st.column_config.TextColumn("Lugar / Detalle"),
    "Fecha": st.column_config.DateColumn("Fecha Docto", format="DD/MM/YYYY"), 
    "Doc": st.column_config.TextColumn("N° Documento"),
    "Monto": st.column_config.NumberColumn("Monto $", format="$ %d")
})
st.session_state.df_aloj = c_aloj

st.markdown("---")
st.markdown("#### ALIMENTACIÓN (C)")
c_alim = st.data_editor(st.session_state.df_alim, num_rows="dynamic", use_container_width=True, key="alim_ed", column_config={
    "Detalle": st.column_config.TextColumn("Lugar / Detalle"),
    "Fecha": st.column_config.DateColumn("Fecha Docto", format="DD/MM/YYYY"), 
    "Doc": st.column_config.TextColumn("N° Documento"),
    "Monto": st.column_config.NumberColumn("Monto $", format="$ %d")
})
st.session_state.df_alim = c_alim

st.markdown("---")
st.markdown("#### OTROS GASTOS (D)")
c_otros = st.data_editor(st.session_state.df_otros, num_rows="dynamic", use_container_width=True, key="otros_ed", column_config={
    "Detalle": st.column_config.TextColumn("Lugar / Detalle"),
    "Fecha": st.column_config.DateColumn("Fecha Docto", format="DD/MM/YYYY"), 
    "Doc": st.column_config.TextColumn("N° Documento"),
    "Monto": st.column_config.NumberColumn("Monto $", format="$ %d")
})
st.session_state.df_otros = c_otros



# --- SUMMARY & EXPORT ---
st.divider()
st_aloj = c_aloj['Monto'].sum(); st_alim = c_alim['Monto'].sum(); st_otros = c_otros['Monto'].sum(); td = st_aloj + st_alim + st_otros; delta = anticipo - td
col1, col2, col3 = st.columns(3)
col1.metric("Total Gastos", format_curr(td))
col2.metric("Anticipo", format_curr(anticipo))
col3.metric("Diferencia", format_curr(delta), delta_color="normal" if delta >= 0 else "inverse")

# --- Estado de vista: 'form' (formulario) o 'preview' (vista previa del PDF) ---
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'form'

# Guardar datos del formulario en session_state para recuperarlos si se vuelve a editar
def save_form_snapshot():
    st.session_state.snap_nombre = nombre
    st.session_state.snap_rut = rut
    st.session_state.snap_cc = cc
    st.session_state.snap_anticipo = anticipo
    st.session_state.snap_fecha_anticipo = fecha_anticipo

# --- Botón principal: Generar Vista Previa PDF ---
if st.session_state.view_mode == 'form':
    if st.button("🔍 Previsualizar y Generar PDF", use_container_width=True, type="primary"):
        if not nombre or not all(c.isalpha() or c.isspace() for c in nombre):
            st.error("⚠️ Nombre inválido. Solo se permiten letras.")
        elif not rut or not rut.strip():
            st.error("⚠️ RUT es obligatorio.")
        else:
            with st.spinner("Generando PDF para revisión..."):
                save_form_snapshot()
                dt = {
                    "nombre": nombre, "rut": rut, "centro_costo": cc,
                    "df_comision": df_comision, "anticipo": anticipo,
                    "fecha_anticipo": fecha_anticipo,
                    "df_alojamiento": c_aloj, "st_alojamiento": st_aloj,
                    "df_alimentacion": c_alim, "st_alimentacion": st_alim,
                    "df_otros": c_otros, "st_otros": st_otros,
                    "fecha_rendicion": datetime.now().strftime("%d-%m-%Y"),
                    "receipt_photos": st.session_state.receipt_photos
                }
                pdf_b = generate_hgt_pdf(dt)
                st.session_state.final_pdf = pdf_b
                st.session_state.pdf_fname = f"Rendicion_HGT_{nombre}_{dt['fecha_rendicion']}.pdf"
                st.session_state.snap_total = td # Guardar total para la DB
                st.session_state.view_mode = 'preview'
                st.rerun()

# --- Vista Previa del PDF ---
if st.session_state.view_mode == 'preview' and 'final_pdf' in st.session_state:
    st.divider()
    st.subheader("📄 Vista Previa del PDF Generado")
    st.info("Revisa el documento a continuación. Si está correcto, confirma el envío. Si necesitas corregir algo, usa el botón '✏️ Corregir Formulario'.")

    # Mostrar PDF embebido con iframe base64

    pdf_b64 = base64.b64encode(st.session_state.final_pdf).decode("utf-8")
    pdf_display = f"""
        <iframe
            src="data:application/pdf;base64,{pdf_b64}"
            width="100%"
            height="700px"
            style="border: 2px solid #212a37; border-radius: 8px;"
        ></iframe>
    """
    st.markdown(pdf_display, unsafe_allow_html=True)

    st.divider()
    st.subheader("¿El documento está correcto?")

    col_corr, col_mid, col_send = st.columns([1, 0.2, 1])

    # Botón CORREGIR: vuelve al formulario SIN perder datos
    with col_corr:
        if st.button("✏️ Corregir Formulario", use_container_width=True):
            st.session_state.view_mode = 'form'
            # Borrar PDF temporal para evitar mostrar versión antigua
            if 'final_pdf' in st.session_state:
                del st.session_state['final_pdf']
            st.rerun()

    # Botón ENVIAR: confirmar y enviar por correo
    with col_send:
        default_to = st.secrets["smtp"]["recipient"] if "smtp" in st.secrets else "finanzas@hgt.cl"
        dest = st.text_input("📧 Destinatario:", value=default_to, key="dest_email")
        
        if st.button("✅ Confirmar y Enviar por Correo", use_container_width=True, type="primary"):
            with st.spinner("Enviando correo..."):
                subject = f"Rendición de Gastos - {st.session_state.get('snap_nombre', 'Funcionario')}"
                body = (
                    f"Estimados,\n\n"
                    f"Se adjunta reporte oficial de rendición de gastos generado por "
                    f"{st.session_state.get('snap_nombre', 'Funcionario')}.\n\n"
                    f"Saludos."
                )
                if send_hgt_email(dest, subject, body, st.session_state.final_pdf, st.session_state.pdf_fname):
                    st.success("✅ ¡Correo enviado con éxito!")
                    # Guardar en base de datos al finalizar con éxito
                    db_save_rendicion(
                        st.session_state.snap_nombre,
                        st.session_state.snap_rut,
                        st.session_state.snap_cc,
                        st.session_state.snap_total,
                        datetime.now()
                    )
                    st.balloons()

    st.divider()
    col_dl, col_reset = st.columns(2)
    col_dl.download_button(
        "💾 Descargar PDF",
        data=bytes(st.session_state.final_pdf),
        file_name=st.session_state.pdf_fname,
        mime="application/pdf",
        use_container_width=True
    )
    if col_reset.button("❌ Nueva Rendición / Salir", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- Historial de Rendiciones ---
st.divider()
with st.expander("📊 Ver Historial de Rendiciones (Registradas en DB)"):
    try:
        conn = sqlite3.connect("rendiciones_hgt.db")
        df_hist = pd.read_sql_query("SELECT * FROM rendiciones ORDER BY fecha_registro DESC", conn)
        conn.close()
        
        if not df_hist.empty:
            st.dataframe(df_hist, use_container_width=True, hide_index=True, column_config={
                "id_rut": "RUT ID",
                "nombre": "Funcionario",
                "fecha": "Fecha Rendición",
                "mes": "Mes",
                "año": "Año",
                "centro_costo": "CC",
                "total": st.column_config.NumberColumn("Total Rendido", format="$ %d"),
                "fecha_registro": "Registro Sistema"
            })
        else:
            st.info("No hay rendiciones registradas aún.")
    except Exception as e:
        st.error(f"Error al cargar historial: {e}")
