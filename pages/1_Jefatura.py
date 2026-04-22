"""
pages/1_Jefatura.py — Panel de aprobación de rendiciones
HGT Chile Logistics · Acceso exclusivo para jefatura
"""
import streamlit as st
import pandas as pd
import base64
import os, sys

# ── Importar utilidades desde el directorio padre ────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    generate_hgt_pdf, send_hgt_email, format_curr, init_db,
    db_get_pending, db_get_all, db_get_rendicion, db_approve, db_reject,
    LOGO_PATH
)

# ── Config de página ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Jefatura - HGT Rendiciones",
    page_icon="🏛️",
    layout="wide"
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
header[data-testid="stHeader"] { display: none !important; }
.block-container { padding-top: 1.5rem !important; }

/* Header panel */
.jefe-header {
    background: linear-gradient(135deg, #1a2233 0%, #212a37 100%);
    color: white; padding: 20px 28px; border-radius: 12px;
    display: flex; align-items: center; gap: 18px; margin-bottom: 24px;
}
.jefe-header h1 { margin: 0; font-size: 1.7rem; font-weight: 700; color: white; }
.jefe-header p  { margin: 0; font-size: 0.9rem; color: #aab4c4; }

/* Tarjeta de rendición */
.card-pendiente {
    border: 1px solid #e5e7eb; border-left: 4px solid #f59e0b;
    border-radius: 8px; padding: 14px 18px; margin-bottom: 10px;
    background: #fffbf5;
}
.card-aprobado {
    border: 1px solid #e5e7eb; border-left: 4px solid #10b981;
    border-radius: 8px; padding: 14px 18px; margin-bottom: 10px;
    background: #f0fdf4;
}
.card-rechazado {
    border: 1px solid #e5e7eb; border-left: 4px solid #ef4444;
    border-radius: 8px; padding: 14px 18px; margin-bottom: 10px;
    background: #fff5f5;
}
/* Badge */
.badge { display:inline-block; padding:3px 10px; border-radius:999px; font-size:0.78rem; font-weight:600; }
.badge-pendiente { background:#fef3c7; color:#92400e; }
.badge-aprobado  { background:#d1fae5; color:#065f46; }
.badge-rechazado { background:#fee2e2; color:#991b1b; }

.stButton>button { border-radius:6px; font-weight:600; min-height:42px; width:100%; }
</style>
""", unsafe_allow_html=True)

init_db()

# ════════════════════════════════════════════════════════════════════════════
# LOGIN
# ════════════════════════════════════════════════════════════════════════════
if "jefe_logged_in" not in st.session_state:
    st.session_state.jefe_logged_in = False

if not st.session_state.jefe_logged_in:
    # Pantalla de login
    col_login = st.columns([1, 1.5, 1])[1]
    with col_login:
        st.markdown("""
            <div style="text-align:center;padding:30px 0 10px;">
                <span style="font-size:3rem;">🏛️</span>
                <h2 style="color:#212a37;margin:8px 0 4px;">Panel de Jefatura</h2>
                <p style="color:#6b7280;">HGT Chile Logistics · Gestión de Rendiciones</p>
            </div>
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            pwd_input = st.text_input("Contraseña de acceso", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Ingresar →", use_container_width=True, type="primary")
            if submitted:
                expected = st.secrets.get("jefatura", {}).get("password", "hgt2025")
                if pwd_input == expected:
                    st.session_state.jefe_logged_in = True
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta.")
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# HEADER PANEL (después del login)
# ════════════════════════════════════════════════════════════════════════════
logo_b64 = ""
if os.path.exists(LOGO_PATH):
    logo_b64 = base64.b64encode(open(LOGO_PATH, "rb").read()).decode()

st.markdown(f"""
<div class="jefe-header">
    {'<img src="data:image/png;base64,' + logo_b64 + '" height="50">' if logo_b64 else '🏛️'}
    <div>
        <h1>Panel de Jefatura</h1>
        <p>Revisión y aprobación de rendiciones de gastos · HGT Chile Logistics</p>
    </div>
</div>
""", unsafe_allow_html=True)

col_logout = st.columns([4, 1])[1]
if col_logout.button("🚪 Cerrar sesión", use_container_width=True):
    st.session_state.jefe_logged_in = False
    st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════════════════════
tab_pending, tab_hist = st.tabs(["🟡 Pendientes de Aprobación", "📋 Historial Completo"])

# ─────────────────────────────────────────────
# TAB 1: PENDIENTES
# ─────────────────────────────────────────────
with tab_pending:
    df_pend = db_get_pending()
    if df_pend.empty:
        st.success("✅ No hay rendiciones pendientes de aprobación.")
    else:
        st.markdown(f"**{len(df_pend)} rendición(es) pendiente(s) de revisión:**")

        for _, row in df_pend.iterrows():
            rid   = int(row['id'])
            key_p = f"expand_{rid}"

            with st.container():
                st.markdown(f"""
                    <div class="card-pendiente">
                        🟡&nbsp; <strong>{row['nombre']}</strong> &nbsp;|&nbsp;
                        RUT: {row['rut']} &nbsp;|&nbsp;
                        CC: {row.get('centro_costo','')} &nbsp;|&nbsp;
                        <strong>Total: {format_curr(row['total'])}</strong> &nbsp;|&nbsp;
                        📅 {str(row['fecha_registro'])[:16]}
                    </div>
                """, unsafe_allow_html=True)

                with st.expander(f"▶ Revisar rendición #{rid} — {row['nombre']}", expanded=False):
                    data, pdf_fname, email_func, nombre_func = db_get_rendicion(rid)
                    if data is None:
                        st.error("Error al cargar los datos de esta rendición.")
                        continue

                    # Vista previa PDF
                    st.markdown("##### 📄 Vista Previa del PDF")
                    pdf_preview = generate_hgt_pdf(data)
                    pdf_b64     = base64.b64encode(pdf_preview).decode()
                    st.markdown(f"""
                        <iframe src="data:application/pdf;base64,{pdf_b64}"
                            width="100%" height="600px"
                            style="border:2px solid #212a37;border-radius:8px;margin-bottom:16px;">
                        </iframe>
                    """, unsafe_allow_html=True)

                    # Firma del Jefe
                    st.markdown("##### ✍️ Firma del Jefe Directo")
                    st.caption("Sube tu firma (PNG/JPG). Se insertará en el campo 'Firma Jefe Directo' del PDF.")
                    sc1, sc2 = st.columns([2, 1])
                    jefe_sig = sc1.file_uploader(
                        "Subir firma de jefe",
                        type=["png", "jpg", "jpeg"],
                        key=f"jefe_sig_{rid}",
                        label_visibility="collapsed"
                    )
                    jefe_sig_bytes = None
                    if jefe_sig:
                        sc2.image(jefe_sig, caption="Vista previa", width=160)
                        jefe_sig_bytes = jefe_sig.getvalue()

                    st.markdown("---")
                    col_rej, col_space, col_appr = st.columns([1, 0.3, 1])

                    # ── RECHAZAR ──
                    with col_rej:
                        if st.button(f"❌ Rechazar rendición #{rid}",
                                     key=f"reject_{rid}", use_container_width=True):
                            db_reject(rid)
                            smtp_conf = dict(st.secrets["smtp"])
                            # Email al funcionario
                            if email_func:
                                send_hgt_email(smtp_conf, email_func,
                                    f"Rendición #{rid} — Requiere corrección",
                                    (f"Estimado/a {nombre_func},\n\n"
                                     f"Tu rendición de gastos (ID #{rid}) ha sido observada por la jefatura "
                                     f"y requiere corrección antes de ser procesada.\n\n"
                                     f"Por favor, contacta a tu jefe directo para más información.\n\n"
                                     f"Saludos,\nSistema HGT Chile Logistics"))
                            st.warning(f"Rendición #{rid} rechazada. Se notificó al funcionario.")
                            st.rerun()

                    # ── APROBAR ──
                    with col_appr:
                        if st.button(f"✅ Aprobar rendición #{rid}",
                                     key=f"approve_{rid}", use_container_width=True, type="primary"):
                            with st.spinner("Generando PDF aprobado y enviando correos..."):
                                # Generar PDF con firma del jefe
                                data['firma_jefe_bytes'] = jefe_sig_bytes
                                pdf_aprobado = generate_hgt_pdf(data)

                                # Guardar en BD
                                db_approve(rid, pdf_aprobado)

                                smtp_conf     = dict(st.secrets["smtp"])
                                encargado_email = smtp_conf.get("recipient", "")
                                total_fmt     = format_curr(row['total'])

                                # Email al funcionario
                                if email_func:
                                    send_hgt_email(smtp_conf, email_func,
                                        f"✅ Rendición #{rid} Aprobada — {nombre_func}",
                                        (f"Estimado/a {nombre_func},\n\n"
                                         f"Tu rendición de gastos (ID #{rid}) por un total de "
                                         f"{total_fmt} ha sido APROBADA por tu jefe directo.\n\n"
                                         f"Adjunto encontrarás el documento firmado.\n\n"
                                         f"Saludos,\nSistema HGT Chile Logistics"),
                                        pdf_aprobado, pdf_fname)

                                # Email al encargado de rendiciones
                                if encargado_email:
                                    send_hgt_email(smtp_conf, encargado_email,
                                        f"Rendición Aprobada — {nombre_func} | {total_fmt}",
                                        (f"Estimado Encargado de Rendiciones,\n\n"
                                         f"La rendición de gastos del funcionario {nombre_func} "
                                         f"(RUT: {row['rut']}, ID #{rid}) por un total de {total_fmt} "
                                         f"ha sido aprobada por la jefatura.\n\n"
                                         f"Se adjunta el documento firmado para procesamiento.\n\n"
                                         f"Saludos,\nSistema HGT Chile Logistics"),
                                        pdf_aprobado, pdf_fname)

                                st.success(f"✅ Rendición #{rid} aprobada. Correos enviados a funcionario y encargado.")
                                st.balloons()
                                st.rerun()

# ─────────────────────────────────────────────
# TAB 2: HISTORIAL
# ─────────────────────────────────────────────
with tab_hist:
    df_all = db_get_all()
    if df_all.empty:
        st.info("No hay rendiciones registradas.")
    else:
        STATUS_ICON = {'pendiente': '🟡', 'aprobado': '🟢', 'rechazado': '🔴'}
        df_all['Estado'] = df_all['status'].map(
            lambda s: f"{STATUS_ICON.get(s, '⚪')} {s.capitalize()}")
        st.dataframe(
            df_all[['id', 'nombre', 'rut', 'centro_costo', 'total', 'Estado', 'fecha_registro']],
            use_container_width=True, hide_index=True,
            column_config={
                "id":             "ID",
                "nombre":         "Funcionario",
                "rut":            "RUT",
                "centro_costo":   "CC",
                "total":          st.column_config.NumberColumn("Total Rendido", format="$ %d"),
                "Estado":         "Estado",
                "fecha_registro": "Fecha Registro",
            }
        )

        # Descarga del PDF aprobado
        st.markdown("---")
        st.markdown("##### 📥 Descargar PDF de rendición aprobada")
        import sqlite3
        from utils import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT id, nombre, pdf_filename FROM rendiciones_workflow WHERE status='aprobado'")
        rows = c.fetchall()
        conn.close()
        if rows:
            opts = {f"#{r[0]} — {r[1]}": (r[0], r[2]) for r in rows}
            sel  = st.selectbox("Seleccionar rendición aprobada:", list(opts.keys()))
            if sel:
                rid_dl, fname_dl = opts[sel]
                conn2 = sqlite3.connect(DB_PATH)
                c2    = conn2.cursor()
                c2.execute("SELECT pdf_aprobado FROM rendiciones_workflow WHERE id=?", (rid_dl,))
                pdf_row = c2.fetchone()
                conn2.close()
                if pdf_row and pdf_row[0]:
                    st.download_button("💾 Descargar PDF Aprobado", data=bytes(pdf_row[0]),
                                       file_name=fname_dl, mime="application/pdf",
                                       use_container_width=True)
        else:
            st.info("No hay rendiciones aprobadas aún.")
