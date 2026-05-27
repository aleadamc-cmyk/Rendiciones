import streamlit as st
import pandas as pd
import base64
from datetime import datetime

from utils import (
    generate_hgt_pdf, format_curr,
    db_get_rendicion, db_approve, db_reject, _exec_df_query, send_hgt_email
)

def show():
    st.subheader("👔 Aprobación de Rendiciones")
    manager = st.session_state.get('user')
    if not manager:
        st.error("⚠️ Usuario no autenticado. Por favor, inicia sesión.")
        st.stop()
    
    email_param = manager.get('email') or ""
    df_p = _exec_df_query(
        "SELECT id, nombre, total, fecha_registro FROM rendiciones_workflow WHERE LOWER(TRIM(email_jefatura)) = LOWER(?) AND status = 'pendiente'",
        params=(email_param.strip(),)
    )
    
    if df_p.empty:
        st.success("✅ No tienes rendiciones pendientes por aprobar.")
    else:
        for _, row in df_p.iterrows():
            with st.expander(f"📦 Rendición #{row['id']} — {row['nombre']} | {format_curr(row['total'])}"):
                rid = row['id']
                data, pdf_fname, email_func, nombre_func, _ = db_get_rendicion(rid)
                
                # Detalle de gastos
                st.markdown("#### 📋 Detalle de Gastos")
                
                if not data['df_comision'].empty:
                    st.markdown("**Comisión de Servicios**")
                    st.dataframe(data['df_comision'], hide_index=True, width='stretch')
                
                if not data['df_alojamiento'].empty:
                    st.markdown("**Alojamiento**")
                    st.dataframe(data['df_alojamiento'], hide_index=True, width='stretch')
                
                if not data['df_alimentacion'].empty:
                    st.markdown("**Alimentación**")
                    st.dataframe(data['df_alimentacion'], hide_index=True, width='stretch')
                
                if not data['df_otros'].empty:
                    st.markdown("**Otros Gastos**")
                    st.dataframe(data['df_otros'], hide_index=True, width='stretch')
                
                st.markdown(f"**Total: {format_curr(row['total'])}**")
                st.divider()
                
                # Vista previa PDF
                pdf_bytes = generate_hgt_pdf(data)
                pdf_b64 = base64.b64encode(pdf_bytes).decode()
                st.markdown("#### 📄 Vista Previa PDF")
                st.markdown(f'<iframe src="data:application/pdf;base64,{pdf_b64}" width="100%" height="500px"></iframe>', unsafe_allow_html=True)
                
                st.markdown("#### ✍️ Aprobación de Jefatura (Firma Digital por Identidad)")
                st.write("Para aprobar, por favor confirme su identidad ingresando su RUT:")
                
                rut_input = st.text_input("Ingrese su RUT", key=f"rut_conf_{rid}")
                
                # Validar que el jefe no sea el mismo funcionario
                if data.get('email_funcionario', '').lower() == manager.get('email', '').lower():
                    st.error("⚠️ No puedes aprobar tu propia rendición. Debes seleccionar otro jefe.")
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Aprobar mediante Firma Digital", key=f"app_{rid}"):
                            if not rut_input:
                                st.error("⚠️ Debe ingresar su RUT para confirmar la aprobación.")
                            elif rut_input.strip() != manager.get('rut'):
                                st.error("⚠️ El RUT ingresado no coincide con su RUT registrado.")
                            else:
                                data['fecha_aprobacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                data['jefe_id'] = manager.get('id')
                                data['jefe_sid'] = manager.get('sid')
                                data['jefe_rut'] = manager.get('rut')
                                data['jefe_nombre'] = manager.get('nombre')
                                pdf_final = generate_hgt_pdf(data)
                                db_approve(rid, pdf_final, data)
                                st.success("✅ Aprobado y enviado a revisión final del Encargado.")
                                st.rerun()
                    with col2:
                        with st.popover("❌ Rechazar", width='stretch'):
                            reason = st.text_area("Motivo del rechazo", key=f"txt_rej_{rid}")
                            if st.button("Confirmar Rechazo", key=f"btn_rej_{rid}"):
                                if reason:
                                    db_reject(rid, reason)
                                    
                                    # Enviar correo de rechazo
                                    smtp_conf = st.secrets["smtp"]
                                    email_subject = f"Rendición de Gastos RECHAZADA - {data['nombre']}"
                                    email_body = (
                                        f"Estimado/a {data['nombre']},\n\n"
                                        f"Le informamos que su rendición de gastos #{rid} ha sido rechazada por la Jefatura.\n\n"
                                        f"Motivo del rechazo:\n{reason}\n\n"
                                        f"Por favor, ingrese al sistema para realizar las correcciones necesarias.\n\n"
                                        f"Saludos cordiales,\n"
                                        f"Sistema de Rendiciones HGT"
                                    )
                                    send_hgt_email(smtp_conf, email_func, email_subject, email_body)
                                    
                                    st.warning("Rechazada y notificada.")
                                    st.rerun()
                                else:
                                    st.error("Debe ingresar un motivo.")

if __name__ == "__main__":
    show()
