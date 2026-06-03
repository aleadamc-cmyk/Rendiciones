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
        "SELECT id, nombre, total, fecha_registro, moneda FROM rendiciones_workflow WHERE LOWER(TRIM(email_jefatura)) = LOWER(?) AND status = 'pendiente'",
        params=(email_param.strip(),)
    )
    
    if df_p.empty:
        st.success("✅ No tienes rendiciones pendientes por aprobar.")
    else:
        for _, row in df_p.iterrows():
            moneda_row = row.get('moneda', 'CLP') or 'CLP'
            with st.expander(f"📦 Rendición #{row['id']} — {row['nombre']} | {format_curr(row['total'], moneda_row)}"):
                rid = row['id']
                data, pdf_fname, email_func, nombre_func, _ = db_get_rendicion(rid)
                
                st.markdown(f"**Funcionario:** {nombre_func} ({email_func})")
                
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
                
                moneda_row = data.get('moneda', 'CLP') or 'CLP'
                st.markdown(f"**Total: {format_curr(row['total'], moneda_row)}**")
                st.divider()
                
                pdf_bytes = generate_hgt_pdf(data)
                pdf_b64 = base64.b64encode(pdf_bytes).decode()
                st.markdown("#### 📄 Vista Previa PDF")
                st.markdown(f'<iframe src="data:application/pdf;base64,{pdf_b64}" width="100%" height="500px"></iframe>', unsafe_allow_html=True)
                
                st.markdown("#### ✍️ Aprobación / Rechazo")
                
                if data.get('email_funcionario', '').lower() == manager.get('email', '').lower():
                    st.error("⚠️ No puedes aprobar tu propia rendición.")
                else:
                    tab_apr, tab_rej = st.tabs(["✅ Aprobar", "❌ Rechazar"])
                    
                    with tab_apr:
                        st.write("Confirme su identidad ingresando su RUT:")
                        rut_input = st.text_input("RUT", key=f"rut_apr_{rid}")
                        if st.button("Aprobar Rendición", key=f"btn_apr_{rid}"):
                            if not rut_input:
                                st.error("⚠️ Debe ingresar su RUT.")
                            elif rut_input.strip() != manager.get('rut'):
                                st.error("⚠️ El RUT no coincide con el registrado.")
                            else:
                                data['fecha_aprobacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                data['jefe_id'] = manager.get('id')
                                data['jefe_sid'] = manager.get('sid')
                                data['jefe_rut'] = manager.get('rut')
                                data['jefe_nombre'] = manager.get('nombre')
                                pdf_final = generate_hgt_pdf(data)
                                db_approve(rid, pdf_final, data)
                                st.success("✅ Rendición aprobada correctamente.")
                                st.rerun()
                    
                    with tab_rej:
                        st.write("Ingrese el motivo del rechazo para notificar al funcionario:")
                        motivo = st.text_area("Motivo del Rechazo", key=f"motivo_rej_{rid}")
                        if st.button("Rechazar Rendición", key=f"btn_rej_{rid}"):
                            if not motivo:
                                st.error("⚠️ Debe ingresar un motivo de rechazo.")
                            else:
                                db_reject(rid, motivo)
                                try:
                                    smtp_conf = st.secrets["smtp"]
                                    subject = f"Rendición de Gastos RECHAZADA - {nombre_func}"
                                    body = (
                                        f"Estimado/a {nombre_func},\n\n"
                                        f"Su rendición de gastos #{rid} ha sido RECHAZADA.\n\n"
                                        f"Motivo:\n{motivo}\n\n"
                                        f"Puede ingresar al sistema para corregirla y volver a enviarla.\n\n"
                                        f"Saludos,\nSistema de Rendiciones HGT"
                                    )
                                    send_hgt_email(smtp_conf, email_func, subject, body)
                                    st.warning("Rendición rechazada. Se ha notificado al funcionario por correo.")
                                except Exception as e:
                                    st.warning(f"Rendición rechazada. No se pudo enviar correo: {e}")
                                st.rerun()

if __name__ == "__main__":
    show()
