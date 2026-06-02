import streamlit as st
import pandas as pd
import base64
import io
from datetime import datetime

from utils import (
    generate_hgt_pdf, format_curr,
    db_get_rendicion, db_encargado_approve, db_encargado_reject, 
    db_get_encargado_stats, db_get_rendiciones_by_status,
    db_reassign_jefatura, db_get_jefaturas, _exec_df_query, send_hgt_email,
    db_get_dashboard_data
)

def show():
    st.title("💼 Panel de Control - Encargado")
    tab_gestion, tab_resumen = st.tabs(["📝 Gestión Diaria", "📊 Resumen Ejecutivo"])
    
    with tab_gestion:
        if 'enc_filter' not in st.session_state:
            st.session_state.enc_filter = "Todas"
        
        stats = db_get_encargado_stats()
        
        # ── KPI Cards Interactivos ──────────────────────────────────────────────
        col_all, col_pending, col_proc, col_wait = st.columns(4)
        
        with col_all:
            if st.button(f"📄 TODAS\n\n{stats['total']}", width='stretch'):
                st.session_state.enc_filter = "Todas"
        
        with col_pending:
            if st.button(f"⏳ POR PROCESAR\n\n{stats['espera']}", width='stretch'):
                st.session_state.enc_filter = "Por Procesar"
                
        with col_proc:
            if st.button(f"✅ PROCESADAS\n\n{stats['aprobadas']}", width='stretch'):
                st.session_state.enc_filter = "Procesadas"
    
        with col_wait:
            c_pend_jefe = _exec_df_query("SELECT count(*) FROM rendiciones_workflow WHERE status='pendiente'").iloc[0,0]
            if st.button(f"👔 EN JEFATURA\n\n{c_pend_jefe}", width='stretch'):
                st.session_state.enc_filter = "En Jefatura"
    
        manager = st.session_state.get('user')
        if not manager:
            st.error("⚠️ Usuario no autenticado.")
            st.stop()
        st.divider()
    
        # ── Obtención de Datos según Filtro ─────────────────────────────────────
        if st.session_state.enc_filter == "Todas":
            df_display = db_get_rendiciones_by_status(None)
        elif st.session_state.enc_filter == "Por Procesar":
            df_display = db_get_rendiciones_by_status(["APROBADO_POR_JEFATURA"])
        elif st.session_state.enc_filter == "En Jefatura":
            df_display = db_get_rendiciones_by_status(["pendiente"])
            # Solo mostrar las que le corresponden al manager logueado (case-insensitive)
            if not df_display.empty and 'email_jefatura' in df_display.columns and manager.get('email'):
                df_display = df_display[df_display['email_jefatura'].str.lower() == manager['email'].lower()]
        elif st.session_state.enc_filter == "Procesadas":
            df_display = db_get_rendiciones_by_status(["PROCESADO_ENCARGADO"])
            
        # ── Tabla de Resultados (Grilla Interactiva) ───────────────────────────
        if df_display.empty:
            st.info(f"No hay rendiciones en estado: {st.session_state.enc_filter}")
        else:
            # Encabezados de la grilla
            h_cols = st.columns([0.5, 2, 1.5, 1.2, 2, 2, 1.2, 0.6])
            h_cols[0].markdown("**ID**")
            h_cols[1].markdown("**Funcionario**")
            h_cols[2].markdown("**RUT**")
            h_cols[3].markdown("**Monto**")
            h_cols[4].markdown("**Estado**")
            h_cols[5].markdown("**Quien aprueba**")
            h_cols[6].markdown("**Fecha**")
            h_cols[7].markdown("**Ver**")
            st.divider()

            for _, row in df_display.iterrows():
                r_cols = st.columns([0.5, 2, 1.5, 1.2, 2, 2, 1.2, 0.6])
                r_cols[0].write(f"#{row['id']}")
                r_cols[1].write(row['nombre'])
                r_cols[2].write(row['rut'] if row['rut'] else "N/A")
                r_cols[3].write(format_curr(row['total']))
                
                # Color según estado
                status = row['status']
                st_color = "#3b82f6" # azul por defecto
                if "APROBADO" in status: st_color = "#10b981"
                if "RECHAZADO" in status: st_color = "#ef4444"
                if "PROCESADO" in status: st_color = "#8b5cf6"
                
                r_cols[4].markdown(f'<span style="color:{st_color}; font-weight:bold; font-size:0.85rem;">{status}</span>', unsafe_allow_html=True)
                r_cols[5].write(row.get('email_jefatura', ''))
                r_cols[6].write(str(row['fecha_registro'])[:16])
                
                # Botón Ojo 👁️
                if r_cols[7].button("👁️", key=f"eye_{row['id']}"):
                    st.session_state.selected_rid = row['id']
            
            st.markdown("---")
            
            # ── Detalle Seleccionado ─────────────────────────────────────────────
            if 'selected_rid' in st.session_state and st.session_state.selected_rid:
                rid_sel = st.session_state.selected_rid
                data, pdf_fname, email_func, nombre_func, pdf_aprobado = db_get_rendicion(rid_sel)
                
                # Buscar el estado actual en el dataframe filtrado
                row_info = df_display[df_display['id'] == rid_sel]
                if not row_info.empty:
                    status_current = row_info['status'].values[0]
                    monto_total = row_info['total'].values[0]
                else:
                    status_current = "Cargando..."
                    monto_total = 0
    
                st.subheader(f"🔍 Detalle: Rendición #{rid_sel}")
                
                c_det1, c_det2 = st.columns([1, 2])
                
                with c_det1:
                    st.info(f"**Estado Actual:** {status_current}")
                    st.write(f"**Funcionario:** {nombre_func}")
                    st.write(f"**Email:** {email_func}")
                    st.write(f"**Monto:** {format_curr(monto_total)}")
                    
                    # Reasignar Jefatura
                    st.markdown("---")
                    st.markdown("**🔄 Reasignar Jefatura**")
                    df_jefes = db_get_jefaturas()
                    if df_jefes.empty:
                        st.warning("No hay jefaturas registradas.")
                    else:
                        jefe_opts = {f"{r['nombre']} ({r['email']})": r['email'] for _, r in df_jefes.iterrows()}
                        new_jefe = st.selectbox("Nueva Jefatura", options=list(jefe_opts.keys()), key=f"reassign_{rid_sel}")
                        
                        if st.button("🔄 Reasignar y Reiniciar", key=f"btn_reassign_{rid_sel}", width='stretch', type="secondary"):
                            new_email = jefe_opts[new_jefe]
                            db_reassign_jefatura(rid_sel, new_email)
                            st.session_state.selected_rid = None
                            st.success(f"Jefatura reasignada a {new_jefe}. Rendición reiniciada a 'pendiente'.")
                            st.rerun()
                    
                    if status_current == 'APROBADO_POR_JEFATURA':
                        st.markdown("---")
                        st.success("✅ **Lista para Procesar Pago Final**")
                        if st.button("Aprobar y Procesar Final", key=f"btn_app_{rid_sel}", width='stretch', type="primary"):
                            db_encargado_approve(rid_sel)
                            st.session_state.selected_rid = None
                            st.success("Procesada con éxito.")
                            st.rerun()
                        
                        with st.popover("❌ Rechazar", width='stretch'):
                            coment = st.text_area("Motivo del rechazo", key=f"txt_rej_{rid_sel}")
                            if st.button("Confirmar Rechazo", key=f"btn_rej_{rid_sel}"):
                                if coment:
                                    db_encargado_reject(rid_sel, coment)
                                    
                                    # Enviar correo de rechazo
                                    smtp_conf = st.secrets["smtp"]
                                    email_subject = f"Rendición de Gastos RECHAZADA - {nombre_func}"
                                    email_body = (
                                        f"Estimado/a {nombre_func},\n\n"
                                        f"Le informamos que su rendición de gastos #{rid_sel} ha sido rechazada por el Encargado.\n\n"
                                        f"Motivo del rechazo:\n{coment}\n\n"
                                        f"Por favor, ingrese al sistema para realizar las correcciones necesarias.\n\n"
                                        f"Saludos cordiales,\n"
                                        f"Sistema de Rendiciones HGT"
                                    )
                                    send_hgt_email(smtp_conf, email_func, email_subject, email_body)
                                    
                                    st.session_state.selected_rid = None
                                    st.warning("Rechazada y notificada.")
                                    st.rerun()
                                else: st.error("Debe ingresar motivo.")
    
                with c_det2:
                    # Detalle de gastos
                    st.markdown("#### 📋 Detalle de Gastos")
                    
                    if 'data' in locals() and data:
                        if not data.get('df_comision', pd.DataFrame()).empty:
                            st.markdown("**Comisión de Servicios**")
                            st.dataframe(data['df_comision'], hide_index=True, width='stretch')
                        
                        if not data.get('df_alojamiento', pd.DataFrame()).empty:
                            st.markdown("**Alojamiento**")
                            st.dataframe(data['df_alojamiento'], hide_index=True, width='stretch')
                        
                        if not data.get('df_alimentacion', pd.DataFrame()).empty:
                            st.markdown("**Alimentación**")
                            st.dataframe(data['df_alimentacion'], hide_index=True, width='stretch')
                        
                        if not data.get('df_otros', pd.DataFrame()).empty:
                            st.markdown("**Otros Gastos**")
                            st.dataframe(data['df_otros'], hide_index=True, width='stretch')
                        
                        st.markdown(f"**Total: {format_curr(monto_total)}**")
                    
                    st.divider()
                    
                    # Vista previa PDF
                    if pdf_aprobado:
                        pdf_bytes = pdf_aprobado
                    else:
                        pdf_bytes = generate_hgt_pdf(data)
                    
                    pdf_b64 = base64.b64encode(pdf_bytes).decode()
                    pdf_html = f'<iframe src="data:application/pdf;base64,{pdf_b64}" width="100%" height="600px"></iframe>'
                    
                    with st.expander("👁️ Vista Previa del Documento y Anexos", expanded=True):
                        st.markdown(pdf_html, unsafe_allow_html=True)
                        st.download_button("⬇️ Descargar Copia PDF", data=pdf_bytes, file_name=f"Rendicion_{rid_sel}.pdf", mime="application/pdf")

    with tab_resumen:
        st.subheader("📊 Dashboard de Distribución")

        df_raw = db_get_dashboard_data()

        if df_raw.empty:
            st.info("No hay datos en rendiciones_detalles. Los datos aparecerán cuando se registren rendiciones en la nueva estructura.")
            st.markdown("""
            **Vista previa desde rendiciones_workflow (histórico):**
            """)
            df_hist = _exec_df_query(
                "SELECT id, nombre, centro_costo, total, fecha_registro, status FROM rendiciones_workflow "
                "WHERE status IN ('PROCESADO_ENCARGADO','PROCESADO_FINAL') ORDER BY fecha_registro DESC"
            )
            if not df_hist.empty:
                df_hist["fecha_registro"] = pd.to_datetime(df_hist["fecha_registro"])
                st.dataframe(df_hist, width='stretch', hide_index=True)
                csv_hist = df_hist.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Descargar Histórico (CSV)", data=csv_hist,
                                   file_name="rendiciones_historicas.csv", mime="text/csv")
        else:
            # ── Filtros ────────────────────────────────────────────────────
            df_raw["fecha_gasto"] = pd.to_datetime(df_raw["fecha_gasto"])
            min_date = df_raw["fecha_gasto"].min().date()
            max_date = df_raw["fecha_gasto"].max().date()

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                d_from = st.date_input("Desde", min_date, min_value=min_date, max_value=max_date)
            with col_f2:
                d_to = st.date_input("Hasta", max_date, min_value=min_date, max_value=max_date)

            # ── Dimensión de agrupación ───────────────────────────────────
            group_dim = st.selectbox("Agrupar por", [
                "colaborador", "sucursal", "centro_costo", "codigo_cuenta", "concepto_amigable"
            ], format_func=lambda x: {
                "colaborador": "Usuario",
                "sucursal": "Sucursal",
                "centro_costo": "Centro de Costo",
                "codigo_cuenta": "Cuenta Contable",
                "concepto_amigable": "Concepto Amigable"
            }.get(x, x))

            # Filtrar por rango
            mask = (df_raw["fecha_gasto"].dt.date >= d_from) & (df_raw["fecha_gasto"].dt.date <= d_to)
            df_filt = df_raw[mask].copy()

            if df_filt.empty:
                st.warning("Sin datos en el rango seleccionado.")
            else:
                # ── Agregación ────────────────────────────────────────────
                label_map = {
                    "colaborador": "colaborador",
                    "sucursal": "sucursal",
                    "centro_costo": "centro_costo",
                    "codigo_cuenta": "codigo_cuenta",
                    "concepto_amigable": "concepto_amigable",
                }
                grp_col = label_map[group_dim]

                df_grp = df_filt.groupby(grp_col).agg(
                    Transacciones=("id", "count"),
                    Monto_Total=("monto_total", "sum")
                ).reset_index().sort_values("Monto_Total", ascending=False)

                df_grp.rename(columns={
                    grp_col: {
                        "colaborador": "Usuario",
                        "sucursal": "Sucursal",
                        "centro_costo": "Centro de Costo",
                        "codigo_cuenta": "Cuenta Contable",
                        "concepto_amigable": "Concepto Amigable"
                    }.get(grp_col, grp_col),
                    "Transacciones": "N° Transacciones",
                    "Monto_Total": "Monto Total ($)"
                }, inplace=True)

                total_tx = df_grp["N° Transacciones"].sum()
                total_monto = df_grp["Monto Total ($)"].sum()

                total_row = pd.DataFrame([{
                    list(df_grp.columns)[0]: "TOTAL GENERAL",
                    "N° Transacciones": total_tx,
                    "Monto Total ($)": total_monto
                }])
                df_final = pd.concat([df_grp, total_row], ignore_index=True)

                st.dataframe(
                    df_final.style.format({"Monto Total ($)": "$ {:,.0f}"}),
                    width='stretch', hide_index=True
                )

                # ── Exportar a Excel ───────────────────────────────────────
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_final.to_excel(writer, sheet_name='Dashboard', index=False)
                    # Hoja detalle
                    df_filt.to_excel(writer, sheet_name='Detalle', index=False)
                excel_bytes = output.getvalue()

                st.download_button(
                    "⬇️ Exportar a Excel",
                    data=excel_bytes,
                    file_name=f"Dashboard_Rendiciones_{d_from}_a_{d_to}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

if __name__ == "__main__":
    show()
