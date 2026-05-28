import streamlit as st
import pandas as pd

from utils import db_get_trayectos, db_get_jefaturas, db_save_trayectos, db_save_jefaturas, db_get_terminales, db_save_terminales, db_get_cuentas_contables, db_save_cuentas_contables, db_get_centros_costos, db_save_centros_costos, db_get_centro_costo_cuentas, db_set_centro_costo_cuentas, _get_conn

def show():
    st.subheader("⚙️ Mantención del Sistema")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🚀 Trayectos y Costos", "👔 Gestión de Jefaturas", "📍 Terminales", "📒 Cuentas Contables", "💰 Centros de Costos"])
    
    # ── TAB 1: Trayectos ───────────────────────────────────────────────────
    with tab1:
        st.write("Actualiza los kilómetros base, peajes y factores para cada ruta.")
        df_tr = db_get_trayectos()
        edited_tr = st.data_editor(
            df_tr,
            num_rows="dynamic",
            width='stretch',
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "origen": "Origen",
                "destino": "Destino",
                "km_base": "KM Base",
                "multiplicador_peaje": st.column_config.NumberColumn("Mult. Peaje", help="Multiplicador para peajes (si aplica)"),
                "monto_peaje_base": "Monto Peaje ($)",
                "factor": st.column_config.NumberColumn("Factor", help="Factor multiplicador para KM", step=0.5, format="%.1f"),
                "alimentacion": st.column_config.NumberColumn("Alimentación ($)", help="Valor máximo alimentación por persona", step=1000, format="$ %d")
            },
            key="tr_editor"
        )
        if st.button("💾 Guardar Trayectos"):
            res = db_save_trayectos(edited_tr)
            if res is True:
                st.success("✅ Trayectos actualizados.")
                st.rerun()
            else:
                st.error(f"❌ Error: {res}")

    # ── TAB 2: Jefaturas ───────────────────────────────────────────────────
    with tab2:
        st.write("Registra los nombres y correos de las jefaturas autorizadas.")
        df_jf = db_get_jefaturas()
        edited_jf = st.data_editor(
            df_jf,
            num_rows="dynamic",
            width='stretch',
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "nombre": "Nombre del Jefe",
                "email": "Correo Electrónico"
            },
            key="jf_editor"
        )
        if st.button("💾 Guardar Jefaturas"):
            res = db_save_jefaturas(edited_jf)
            if res is True:
                st.success("✅ Jefaturas actualizadas.")
                st.rerun()
            else:
                st.error(f"❌ Error: {res}")

    # ── TAB 3: Terminales ─────────────────────────────────────────────────
    with tab3:
        st.write("Mantenedor de terminales (origen/destino).")

        if st.button("➕ Agregar Terminal"):
            st.session_state.show_form_terminal = not st.session_state.get('show_form_terminal', False)

        if st.session_state.get('show_form_terminal'):
            with st.form("form_terminal", clear_on_submit=True):
                f_nombre = st.text_input("Nombre", placeholder="Ej: Placilla (PLA)")
                f_codigo = st.text_input("Código Interno", placeholder="Ej: PLA")
                f_activo = st.checkbox("Activo", value=True)
                col_s1, col_s2 = st.columns([1, 1])
                with col_s1:
                    guardar = st.form_submit_button("Guardar", use_container_width=True)
                with col_s2:
                    cancelar = st.form_submit_button("Cancelar", use_container_width=True)
                if cancelar:
                    st.session_state.show_form_terminal = False
                    st.rerun()
                if guardar:
                    if f_nombre and f_codigo:
                        conn = _get_conn()
                        c = conn.cursor()
                        c.execute("INSERT INTO terminales (nombre, codigo_interno, activo) VALUES (?, ?, ?)",
                                  (f_nombre, f_codigo, int(f_activo)))
                        conn.commit()
                        conn.close()
                        st.session_state.show_form_terminal = False
                        st.success("✅ Terminal agregado.")
                        st.rerun()
                    else:
                        st.error("Nombre y código son obligatorios.")

        df_trm = db_get_terminales()
        edited_trm = st.data_editor(
            df_trm,
            num_rows="dynamic",
            width='stretch',
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "nombre": st.column_config.TextColumn("Nombre", required=True),
                "codigo_interno": st.column_config.TextColumn("Código Interno", required=True),
                "activo": st.column_config.CheckboxColumn("Activo")
            },
            key="trm_editor"
        )
        if st.button("💾 Guardar Cambios"):
            res = db_save_terminales(edited_trm)
            if res is True:
                st.success("✅ Terminales actualizados.")
                st.rerun()
            else:
                st.error(f"❌ Error: {res}")

    # ── TAB 4: Cuentas Contables ──────────────────────────────────────────
    with tab4:
        st.write("Mapeo de cuentas contables del ERP a conceptos amigables para el usuario.")

        if st.button("➕ Agregar Cuenta Contable"):
            st.session_state.show_form_cc = not st.session_state.get('show_form_cc', False)

        if st.session_state.get('show_form_cc'):
            with st.form("form_cc", clear_on_submit=True):
                f_codigo = st.text_input("Código Cuenta", placeholder="Ej: 750520")
                f_detalle = st.text_input("Detalle", placeholder="Ej: Gastos Viaje")
                f_concepto = st.text_input("Concepto Amigable", placeholder="Ej: Alimentación")
                col_s1, col_s2 = st.columns([1, 1])
                with col_s1:
                    guardar = st.form_submit_button("Guardar", use_container_width=True)
                with col_s2:
                    cancelar = st.form_submit_button("Cancelar", use_container_width=True)
                if cancelar:
                    st.session_state.show_form_cc = False
                    st.rerun()
                if guardar:
                    if f_codigo and f_detalle and f_concepto:
                        conn = _get_conn()
                        c = conn.cursor()
                        c.execute("INSERT INTO cuentas_contables (codigo_cuenta, detalle_1, concepto_amigable) VALUES (?, ?, ?)",
                                  (f_codigo, f_detalle, f_concepto))
                        conn.commit()
                        conn.close()
                        st.session_state.show_form_cc = False
                        st.success("✅ Cuenta contable agregada.")
                        st.rerun()
                    else:
                        st.error("Todos los campos son obligatorios.")

        df_cc = db_get_cuentas_contables()
        edited_cc = st.data_editor(
            df_cc,
            num_rows="dynamic",
            width='stretch',
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "codigo_cuenta": st.column_config.TextColumn("Código Cuenta", required=True),
                "detalle_1": st.column_config.TextColumn("Detalle", required=True),
                "concepto_amigable": st.column_config.TextColumn("Concepto Amigable", required=True),
            },
            key="cc_editor"
        )
        if st.button("💾 Guardar Cuentas Contables"):
            res = db_save_cuentas_contables(edited_cc)
            if res is True:
                st.success("✅ Cuentas contables actualizadas.")
                st.rerun()
            else:
                st.error(f"❌ Error: {res}")

    # ── TAB 5: Centros de Costos ──────────────────────────────────────────
    with tab5:
        st.write("Mantenedor de centros de costo (departamento / área financiera).")

        if st.button("➕ Agregar Centro de Costo"):
            st.session_state.show_form_cc2 = not st.session_state.get('show_form_cc2', False)

        if st.session_state.get('show_form_cc2'):
            with st.form("form_cc2", clear_on_submit=True):
                f_codigo_cc = st.text_input("Código CC", placeholder="Ej: SMLG00275")
                f_detalle_cc = st.text_input("Detalle Departamento", placeholder="Ej: GAV RRHH")
                col_s1, col_s2 = st.columns([1, 1])
                with col_s1:
                    guardar = st.form_submit_button("Guardar", use_container_width=True)
                with col_s2:
                    cancelar = st.form_submit_button("Cancelar", use_container_width=True)
                if cancelar:
                    st.session_state.show_form_cc2 = False
                    st.rerun()
                if guardar:
                    if f_codigo_cc and f_detalle_cc:
                        conn = _get_conn()
                        c = conn.cursor()
                        c.execute("INSERT INTO centros_costos (codigo_cc, detalle_cc) VALUES (?, ?)",
                                  (f_codigo_cc, f_detalle_cc))
                        conn.commit()
                        conn.close()
                        st.session_state.show_form_cc2 = False
                        st.success("✅ Centro de costo agregado.")
                        st.rerun()
                    else:
                        st.error("Todos los campos son obligatorios.")

        df_cc2 = db_get_centros_costos()
        edited_cc2 = st.data_editor(
            df_cc2,
            num_rows="dynamic",
            width='stretch',
            column_config={
                "codigo_cc": st.column_config.TextColumn("Código CC", required=True),
                "detalle_cc": st.column_config.TextColumn("Detalle Departamento", required=True),
            },
            key="cc2_editor"
        )
        if st.button("💾 Guardar Centros de Costo"):
            res = db_save_centros_costos(edited_cc2)
            if res is True:
                st.success("✅ Centros de costo actualizados.")
                st.rerun()
            else:
                st.error(f"❌ Error: {res}")

        st.divider()
        st.markdown("#### 🔗 Asignar Cuentas Contables a Centro de Costo")
        df_cc_list = db_get_centros_costos()
        cc_options = df_cc_list['codigo_cc'].tolist()
        if cc_options:
            sel_cc = st.selectbox("Seleccionar Centro de Costo", options=cc_options, key="cc_asign")
            assigned = db_get_centro_costo_cuentas(sel_cc)
            df_ctas = db_get_cuentas_contables()
            cta_options = df_ctas['codigo_cuenta'].tolist()
            sel_ctas = st.multiselect("Cuentas Contables asignadas", options=cta_options, default=assigned, key="cta_asign")
            if st.button("💾 Guardar Asignación"):
                db_set_centro_costo_cuentas(sel_cc, sel_ctas)
                st.success(f"✅ Asignación actualizada para {sel_cc}.")
                st.rerun()

if __name__ == "__main__":
    show()
