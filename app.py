import streamlit as st
import os, base64
from utils import init_db, db_verify_user, LOGO_PATH

# Inicializar DB
init_db()

# ── Configuración de Página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="HGT - Gestión de Rendiciones",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ── CSS HGT Premium ────────────────────────────────────────────────────────
def load_css():
    with open(os.path.join(os.path.dirname(__file__), "css", "hgt_style.css"), "r", encoding="utf-8") as f:
        custom_css = f.read()
    
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');

        {custom_css}

        /* ═══ APP — Tipografía y fondo base ═══ */
        .stApp {{
            font-family: 'Outfit', 'Inter', system-ui, -apple-system, sans-serif !important;
            background-color: var(--bg-main) !important;
            color: var(--text-main) !important;
        }}

        /* ═══ SIDEBAR — HGT Brand ═══ */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, var(--hgt-greyblue) 0%, #0f1620 100%) !important;
            border-right: 1px solid rgba(255,255,255,0.05) !important;
        }}
        [data-testid="stSidebar"] > div:first-child {{
            padding-top: 1rem;
        }}
        [data-testid="stSidebar"] * {{
            color: var(--hgt-white) !important;
        }}
        [data-testid="stSidebar"] .stMarkdown {{
            color: var(--hgt-white) !important;
        }}
        [data-testid="stSidebar"] hr {{
            border-color: rgba(255,255,255,0.08) !important;
        }}

        /* Sidebar — Brand box */
        .sidebar-brand {{
            background: var(--hgt-greyblue-light);
            margin: 0 1rem 1.5rem 1rem;
            padding: 1rem;
            border-radius: 12px;
            text-align: center;
            border-bottom: 2px solid var(--hgt-orange);
            transition: var(--spring);
        }}
        .sidebar-brand:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.3);
        }}
        .sidebar-brand img {{
            max-width: 80%;
            height: auto;
            display: block;
            margin: 0 auto;
        }}
        .sidebar-user {{
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 0.85rem 1rem;
            margin: 0 1rem 1rem 1rem;
            font-size: 0.85rem;
        }}
        .sidebar-user .name {{
            font-weight: 700;
            color: var(--hgt-white);
            margin-bottom: 0.25rem;
        }}
        .sidebar-user .meta {{
            color: rgba(255,255,255,0.55);
            font-size: 0.75rem;
        }}
        .sidebar-user .role-pill {{
            display: inline-block;
            background: var(--hgt-orange);
            color: var(--hgt-white);
            font-size: 0.65rem;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 50px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-right: 4px;
        }}

        /* Sidebar — Nav items */
        .sidebar-nav-item {{
            display: flex;
            align-items: center;
            gap: 0.85rem;
            padding: 0.75rem 1.25rem;
            margin: 0.15rem 0.75rem;
            border-radius: 10px;
            color: rgba(255,255,255,0.75) !important;
            font-weight: 500;
            font-size: 0.92rem;
            transition: all 0.25s ease;
            cursor: pointer;
            text-decoration: none;
            border-left: 3px solid transparent;
        }}
        .sidebar-nav-item:hover {{
            background: rgba(255, 102, 0, 0.10);
            color: var(--hgt-orange) !important;
            border-left-color: var(--hgt-orange);
        }}
        .sidebar-nav-item.active {{
            background: rgba(255, 102, 0, 0.15);
            color: var(--hgt-orange) !important;
            border-left-color: var(--hgt-orange);
            font-weight: 600;
        }}
        .sidebar-nav-item i {{
            width: 18px;
            text-align: center;
            font-size: 0.95rem;
        }}

        /* ═══ BUTTONS — Mapear a .btn .btn-primary ═══ */
        .stButton>button, .stFormSubmitButton>button, .stDownloadButton>button {{
            background: var(--hgt-orange) !important;
            color: var(--hgt-white) !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 0.6rem 1.2rem !important;
            font-weight: 600 !important;
            font-family: 'Outfit', sans-serif !important;
            font-size: 0.92rem !important;
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
            box-shadow: var(--hgt-shadow) !important;
            position: relative;
            overflow: hidden;
        }}
        .stButton>button:hover, .stFormSubmitButton>button:hover, .stDownloadButton>button:hover {{
            background: var(--hgt-orange-dark) !important;
            transform: translateY(-2px) !important;
            box-shadow: var(--hgt-shadow-hover) !important;
            color: var(--hgt-white) !important;
        }}
        .stButton>button:active, .stFormSubmitButton>button:active {{
            transform: translateY(0) !important;
        }}

        /* Secondary buttons (no primary) */
        .stButton>button[kind="secondary"] {{
            background: var(--hgt-greyblue) !important;
        }}
        .stButton>button[kind="secondary"]:hover {{
            background: var(--hgt-greyblue-light) !important;
        }}

        /* ═══ INPUTS — Mapear a .form-control ═══ */
        .stTextInput>div>div>input,
        .stNumberInput>div>div>input,
        .stTextArea>div>div>textarea,
        .stDateInput>div>div>input,
        .stTimeInput>div>div>input {{
            background: var(--hgt-white) !important;
            border: 1.5px solid var(--hgt-border) !important;
            border-radius: 10px !important;
            color: var(--text-main) !important;
            font-family: 'Outfit', sans-serif !important;
            transition: all 0.2s ease !important;
        }}
        .stTextInput>div>div>input:focus,
        .stNumberInput>div>div>input:focus,
        .stTextArea>div>div>textarea:focus {{
            border-color: var(--hgt-orange) !important;
            box-shadow: 0 0 0 3px var(--hgt-orange-glow) !important;
            outline: none !important;
        }}
        .stTextInput label, .stNumberInput label, .stTextArea label,
        .stSelectbox label, .stMultiSelect label, .stDateInput label,
        .stTimeInput label, .stFileUploader label {{
            color: var(--text-main) !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
        }}

        /* Select / Multiselect */
        .stSelectbox>div>div, .stMultiSelect>div>div {{
            border-radius: 10px !important;
        }}
        [data-baseweb="select"]>div {{
            border: 1.5px solid var(--hgt-border) !important;
            border-radius: 10px !important;
            background: var(--hgt-white) !important;
        }}
        [data-baseweb="select"]>div:focus-within {{
            border-color: var(--hgt-orange) !important;
            box-shadow: 0 0 0 3px var(--hgt-orange-glow) !important;
        }}
        [data-baseweb="tag"] {{
            background: var(--hgt-orange) !important;
            color: var(--hgt-white) !important;
        }}

        /* Checkbox / Radio */
        .stCheckbox label, .stRadio label {{
            color: var(--text-main) !important;
        }}

        /* File uploader */
        [data-testid="stFileUploaderDropzone"] {{
            background: var(--bg-card) !important;
            border: 2px dashed var(--hgt-border) !important;
            border-radius: 12px !important;
        }}
        [data-testid="stFileUploaderDropzone"]:hover {{
            border-color: var(--hgt-orange) !important;
            background: var(--hgt-orange-glow) !important;
        }}

        /* ═══ CARDS / EXPANDER ═══ */
        .stExpander, details[data-testid="stExpander"] {{
            background: var(--bg-card) !important;
            border-radius: 12px !important;
            border: 1px solid var(--hgt-border) !important;
            box-shadow: var(--hgt-shadow) !important;
            overflow: hidden;
        }}
        details[data-testid="stExpander"] summary,
        .stExpander summary {{
            background: var(--bg-card) !important;
            color: var(--text-main) !important;
            font-weight: 600 !important;
            border-radius: 12px !important;
            padding: 0.85rem 1rem !important;
        }}
        details[data-testid="stExpander"] summary:hover {{
            background: var(--hgt-slate) !important;
        }}
        details[data-testid="stExpander"][open] summary {{
            border-bottom: 1px solid var(--hgt-border);
            border-radius: 12px 12px 0 0 !important;
        }}

        /* ═══ TABS — HGT pill style ═══ */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.5rem;
            background: transparent;
            border-bottom: 2px solid var(--hgt-border);
            padding-bottom: 0;
        }}
        .stTabs [data-baseweb="tab"] {{
            background: transparent !important;
            color: var(--text-muted) !important;
            border-radius: 10px 10px 0 0 !important;
            padding: 0.65rem 1.25rem !important;
            font-weight: 600 !important;
            border: none !important;
            border-bottom: 3px solid transparent !important;
            transition: all 0.2s ease !important;
        }}
        .stTabs [data-baseweb="tab"]:hover {{
            color: var(--hgt-orange) !important;
            background: var(--hgt-orange-glow) !important;
        }}
        .stTabs [aria-selected="true"][data-baseweb="tab"] {{
            color: var(--hgt-orange) !important;
            background: var(--hgt-orange-glow) !important;
            border-bottom-color: var(--hgt-orange) !important;
        }}

        /* ═══ DATAFRAME — tabla HGT ═══ */
        .stDataFrame, [data-testid="stDataFrame"] {{
            background: var(--bg-card) !important;
            border-radius: 12px !important;
            border: 1px solid var(--hgt-border) !important;
            box-shadow: var(--hgt-shadow) !important;
            overflow: hidden;
        }}

        /* ═══ METRICS ═══ */
        [data-testid="stMetric"] {{
            background: var(--bg-card);
            padding: 1rem 1.25rem;
            border-radius: 12px;
            border: 1px solid var(--hgt-border);
            box-shadow: var(--hgt-shadow);
            border-left: 4px solid var(--hgt-orange);
        }}
        [data-testid="stMetricValue"] {{
            color: var(--hgt-greyblue);
            font-weight: 700;
        }}
        [data-testid="stMetricLabel"] {{
            color: var(--text-muted);
            font-weight: 500;
        }}

        /* ═══ PAGE HEADER HGT ═══ */
        .hgt-page-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
            position: relative;
        }}
        .hgt-page-header::after {{
            content: '';
            position: absolute;
            bottom: 0; left: 0;
            width: 100px; height: 3px;
            background: var(--hgt-orange);
            border-radius: 2px;
        }}
        .hgt-page-header h1 {{
            margin: 0;
            font-size: 2rem;
            font-weight: 700;
            color: var(--hgt-greyblue);
            letter-spacing: -0.02em;
        }}
        .hgt-page-header .subtitle {{
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-top: 0.25rem;
        }}

        /* ═══ ALERTAS — Mapear st.success/error/info/warning a .alert ═══ */
        .stAlert, [data-testid="stAlert"] {{
            border-radius: 10px !important;
            border-left-width: 4px !important;
            padding: 0.85rem 1rem !important;
            font-weight: 500 !important;
        }}

        /* ═══ PROGRESS BAR ═══ */
        .stProgress > div > div > div > div {{
            background: var(--hgt-orange) !important;
        }}

        /* ═══ CHROMIUM HIDE ═══ */
        #MainMenu, footer {{visibility: hidden;}}
        header[data-testid="stHeader"] {{ background: transparent; }}
    </style>
    """, unsafe_allow_html=True)

load_css()

# ── Lógica de Sesión ─────────────────────────────────────────────────────────
if "user" not in st.session_state:
    st.session_state.user = None

# ── Función de Logout ───────────────────────────────────────────────────────
def logout():
    st.session_state.user = None
    st.rerun()

# ── PANTALLA DE LOGIN ───────────────────────────────────────────────────────
if st.session_state.user is None:
    # Aplicar fondo y estilo de card vía CSS inyectado
    st.markdown('<div class="login-background"></div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown('<div class="login-card-container">', unsafe_allow_html=True)
        with st.form("login_form"):
            if os.path.exists(LOGO_PATH):
                logo_b64 = base64.b64encode(open(LOGO_PATH, "rb").read()).decode()
                st.markdown(f'<div style="text-align:center; margin-bottom:20px;"><img src="data:image/png;base64,{logo_b64}" width="220"></div>', unsafe_allow_html=True)
            
            st.markdown('<h3 style="text-align:center; color:white; margin-top:0; letter-spacing:1px;">HGT CHILE LOGISTICS</h3>', unsafe_allow_html=True)
            st.markdown('<p style="text-align:center; color:rgba(255,255,255,0.7); font-size:0.9rem;">Gestión de Rendiciones</p>', unsafe_allow_html=True)
            
            username = st.text_input("Usuario", placeholder="ej: nombre@hgt.com")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("INICIAR SESIÓN", use_container_width=True)
            
            if submitted:
                user = db_verify_user(username, password)
                if user:
                    st.session_state.user = user
                    st.success(f"¡Bienvenido, {user['nombre']}!")
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<p style="text-align:center; color:white; font-size:0.8rem; margin-top:20px;">&copy; 2026 HGT Chile Logistics</p>', unsafe_allow_html=True)
    st.stop()


# ── NAVEGACIÓN BASADA EN ROLES ──────────────────────────────────────────────
user = st.session_state.user
roles = [r.strip() for r in user['role'].split(',')] if user['role'] else []

import views.rendicion as p_rendicion
import views.aprobaciones as p_aprob
import views.mantencion as p_mant
import views.admin_usuarios as p_admin
import views.encargado as p_enc

if "page" not in st.session_state:
    st.session_state.page = "rendicion"

# Super admin: tiene TODOS los privilegios (equivale a admin + jefatura + encargado + usuario)
is_super = user.get('username') == 'Super' or user.get('nombre') == 'Super'

with st.sidebar:
    st.markdown(f"**Usuario:** {user['nombre']}")
    role_display = [r.capitalize() for r in roles if r != 'jefatura']
    if is_super and 'Super admin' not in role_display:
        role_display.insert(0, '⭐ Super admin')
    st.markdown(f"**Roles:** {', '.join(role_display)}")
    st.divider()

    # Super puede ver TODO; cada rol ve lo suyo
    if 'usuario' in roles or not roles or is_super:
        if st.button("📝 Mis Rendiciones", use_container_width=True, key="nav_rendicion"):
            st.session_state.page = "rendicion"; st.rerun()
    if 'jefatura' in roles or 'admin' in roles or is_super:
        if st.button("👔 Aprobaciones", use_container_width=True, key="nav_aprobaciones"):
            st.session_state.page = "aprobaciones"; st.rerun()
    if 'encargado' in roles or 'admin' in roles or is_super:
        if st.button("💼 Gestión Encargado", use_container_width=True, key="nav_encargado"):
            st.session_state.page = "encargado"; st.rerun()
    if 'admin' in roles or is_super:
        if st.button("👥 Usuarios", use_container_width=True, key="nav_usuarios"):
            st.session_state.page = "usuarios"; st.rerun()
        if st.button("⚙️ Mantención", use_container_width=True, key="nav_mantencion"):
            st.session_state.page = "mantencion"; st.rerun()

    st.divider()
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        logout()

if st.session_state.page == "rendicion":
    p_rendicion.show()
elif st.session_state.page == "aprobaciones":
    p_aprob.show()
elif st.session_state.page == "encargado":
    p_enc.show()
elif st.session_state.page == "usuarios":
    p_admin.show()
elif st.session_state.page == "mantencion":
    p_mant.show()
