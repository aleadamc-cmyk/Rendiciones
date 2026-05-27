import streamlit as st
import pandas as pd
import os, sys, re
import sqlite3

# Rutas para importar utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (
    db_get_all, db_register_user, db_delete_user, db_update_user_roles,
    db_update_password, hash_pw, DB_PATH, db_get_jefaturas, process_id_card_with_ai,
    db_update_user_full
)

def show():
    st.subheader("👥 Administración de Usuarios")
    
    # ── TAB 1: Lista y Gestión ──────────────────────────────────────────────
    tab_list, tab_add = st.tabs(["📋 Lista de Usuarios", "➕ Crear Usuario"])
    
    with tab_list:
        st.write("Gestiona todos los campos de los usuarios registrados.")
        df_users = db_get_all("usuarios")
        if df_users.empty:
            st.info("No hay usuarios registrados.")
        else:
            # Seleccionar usuario para editar
            user_opts = {f"{r['nombre']} ({r['email']})": r for _, r in df_users.iterrows()}
            selected_label = st.selectbox("Seleccione un usuario para gestionar", options=list(user_opts.keys()), key="sel_user_admin")
            u = user_opts[selected_label]
            
            with st.form(f"edit_user_form_{u['id']}"):
                st.markdown(f"#### ✏️ Editando: {u['nombre']}")
                ec1, ec2 = st.columns(2)
                
                # Campos editables
                en_nombre = ec1.text_input("Nombre Completo", value=u['nombre'])
                en_email  = ec2.text_input("Email / Login", value=u['email'])
                en_rut    = ec1.text_input("RUT", value=u['rut'], help="Solo se permiten números y guión (-)")
                en_cc     = ec2.text_input("Centro Costo", value=u.get('centro_costo', ''))
                
                # Gestión de Jefatura
                df_jefes = db_get_jefaturas()
                jefe_opts = ["No asignado"] + df_jefes['email'].tolist()
                jefe_names = {r['email']: r['nombre'] for _, r in df_jefes.iterrows()}
                current_jefe = u.get('email_jefatura')
                if current_jefe and current_jefe not in jefe_opts:
                    jefe_opts.append(current_jefe)
                
                en_jefatura = ec1.selectbox("Jefatura que Aprueba", options=jefe_opts, 
                                            index=jefe_opts.index(current_jefe) if current_jefe in jefe_opts else 0,
                                            format_func=lambda x: f"{jefe_names.get(x, x)}")
                
                # Gestión de Roles
                valid_roles = ["usuario", "jefatura", "encargado", "admin"]
                current_roles = [r.strip() for r in str(u['role']).split(',') if r.strip()]
                current_roles_filtered = [r for r in current_roles if r in valid_roles]
                
                en_roles = ec2.multiselect("Roles asignados", valid_roles, default=current_roles_filtered)
                
                if st.form_submit_button("💾 Guardar Cambios Generales", width='stretch'):
                    if en_rut and not re.match(r'^[\d-]+$', en_rut):
                        st.error("El RUT solo puede contener números y guión (-).")
                    else:
                        roles_str = ",".join(en_roles)
                        res = db_update_user_full(
                            u['id'], en_nombre, en_email, en_rut, en_cc, roles_str,
                            email_jefatura=en_jefatura if en_jefatura != "No asignado" else None
                        )
                        if res is True:
                            st.success("Usuario actualizado correctamente.")
                            # Actualizar sesión si es el mismo usuario
                            if u['email'] == st.session_state.user['email']:
                                st.session_state.user.update({
                                    'nombre': en_nombre, 'email': en_email, 'rut': en_rut, 'cc': en_cc, 'role': roles_str
                                })
                            st.rerun()
                        else:
                            st.error(f"Error: {res}")

            st.divider()
            c1, c2 = st.columns(2)

            with c2:
                # Cambio de Contraseña
                with st.expander("🔑 Cambiar Contraseña"):
                    new_pw = st.text_input("Nueva contraseña", type="password", key=f"pw_{u['id']}")
                    if st.button("Actualizar Contraseña", key=f"btn_pw_{u['id']}"):
                        if new_pw:
                            db_update_password(u['id'], hash_pw(new_pw))
                            st.success("Contraseña actualizada.")
                        else:
                            st.error("Ingrese una contraseña.")
                
                st.divider()
                # Eliminar Usuario
                if st.button("🗑️ Eliminar Usuario", type="secondary", help="Esta acción no se puede deshacer", key=f"btn_del_{u['id']}"):
                    if u['email'] == st.session_state.user['email']:
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
                with st.spinner("Analizando imagen..."):
                    res_ocr = process_id_card_with_ai(id_img)
                    if res_ocr.get("success"):
                        st.session_state.ocr_data = res_ocr['data']
                        st.session_state.ocr_done = True
                        st.success("Imagen procesada con éxito.")
                    else:
                        st.error(f"Error en OCR: {res_ocr.get('error')}")
            
            if st.button("🔄 Nueva Captura / Limpiar", key="reset_ocr"):
                if 'ocr_done' in st.session_state: del st.session_state.ocr_done
                if 'ocr_data' in st.session_state: del st.session_state.ocr_data
                st.rerun()

        # 2. Formulario de Registro
        with st.form("new_user_form"):
            st.write("Complete o verifique los datos para registrar un nuevo integrante.")
            nc1, nc2 = st.columns(2)
            
            # Valores por defecto desde OCR si existen
            d_nombre = st.session_state.ocr_data.get('nombre', '') if 'ocr_data' in st.session_state else ""
            d_rut    = st.session_state.ocr_data.get('rut', '')    if 'ocr_data' in st.session_state else ""
            
            n_nombre = nc1.text_input("Nombre Completo", value=d_nombre)
            n_email  = nc2.text_input("Email (será el login)")
            n_rut    = nc1.text_input("RUT", value=d_rut, help="Solo se permiten números y guión (-)")
            n_cc     = nc2.text_input("Centro de Costo (Alfanumérico, máx 15)", max_chars=15)
            n_pass   = nc1.text_input("Contraseña", type="password")
            
            # Selección de Jefatura
            df_jefes = db_get_jefaturas()
            jefe_opts = ["No asignado"] + df_jefes['email'].tolist()
            jefe_names = {r['email']: r['nombre'] for _, r in df_jefes.iterrows()}
            n_jefatura = nc2.selectbox("Jefatura que Aprueba", options=jefe_opts, 
                                        format_func=lambda x: f"{jefe_names.get(x, x)}")
            
            n_roles = st.multiselect("Asignar Roles", ["usuario", "jefatura", "encargado", "admin"], default=["usuario"])
            

            
            submit = st.form_submit_button("Crear Usuario", width='stretch')
            if submit:
                if not n_nombre or not n_email or not n_pass:
                    st.error("Nombre, Email y Contraseña son obligatorios.")
                elif n_rut and not re.match(r'^[\d-]+$', n_rut):
                    st.error("El RUT solo puede contener números y guión (-).")
                else:
                    roles_str = ",".join(n_roles)
                    res = db_register_user(
                        n_nombre, n_email, n_pass, roles_str, n_rut, n_cc, 
                        email_jefatura=n_jefatura if n_jefatura != "No asignado" else None
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
