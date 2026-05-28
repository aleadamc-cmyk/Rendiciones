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
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&family=Inter:wght@400;600;700&display=swap');
        
        {custom_css}
        
        /* Adaptación Streamlit */
        .stApp {{
            font-family: 'Outfit', 'Inter', sans-serif !important;
            background-color: var(--bg-main) !important;
        }}
        
        [data-testid="stSidebar"] {{
            background-color: var(--hgt-greyblue) !important;
            color: var(--hgt-white) !important;
        }}
        
        [data-testid="stSidebar"] * {{
            color: var(--hgt-white) !important;
        }}

        [data-testid="stSidebarNav"] li a:hover, [data-testid="stSidebarNav"] li a[aria-current="page"] {{
            background-color: rgba(255, 102, 0, 0.1) !important;
            border-left: 4px solid var(--hgt-orange) !important;
            color: var(--hgt-orange) !important;
        }}

        /* Buttons HGT Style */
        .stButton>button, .stFormSubmitButton>button {{
            background-color: var(--hgt-orange) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 0.6rem 1.2rem !important;
            font-weight: 700 !important;
            transition: var(--spring) !important;
            box-shadow: var(--hgt-shadow) !important;
        }}
        
        .stButton>button:hover, .stFormSubmitButton>button:hover {{
            background-color: var(--hgt-orange-dark) !important;
            transform: translateY(-2px) !important;
            box-shadow: var(--hgt-shadow-hover) !important;
            color: white !important;
        }}

        /* Inputs */
        .stTextInput>div>div>input, .stNumberInput>div>div>input {{
            border-radius: 10px !important;
            border: 1.5px solid var(--hgt-border) !important;
        }}
        
        .stTextInput>div>div>input:focus {{
            border-color: var(--hgt-orange) !important;
            box-shadow: 0 0 0 3px var(--hgt-orange-glow) !important;
        }}

        /* Cards / Containers */
        .stExpander, div[data-testid="stVerticalBlock"] > div[style*="border"] {{
            background-color: var(--bg-card) !important;
            border-radius: 16px !important;
            border: 1px solid var(--hgt-border) !important;
            box-shadow: var(--hgt-shadow) !important;
            padding: 1rem !important;
        }}

        /* Login adaptation */
        .login-background {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background-image: url('https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&q=80&w=2000');
            background-size: cover;
            background-position: center;
            filter: brightness(0.4);
            z-index: -1;
        }}
        
        .stApp {{
            background-color: transparent !important;
        }}
        
        div[data-testid="stForm"] {{
            background: rgba(26, 34, 45, 0.8) !important;
            backdrop-filter: blur(20px) !important;
            border-radius: 24px !important;
            padding: 3rem !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-top: 3px solid #ff6b2b !important;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5) !important;
        }}
        
        .stTextInput label, .stPasswordInput label {{
            color: white !important;
        }}

        /* Hide deploy button */
        #MainMenu, footer {{visibility: hidden;}}
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

with st.sidebar:
    st.markdown(f"**Usuario:** {user['nombre']}")
    st.markdown(f"**Roles:** {', '.join([r.capitalize() for r in roles if r != 'jefatura'])}")
    st.divider()

    if 'usuario' in roles or not roles:
        if st.button("📝 Mis Rendiciones", use_container_width=True, key="nav_rendicion"):
            st.session_state.page = "rendicion"; st.rerun()
    if 'jefatura' in roles or 'admin' in roles:
        if st.button("👔 Aprobaciones", use_container_width=True, key="nav_aprobaciones"):
            st.session_state.page = "aprobaciones"; st.rerun()
    if 'encargado' in roles or 'admin' in roles:
        if st.button("💼 Gestión Encargado", use_container_width=True, key="nav_encargado"):
            st.session_state.page = "encargado"; st.rerun()
    if 'admin' in roles:
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
