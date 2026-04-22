import streamlit as st
import pandas as pd
import json, os, base64
import google.generativeai as genai
from datetime import datetime
import sqlite3

# ── Importar utilidades compartidas ─────────────────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    generate_hgt_pdf, send_hgt_email, format_curr,
    init_db, db_submit_rendicion, db_get_all, LOGO_PATH, DB_PATH
)

# ── Configuración IA ─────────────────────────────────────────────────────────
def init_ai():
    if "ai" in st.secrets and "gemini_api_key" in st.secrets["ai"]:
        genai.configure(api_key=st.secrets["ai"]["gemini_api_key"])
        return True
    return False

# ── Inicialización ───────────────────────────────────────────────────────────
init_db()

# ── Escáner IA ───────────────────────────────────────────────────────────────
def process_receipt_with_ai(uploaded_file):
    if not init_ai():
        st.error("❌ No se encontró la GEMINI_API_KEY en secrets.toml")
        return None
    try:
        model    = genai.GenerativeModel('gemini-flash-latest')
        img_bytes = uploaded_file.getvalue()
        prompt   = """
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
            prompt, {"mime_type": uploaded_file.type, "data": img_bytes}
        ])
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except Exception as e:
        st.error(f"❌ Error al procesar con IA: {e}")
        return None

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(page_title="HGT - Rendición de Gastos", page_icon="🏢", layout="wide")

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    .main { background-color: #ffffff; }
    .block-container { padding-top:1rem !important; padding-bottom:1rem !important;
                       padding-left:1rem !important; padding-right:1rem !important; }
    header[data-testid="stHeader"] { display: none !important; }
    hr { margin-top: 0.5rem !important; margin-bottom: 0.5rem !important; }
    div[data-testid="stExpander"] { margin-bottom: 0.2rem !important; }
    h3 { padding-bottom: 0.2rem !important; margin-bottom: 0px !important; }
    .stButton>button, .stDownloadButton>button {
        border-radius: 6px; font-weight: bold; padding: 0.5rem 1rem;
        min-height: 45px; width: 100%; border: 1px solid #212a37; }
    .stButton>button { background-color: #212a37; color: white; }
    .stButton>button[kind="primary"] { background-color: #ff6600; color: white; border-color: #ff6600; }
    .stDownloadButton>button { background-color: #ff6600; color: white; border-color: #ff6600; }
    .stMetric { background-color:#ffffff; padding:5px 15px; border-radius:10px;
                border:1px solid #dadadf; margin-bottom:5px; box-shadow:0 1px 3px rgba(0,0,0,0.05); }
    @media (max-width: 768px) {
        .stTitle { font-size: 1.6rem !important; text-align: center; }
        .stImage { display: flex; justify-content: center; margin-bottom: -20px; }
        div[data-testid="stExpander"] { margin-left:-5px; margin-right:-5px; }
    }
    </style>
""", unsafe_allow_html=True)

# ── Header con Logo ──────────────────────────────────────────────────────────
if os.path.exists(LOGO_PATH):
    st.markdown("""
        <div style="display:flex;align-items:center;gap:20px;padding:10px 0;
                    border-bottom:2px solid #f0f2f6;margin-bottom:25px;">
            <img src="data:image/png;base64,{}" width="180">
            <h1 style="margin:0;color:#212a37;font-size:2.2rem;font-weight:700;">
                Rendición de Gastos</h1>
        </div>
    """.format(base64.b64encode(open(LOGO_PATH, "rb").read()).decode()),
    unsafe_allow_html=True)
else:
    st.title("🏢 Rendición de Gastos - HGT")

# ── Session state ────────────────────────────────────────────────────────────
if 'receipt_photos' not in st.session_state:
    st.session_state.receipt_photos = []
if 'firma_bytes' not in st.session_state:
    st.session_state.firma_bytes = None
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'form'

for df_key in ['df_comision', 'df_aloj', 'df_alim', 'df_otros']:
    if df_key not in st.session_state or not isinstance(st.session_state[df_key], pd.DataFrame):
        if df_key == 'df_comision':
            st.session_state[df_key] = pd.DataFrame(
                columns=["Traslado", "Desde oficina", "A localidad", "Fecha Inicio", "Fecha Término"]
            ).astype({"Fecha Inicio": "datetime64[ns]", "Fecha Término": "datetime64[ns]"})
        else:
            st.session_state[df_key] = pd.DataFrame(
                columns=["Detalle", "Fecha", "Doc", "Monto"]
            ).astype({"Fecha": "datetime64[ns]", "Monto": "float"})

# ════════════════════════════════════════════════════════════════════════
# SECCIÓN 1: Funcionario
# ════════════════════════════════════════════════════════════════════════
with st.container():
    st.subheader("1. Funcionario que rinde")
    c1, c2, c3, c4 = st.columns(4)
    nombre = c1.text_input("Nombre", value="")
    if nombre and not all(ch.isalpha() or ch.isspace() for ch in nombre):
        c1.warning("⚠️ Solo se permiten letras")
    rut = c2.text_input("RUT", value="")
    if rut and not all(ch.isdigit() or ch == "-" for ch in rut):
        c2.warning("⚠️ Solo números y guion (-)")
    cc            = c3.text_input("Centro de costo")
    email_func    = c4.text_input("Email funcionario", placeholder="tu@correo.com")

# ════════════════════════════════════════════════════════════════════════
# SECCIÓN 2: Comisión de Servicios
# ════════════════════════════════════════════════════════════════════════
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
        c_desde    = col_c2.selectbox("Desde oficina",
                                      ["Placilla", "Renca", "San Antonio", "Santiago"], key="c_des")
        c_hacia    = col_c3.selectbox("A localidad",
                                      ["Placilla", "Renca", "San Antonio", "Santiago"], key="c_hac")
        col_c4, col_c5 = st.columns(2)
        c_f_inicio  = col_c4.date_input("Fecha Inicio",  value=datetime.today(), key="c_fi", format="DD/MM/YYYY")
        c_f_termino = col_c5.date_input("Fecha Término", value=datetime.today(), key="c_ft", format="DD/MM/YYYY")

        if c_traslado == "Vehículo propio":
            st.markdown("##### 🚗 Cálculo Automático (Vehículo Propio)")
            _tsel = f"{c_desde} a {c_hacia}"
            c_f, c_ps, c_psa = st.columns([1, 1.5, 1.5])
            if _tsel in TRAYECTO_CONFIG:
                _kb, _, _pdef = TRAYECTO_CONFIG[_tsel]
                v_fac   = c_f.number_input("Factor", min_value=0.0, value=1.0, step=0.5, key="c_fac")
                v_pstgo = c_ps.number_input("Valor Peajes Santiago ($)", min_value=0,
                                            value=_pdef if "Renca" in _tsel else 0, step=100, key="c_pstgo")
                v_psa   = c_psa.number_input("Valor Peaje San Antonio ($)", min_value=0,
                                             value=0, step=100, key="c_psa")
            else:
                st.warning("⚠️ Ruta no pre-configurada.")
                v_fac = v_pstgo = v_psa = 0

            st.markdown("###### Adicionales del viaje")
            ca1, ca2 = st.columns([2, 1])
            con_acomp   = ca1.checkbox("¿Incluye Acompañante(s)? (20% de la base c/u)", key="ac_chk")
            n_acomp     = ca2.number_input("Cantidad", min_value=1, value=1, step=1, key="ac_num") if con_acomp else 0
            con_equipos = st.checkbox("¿Incluye Traslado de equipos? (20% de la base)", key="eq_chk")
        else:
            st.info("ℹ️ **Uber seleccionado**: Usa el Escáner de Boletas para adjuntar el recibo Uber.")

        st.write("")
        if st.button("Añadir Comisión", use_container_width=True, type="primary"):
            nuevo = {"Traslado": c_traslado, "Desde oficina": c_desde, "A localidad": c_hacia,
                     "Fecha Inicio": pd.to_datetime(c_f_inicio),
                     "Fecha Término": pd.to_datetime(c_f_termino)}
            st.session_state.df_comision = pd.concat(
                [st.session_state.df_comision, pd.DataFrame([nuevo])], ignore_index=True)
            if c_traslado == "Vehículo propio":
                _tsi = f"{c_desde} a {c_hacia}"
                if _tsi in TRAYECTO_CONFIG:
                    gastos_auto = []
                    _kb, _, _ = TRAYECTO_CONFIG[_tsi]
                    base_monto = float(_kb * 2 * v_fac)
                    if _tsi in ["Renca a Placilla", "Placilla a Renca"]:
                        gastos_auto.append({"Detalle": f"Traslado {_tsi}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": base_monto})
                        if v_pstgo > 0:
                            gastos_auto.append({"Detalle": "Peaje Santiago", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(v_pstgo * 4)})
                    elif _tsi in ["Renca a San Antonio", "San Antonio a Renca"]:
                        gastos_auto.append({"Detalle": f"Traslado {_tsi}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": base_monto})
                        if v_pstgo > 0:
                            gastos_auto.append({"Detalle": "Peaje Santiago", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(v_pstgo * 4)})
                        if v_psa > 0:
                            gastos_auto.append({"Detalle": "Peaje San Antonio", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(v_psa * 2)})
                    elif _tsi in ["Placilla a San Antonio", "San Antonio a Placilla"]:
                        gastos_auto.append({"Detalle": f"Traslado {_tsi}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": base_monto})
                        if v_psa > 0:
                            gastos_auto.append({"Detalle": "Peaje San Antonio", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(v_psa * 2)})
                    else:
                        gastos_auto.append({"Detalle": f"Traslado {_tsi}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": base_monto + v_pstgo + v_psa})
                    if con_equipos:
                        gastos_auto.append({"Detalle": "Traslado de equipos (20%)", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(base_monto * 0.2)})
                    if con_acomp and n_acomp > 0:
                        gastos_auto.append({"Detalle": f"Acompañantes x{n_acomp} (20% c/u)", "Fecha": pd.to_datetime(c_f_inicio), "Doc": "", "Monto": float(base_monto * 0.2 * n_acomp)})
                    st.session_state.df_otros = pd.concat(
                        [st.session_state.df_otros, pd.DataFrame(gastos_auto)], ignore_index=True)
            st.rerun()

    df_c_edit = st.session_state.df_comision.copy()
    if not df_c_edit.empty:
        df_c_edit["Fecha Inicio"]  = pd.to_datetime(df_c_edit["Fecha Inicio"])
        df_c_edit["Fecha Término"] = pd.to_datetime(df_c_edit["Fecha Término"])
    df_comision = st.data_editor(df_c_edit, num_rows="dynamic", use_container_width=True,
        key="comision_editor", column_config={
            "Traslado":      st.column_config.SelectboxColumn("Traslado", options=["Uber", "Vehículo propio"], required=True),
            "Desde oficina": st.column_config.SelectboxColumn("Desde oficina", options=["Placilla", "Renca", "San Antonio", "Santiago"], required=True),
            "A localidad":   st.column_config.SelectboxColumn("A localidad",   options=["Placilla", "Renca", "San Antonio", "Santiago"], required=True),
            "Fecha Inicio":  st.column_config.DateColumn("Fecha Inicio",  format="DD/MM/YYYY"),
            "Fecha Término": st.column_config.DateColumn("Fecha Término", format="DD/MM/YYYY"),
        })
    st.session_state.df_comision = df_comision

# ════════════════════════════════════════════════════════════════════════
# SECCIÓN 3: Anticipo
# ════════════════════════════════════════════════════════════════════════
with st.container():
    st.subheader("3. Anticipo sujeto a rendición (A)")
    c1, c2 = st.columns(2)
    fecha_anticipo = c1.date_input("Fecha Egreso", value=datetime.today())
    anticipo       = c2.number_input("Monto Anticipo (A)", min_value=0, step=1, value=0)

# ════════════════════════════════════════════════════════════════════════
# SECCIÓN 4: Detalle de Gastos
# ════════════════════════════════════════════════════════════════════════
st.subheader("4. Detalle de Gastos")

with st.expander("📸 Escáner de Boletas con IA", expanded=True):
    st.write("Sube una imagen o captura una foto para extraer los datos automáticamente.")
    dest_table   = st.selectbox("Tipo de gasto", ["Alimentación", "Alojamiento", "Otros"])
    uploaded_file = st.file_uploader("Selecciona o captura imagen/PDF",
                                     type=["jpg", "jpeg", "png", "pdf"], key="uploader")
    if st.button("🔍 Escanear y Agregar", type="primary", use_container_width=True):
        if not uploaded_file:
            st.warning("⚠️ Por favor, sube un archivo primero.")
        else:
            with st.spinner("IA analizando boleta..."):
                res = process_receipt_with_ai(uploaded_file)
                if res:
                    try:
                        new_row = {
                            "Detalle": res.get("Detalle", "Sin detalle"),
                            "Fecha":   datetime.strptime(res["Fecha"], "%Y-%m-%d").date() if res.get("Fecha") else datetime.today().date(),
                            "Doc":     str(res.get("Doc", "")),
                            "Monto":   float(res.get("Monto", 0))
                        }
                        mapping = {"Alimentación": "df_alim", "Alojamiento": "df_aloj", "Otros": "df_otros"}
                        skey    = mapping[dest_table]
                        st.session_state[skey] = pd.concat(
                            [st.session_state[skey], pd.DataFrame([new_row])], ignore_index=True)
                        st.session_state.receipt_photos.append(uploaded_file.getvalue())
                        st.success(f"✅ Agregado a {dest_table}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al procesar datos extraídos: {e}")
    c_img1, c_img2 = st.columns(2)
    c_img1.write(f"📎 Boletas adjuntas: **{len(st.session_state.receipt_photos)}**")
    if st.session_state.receipt_photos:
        if c_img2.button("🗑️ Limpiar Boletas Adjuntas"):
            st.session_state.receipt_photos = []
            st.rerun()

st.markdown("#### ALOJAMIENTO (B)")
c_aloj = st.data_editor(st.session_state.df_aloj, num_rows="dynamic", use_container_width=True,
    key="aloj_ed", column_config={
        "Detalle": st.column_config.TextColumn("Lugar / Detalle"),
        "Fecha":   st.column_config.DateColumn("Fecha Docto", format="DD/MM/YYYY"),
        "Doc":     st.column_config.TextColumn("N° Documento"),
        "Monto":   st.column_config.NumberColumn("Monto $", format="$ %d"),
    })
st.session_state.df_aloj = c_aloj

st.markdown("---")
st.markdown("#### ALIMENTACIÓN (C)")
c_alim = st.data_editor(st.session_state.df_alim, num_rows="dynamic", use_container_width=True,
    key="alim_ed", column_config={
        "Detalle": st.column_config.TextColumn("Lugar / Detalle"),
        "Fecha":   st.column_config.DateColumn("Fecha Docto", format="DD/MM/YYYY"),
        "Doc":     st.column_config.TextColumn("N° Documento"),
        "Monto":   st.column_config.NumberColumn("Monto $", format="$ %d"),
    })
st.session_state.df_alim = c_alim

st.markdown("---")
st.markdown("#### OTROS GASTOS (D)")
c_otros = st.data_editor(st.session_state.df_otros, num_rows="dynamic", use_container_width=True,
    key="otros_ed", column_config={
        "Detalle": st.column_config.TextColumn("Lugar / Detalle"),
        "Fecha":   st.column_config.DateColumn("Fecha Docto", format="DD/MM/YYYY"),
        "Doc":     st.column_config.TextColumn("N° Documento"),
        "Monto":   st.column_config.NumberColumn("Monto $", format="$ %d"),
    })
st.session_state.df_otros = c_otros

# ════════════════════════════════════════════════════════════════════════
# RESUMEN
# ════════════════════════════════════════════════════════════════════════
st.divider()
st_aloj  = c_aloj['Monto'].sum()
st_alim  = c_alim['Monto'].sum()
st_otros = c_otros['Monto'].sum()
td       = st_aloj + st_alim + st_otros
delta    = anticipo - td

col1, col2, col3 = st.columns(3)
col1.metric("Total Gastos",  format_curr(td))
col2.metric("Anticipo",      format_curr(anticipo))
col3.metric("Diferencia",    format_curr(delta), delta_color="normal" if delta >= 0 else "inverse")

# ── Firma del Funcionario ───────────────────────────────────────────────────
st.markdown("#### ✍️ Firma del Funcionario")
st.caption("Sube una imagen de tu firma (PNG o JPG). Se insertará en el PDF en el campo 'Firma Funcionario'.")
sig_col1, sig_col2 = st.columns([2, 1])
sig_file = sig_col1.file_uploader("Subir imagen de firma", type=["png", "jpg", "jpeg"],
                                   key="firma_uploader", label_visibility="collapsed")
if sig_file:
    sig_col2.image(sig_file, caption="Vista previa firma", width=180)
    st.session_state.firma_bytes = sig_file.getvalue()

# ── Snapshot ────────────────────────────────────────────────────────────────
def save_form_snapshot():
    st.session_state.snap_nombre         = nombre
    st.session_state.snap_rut            = rut
    st.session_state.snap_cc             = cc
    st.session_state.snap_email_func     = email_func
    st.session_state.snap_anticipo       = anticipo
    st.session_state.snap_fecha_anticipo = fecha_anticipo

# ════════════════════════════════════════════════════════════════════════
# BOTÓN: Previsualizar
# ════════════════════════════════════════════════════════════════════════
if st.session_state.view_mode == 'form':
    if st.button("🔍 Previsualizar Rendición", use_container_width=True, type="primary"):
        if not nombre or not all(ch.isalpha() or ch.isspace() for ch in nombre):
            st.error("⚠️ Nombre inválido. Solo se permiten letras.")
        elif not rut or not rut.strip():
            st.error("⚠️ RUT es obligatorio.")
        else:
            with st.spinner("Generando PDF para revisión..."):
                save_form_snapshot()
                dt = {
                    "nombre": nombre, "rut": rut, "centro_costo": cc,
                    "email_funcionario": email_func,
                    "df_comision": df_comision, "anticipo": anticipo,
                    "fecha_anticipo": fecha_anticipo,
                    "df_alojamiento": c_aloj, "st_alojamiento": st_aloj,
                    "df_alimentacion": c_alim, "st_alimentacion": st_alim,
                    "df_otros": c_otros, "st_otros": st_otros,
                    "fecha_rendicion": datetime.now().strftime("%d-%m-%Y"),
                    "receipt_photos": st.session_state.receipt_photos,
                    "firma_bytes": st.session_state.get('firma_bytes'),
                }
                st.session_state.pending_data = dt
                st.session_state.final_pdf    = generate_hgt_pdf(dt)
                st.session_state.pdf_fname    = f"Rendicion_HGT_{nombre}_{dt['fecha_rendicion']}.pdf"
                st.session_state.snap_total   = td
                st.session_state.view_mode    = 'preview'
                st.rerun()

# ════════════════════════════════════════════════════════════════════════
# VISTA PREVIA + ENVÍO A JEFATURA
# ════════════════════════════════════════════════════════════════════════
if st.session_state.view_mode == 'preview' and 'final_pdf' in st.session_state:
    st.divider()
    st.subheader("📄 Vista Previa del PDF")
    st.info("Revisa el documento. Si está correcto, envíalo a tu jefatura para aprobación.")

    pdf_b64     = base64.b64encode(st.session_state.final_pdf).decode("utf-8")
    st.markdown(f"""
        <iframe src="data:application/pdf;base64,{pdf_b64}" width="100%" height="700px"
            style="border:2px solid #212a37;border-radius:8px;"></iframe>
    """, unsafe_allow_html=True)

    st.divider()
    col_corr, col_mid, col_send = st.columns([1, 0.2, 1])

    with col_corr:
        if st.button("✏️ Corregir Formulario", use_container_width=True):
            st.session_state.view_mode = 'form'
            if 'final_pdf' in st.session_state:
                del st.session_state['final_pdf']
            st.rerun()

    with col_send:
        st.markdown("**Enviar a Jefatura para aprobación:**")
        if st.button("✅ Enviar para Aprobación", use_container_width=True, type="primary"):
            with st.spinner("Enviando rendición..."):
                # 1. Guardar en BD
                rid = db_submit_rendicion(st.session_state.pending_data)

                # 2. Notificar a jefatura
                jefe_email = st.secrets.get("jefatura", {}).get("email", st.secrets["smtp"]["recipient"])
                smtp_conf  = dict(st.secrets["smtp"])
                body_jefe  = (f"Estimada Jefatura,\n\n"
                              f"El funcionario {st.session_state.snap_nombre} "
                              f"(RUT: {st.session_state.snap_rut}) ha enviado una rendición de gastos "
                              f"por un total de {format_curr(st.session_state.snap_total)} "
                              f"que requiere su aprobación.\n\n"
                              f"Por favor, ingrese al Panel de Jefatura para revisar y aprobar.\n\n"
                              f"Saludos,\nSistema HGT Chile Logistics")
                send_hgt_email(smtp_conf, jefe_email,
                               f"[PENDIENTE] Rendición de {st.session_state.snap_nombre}",
                               body_jefe,
                               bytes(st.session_state.final_pdf),
                               st.session_state.pdf_fname)

                st.success(f"✅ Rendición enviada a jefatura para aprobación (ID #{rid}).")
                st.info("Serás notificado por correo cuando sea aprobada.")
                st.balloons()
                # Limpiar
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

    st.divider()
    st.download_button(
        "💾 Descargar copia del PDF",
        data=bytes(st.session_state.final_pdf),
        file_name=st.session_state.pdf_fname,
        mime="application/pdf",
        use_container_width=True
    )

# ════════════════════════════════════════════════════════════════════════
# HISTORIAL (propio)
# ════════════════════════════════════════════════════════════════════════
st.divider()
with st.expander("📊 Ver Historial de Mis Rendiciones"):
    try:
        df_hist = db_get_all()
        if not df_hist.empty:
            STATUS_COLORS = {'pendiente': '🟡', 'aprobado': '🟢', 'rechazado': '🔴'}
            df_hist['Estado'] = df_hist['status'].map(lambda s: f"{STATUS_COLORS.get(s,'⚪')} {s.capitalize()}")
            st.dataframe(df_hist[['id','nombre','rut','centro_costo','total','Estado','fecha_registro']],
                         use_container_width=True, hide_index=True,
                         column_config={
                             "id":              "ID",
                             "nombre":          "Funcionario",
                             "rut":             "RUT",
                             "centro_costo":    "CC",
                             "total":           st.column_config.NumberColumn("Total", format="$ %d"),
                             "Estado":          "Estado",
                             "fecha_registro":  "Fecha Registro",
                         })
        else:
            st.info("No hay rendiciones registradas aún.")
    except Exception as e:
        st.error(f"Error al cargar historial: {e}")
