import streamlit as st
import pandas as pd

from utils import db_get_trayectos, db_get_jefaturas, db_save_trayectos, db_save_jefaturas

def show():
    st.subheader("⚙️ Mantención del Sistema")
    
    tab1, tab2 = st.tabs(["🚀 Trayectos y Costos", "👔 Gestión de Jefaturas"])
    
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

if __name__ == "__main__":
    show()
