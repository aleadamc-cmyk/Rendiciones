import streamlit as st
import pandas as pd
import os, sys, re
import sqlite3

# Rutas para importar utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    db_get_all, db_register_user, db_delete_user, db_update_user_roles,
    db_update_password, hash_pw, DB_PATH, db_get_jefaturas, process_id_card_with_ai,
    db_update_user_full, db_get_terminales, db_get_centros_costos,
    db_get_usuario_centros_costos, db_get_cuentas_contables,
    db_get_usuario_cc_cuentas,
    db_get_all_visible_users, is_super_user, SUPER_USERNAME,
)

def show():
    current_user = st.session_state.user
    is_super = is_super_user(current_user)

    st.markdown("""
    <style>
        div[data-testid="stForm"] label p,
        div[data-testid="stForm"] .stSelectbox label p,
        div[data-testid="stForm"] .stMultiSelect label p,
        div[data-testid="stForm"] .stTextInput label p { color: white !important; }
    </style>
    """, unsafe_allow_html=True)
    st.subheader("👥 Administración de Usuarios")

    # ── TAB 1: Lista y Gestión ──────────────────────────────────────────────
    tab_list, tab_add = st.tabs(["📋 Lista de Usuarios", "➕ Crear Usuario"])

    with tab_list:
        st.write("Gestiona todos los campos de los usuarios registrados.")
        # Listado filtrado: Super NO aparece para nadie excepto para sí mismo
        df_users = db_get_all_visible_users(current_user)
        if df_users.empty:
            st.info("No hay usuarios registrados.")
        else:
            # Opciones del selector; si el viewer es Super, marca a Super con candado
            def _fmt(row):
                nombre = row['nombre']
                email = row.get('email') or '—'
                roles = row.get('role') or ''
                badge = ""
                if row.get('username') == SUPER_USERNAME:
                    badge = " 🔒"
                return f"{nombre} ({email}) — {roles}{badge}"
            user_opts = { _fmt(r): r for _, r in df_users.iterrows() }
            selected_label = st.selectbox(
                "Seleccione un usuario para gestionar",
                options=list(user_opts.keys()),
                key="sel_user_admin",
            )
            u = user_opts[selected_label]
            target_is_super = (u.get('username') == SUPER_USERNAME)

            with st.form(f"edit_user_form_{u['id']}"):
                st.markdown(f"#### ✏️ Editando: {u['nombre']}")
                ec1, ec2 = st.columns(2)

                en_nombre = ec1.text_input("Nombre Completo", value=u['nombre'], disabled=target_is_super)
                en_email  = ec2.text_input("Email / Login", value=u['email'] or '', disabled=target_is_super)
                en_rut    = ec1.text_input("RUT", value=u['rut'] or '', help="Solo se permiten números y guión (-)", disabled=target_is_super)

                # Centros de Costo (multiselect)
                df_cc = db_get_centros_costos()
                cc_opts = df_cc['codigo_cc'].tolist()
                current_cc = db_get_usuario_centros_costos(u['id'])
                en_cc = ec1.multiselect("Centros de Costo", options=cc_opts, default=current_cc, key="edit_cc", disabled=target_is_super)

                # Cuentas por centro de costo
                df_ctas = db_get_cuentas_contables()
                cta_opts = df_ctas['codigo_cuenta'].tolist()
                current_cc_ctas = db_get_usuario_cc_cuentas(u['id'])
                en_cc_cuentas = {}
                for cc in en_cc:
                    default_ctas = current_cc_ctas.get(cc, [])
                    en_cc_cuentas[cc] = st.multiselect(
                        f"Cuentas para {cc}", options=cta_opts, default=default_ctas,
                        key=f"edit_ctas_{cc}", disabled=target_is_super
                    )

                # Gestión de Jefatura
                df_jefes = db_get_jefaturas()
                jefe_opts = ["No asignado"] + df_jefes['email'].tolist()
                jefe_names = {r['email']: r['nombre'] for _, r in df_jefes.iterrows()}
                current_jefe = u.get('email_jefatura')
                if current_jefe and current_jefe not in jefe_opts:
                    jefe_opts.append(current_jefe)
                en_jefatura = ec1.selectbox(
                    "Jefatura que Aprueba", options=jefe_opts,
                    index=jefe_opts.index(current_jefe) if current_jefe in jefe_opts else 0,
                    format_func=lambda x: f"{jefe_names.get(x, x)}",
                    disabled=target_is_super,
                )

                # Terminal asignado
                df_term = db_get_terminales()
                term_opts = ["No asignado"] + df_term['nombre'].tolist()
                current_term = u.get('terminal_asignado')
                if current_term and current_term not in term_opts:
                    term_opts.append(current_term)
                en_terminal = ec1.selectbox(
                    "Terminal Asignado", options=term_opts,
                    index=term_opts.index(current_term) if current_term in term_opts else 0,
                    disabled=target_is_super,
                )

                # Gestión de Roles
                valid_roles = ["usuario", "jefatura", "encargado", "admin"]
                if is_super:
                    valid_roles = valid_roles + ["super_admin"]
                current_roles = [r.strip() for r in str(u['role']).split(',') if r.strip()]
                current_roles_filtered = [r for r in current_roles if r in valid_roles]
                en_roles = ec2.multiselect(
                    "Roles asignados", valid_roles, default=current_roles_filtered,
                    disabled=target_is_super,
                )

                # Si es Super, mostrar aviso
                if target_is_super:
                    st.info(
                        "🔒 **Usuario Super (oculto al resto del sistema).** "
                        "Sus datos, contraseña y existencia solo pueden ser gestionados por el propio Super."
                    )

                if st.form_submit_button("💾 Guardar Cambios Generales", width='stretch', disabled=target_is_super):
                    if en_rut and not re.match(r'^[\d\-kK]+$', en_rut):
                        st.error("El RUT solo puede contener números, guión (-) y la letra K.")
                    else:
                        roles_str = ",".join(en_roles)
                        res = db_update_user_full(
                            u['id'], en_nombre, en_email, en_rut, "", roles_str,
                            email_jefatura=en_jefatura if en_jefatura != "No asignado" else None,
                            terminal_asignado=en_terminal if en_terminal != "No asignado" else None,
                            centros_costo=en_cc,
                            cc_cuentas=en_cc_cuentas
                        )
                        if res is True:
                            st.success("✅ Usuario actualizado correctamente.")
                            if u['email'] == current_user['email']:
                                st.session_state.user.update({
                                    'nombre': en_nombre, 'email': en_email, 'rut': en_rut, 'cc': en_cc, 'role': roles_str
                                })
                        else:
                            st.error(f"Error: {res}")

            st.divider()
            c1, c2 = st.columns(2)

            with c2:
                # Cambio de Contraseña — bloqueado para Super
                if target_is_super:
                    st.warning("🔒 La contraseña del Super solo puede ser modificada por el propio Super desde otro flujo (no expuesto en esta UI).")
                else:
                    with st.expander("🔑 Cambiar Contraseña"):
                        new_pw = st.text_input("Nueva contraseña", type="password", key=f"pw_{u['id']}")
                        if st.button("Actualizar Contraseña", key=f"btn_pw_{u['id']}"):
                            if new_pw:
                                db_update_password(u['id'], hash_pw(new_pw))
                                st.success("Contraseña actualizada.")
                            else:
                                st.error("Ingrese una contraseña.")

                st.divider()
                # Eliminar Usuario — bloqueado para Super y para uno mismo
                del_disabled = target_is_super or (u['email'] == current_user['email'])
                if st.button(
                    "🗑️ Eliminar Usuario", help="Esta acción no se puede deshacer",
                    key=f"btn_del_{u['id']}", type="primary", disabled=del_disabled
                ):
                    if u['email'] == current_user['email']:
                        st.error("No puedes eliminar tu propio usuario.")
                    else:
                        db_delete_user(u['id'], u['email'])
                        st.success(f"Usuario {u['nombre']} eliminado.")
                        st.rerun()

    # ── TAB 2: Crear Nuevo ─────────────────────────────────────────────────
    with tab_add:
        # 1. Escaneo de Cédula (Cámara o Archivo)
        with st.expander("📸 Automatizar con Cédula de Identidad", expanded=False):
            st.write("Puedes capturar la cédula con la cámara o subir una foto. Los datos (Nombre y RUT) se extraerán automáticamente.")
            
            tab_cam, tab_file = st.tabs(["📷 Cámara en Vivo", "📁 Subir Foto"])
            
            id_img = None
            with tab_cam:
                cam_file = st.camera_input("Capturar Cédula (Frontal)", key="id_camera")
                if cam_file: id_img = cam_file
            
            with tab_file:
                up_file = st.file_uploader("Seleccionar foto de la cédula", type=["jpg", "jpeg", "png"], key="id_file_up")
                if up_file: id_img = up_file

            if id_img and 'ocr_done' not in st.session_state:
                with st.spinner("Analizando imagen con Gemini..."):
                    res_ocr = process_id_card_with_ai(id_img)
                    if res_ocr.get("success"):
                        st.session_state.ocr_data = res_ocr['data']
                        st.session_state.ocr_done = True
                        st.success("✅ Imagen procesada con éxito.")
                    elif res_ocr.get("error") == "quota_exhausted":
                        st.warning(res_ocr.get("user_message", "Cuota de IA agotada. Ingresa los datos manualmente."))
                        st.session_state.ocr_done = True
                    else:
                        st.error(f"Error en OCR: {res_ocr.get('error')}")
            
            if st.button("🔄 Nueva Captura / Limpiar", key="reset_ocr"):
                if 'ocr_done' in st.session_state: del st.session_state.ocr_done
                if 'ocr_data' in st.session_state: del st.session_state.ocr_data
                st.rerun()

        # 2. Formulario de Registro
        st.markdown("""
        <style>
            div[data-testid="stForm"] button[key="btn_crear"] {
                background: linear-gradient(135deg, #ff6b2b, #ff8f4f) !important;
                color: white !important;
                border: none !important;
                font-weight: 600 !important;
                border-radius: 8px !important;
            }
        </style>
        """, unsafe_allow_html=True)
        with st.form("new_user_form"):
            st.write("Complete o verifique los datos para registrar un nuevo integrante.")
            nc1, nc2 = st.columns(2)
            
            # Valores por defecto desde OCR si existen
            d_nombre = st.session_state.ocr_data.get('nombre', '') if 'ocr_data' in st.session_state else ""
            d_rut    = st.session_state.ocr_data.get('rut', '')    if 'ocr_data' in st.session_state else ""
            
            n_nombre = nc1.text_input("Nombre Completo", value=d_nombre)
            n_email  = nc2.text_input("Email (será el login)")
            n_rut    = nc1.text_input("RUT", value=d_rut, help="Solo se permiten números y guión (-)")

            # Centros de Costo (multiselect)
            df_cc = db_get_centros_costos()
            n_cc = st.multiselect("Centros de Costo", options=df_cc['codigo_cc'].tolist(), key="new_cc")

            # Cuentas por centro de costo
            df_ctas = db_get_cuentas_contables()
            cta_opts = df_ctas['codigo_cuenta'].tolist()
            n_cc_cuentas = {}
            for cc in n_cc:
                n_cc_cuentas[cc] = st.multiselect(
                    f"Cuentas para {cc}", options=cta_opts,
                    key=f"new_ctas_{cc}"
                )

            n_pass   = nc1.text_input("Contraseña", type="password")
            
            # Selección de Jefatura
            df_jefes = db_get_jefaturas()
            jefe_opts = ["No asignado"] + df_jefes['email'].tolist()
            jefe_names = {r['email']: r['nombre'] for _, r in df_jefes.iterrows()}
            n_jefatura = nc2.selectbox("Jefatura que Aprueba", options=jefe_opts, 
                                        format_func=lambda x: f"{jefe_names.get(x, x)}")
            
            # Terminal asignado
            df_term = db_get_terminales()
            term_opts = ["No asignado"] + df_term['nombre'].tolist()
            n_terminal = st.selectbox("Terminal Asignado", options=term_opts)
            
            # Roles asignables: super_admin SOLO si quien crea es Super
            asignable_roles = ["usuario", "jefatura", "encargado", "admin"]
            if is_super:
                asignable_roles.append("super_admin")
            n_roles = st.multiselect("Asignar Roles", asignable_roles, default=["usuario"])
            

            
            col_s1, col_s2 = st.columns([1, 1])
            with col_s1:
                submit = st.form_submit_button("Crear Usuario", use_container_width=True, key="btn_crear")
            with col_s2:
                cancelar = st.form_submit_button("Cancelar", use_container_width=True)
            if cancelar:
                if 'ocr_done' in st.session_state: del st.session_state.ocr_done
                if 'ocr_data' in st.session_state: del st.session_state.ocr_data
                st.rerun()
            if submit:
                if not n_nombre or not n_email or not n_pass:
                    st.error("Nombre, Email y Contraseña son obligatorios.")
                elif n_rut and not re.match(r'^[\d\-kK]+$', n_rut):
                    st.error("El RUT solo puede contener números, guión (-) y la letra K.")
                elif 'super_admin' in n_roles and not is_super:
                    st.error("🚫 Solo el Super admin puede asignar el rol 'super_admin'.")
                else:
                    roles_str = ",".join(n_roles)
                    res = db_register_user(
                        n_nombre, n_email, n_pass, roles_str, n_rut, "",
                        email_jefatura=n_jefatura if n_jefatura != "No asignado" else None,
                        terminal_asignado=n_terminal if n_terminal != "No asignado" else None,
                        centros_costo=n_cc,
                        cc_cuentas=n_cc_cuentas
                    )
                    if res is True:
                        st.success(f"Usuario {n_nombre} creado con éxito.")
                        # Limpiar OCR state
                        if 'ocr_done' in st.session_state: del st.session_state.ocr_done
                        if 'ocr_data' in st.session_state: del st.session_state.ocr_data
                        st.toast(f"Usuario {n_nombre} creado!")
                    else:
                        st.error(f"Error al crear usuario: {res}")

if __name__ == "__main__":
    show()
