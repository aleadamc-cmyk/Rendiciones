import streamlit as st
import pandas as pd
from datetime import datetime
import base64

from utils import (
    generate_hgt_pdf, format_curr,
    db_submit_rendicion, db_update_rendicion, db_get_user_rendiciones, db_get_rendicion,
    db_get_trayectos_dict, db_get_jefaturas, send_hgt_email,
    process_receipt_with_ai, db_get_cuentas_contables,
    db_get_usuario_centros_costos, db_get_centros_costos, db_get_centro_costo_cuentas,
    db_get_all_centro_costo_cuentas, db_get_usuario_cc_cuentas, db_get_topes_usd_dict
)

def _calc_subtotals(df_aloj, df_alim, df_otros):
    """Calcula subtotales de cada categoría de gasto."""
    return {
        'st_alojamiento': pd.to_numeric(df_aloj['Monto'], errors='coerce').fillna(0).sum(),
        'st_alimentacion': pd.to_numeric(df_alim['Monto'], errors='coerce').fillna(0).sum(),
        'st_otros': pd.to_numeric(df_otros['Monto'], errors='coerce').fillna(0).sum()
    }

def _build_rendicion_data(nombre, rut, cc, email_func, email_jefe, anticipo, f_ant, user, df_comision, df_aloj, df_alim, df_otros, receipt_photos, moneda='CLP'):
    """Construye el diccionario de datos para la rendición."""
    subtotals = _calc_subtotals(df_aloj, df_alim, df_otros)
    return {
        "nombre": nombre, "rut": rut, "centro_costo": cc, "email_funcionario": email_func,
        "email_jefatura": email_jefe, "anticipo": anticipo, "fecha_anticipo": f_ant,
        "user_id": user.get('id'), "user_sid": user.get('sid'),
        "df_comision": df_comision, "df_alojamiento": df_aloj, 
        "df_alimentacion": df_alim, "df_otros": df_otros,
        "fecha_rendicion": datetime.now().strftime("%d/%m/%Y"),
        "receipt_photos": receipt_photos,
        "moneda": moneda,
        **subtotals
    }

def _cuentas_para_cc(codigo_cc, usuario_id=None):
    """Retorna cuentas contables filtradas por centro de costo.
    Busca primero en centro_costo_cuenta, luego en usuario_centro_costo_cuenta."""
    df = db_get_cuentas_contables()
    codigos = db_get_centro_costo_cuentas(codigo_cc)
    if codigos:
        df = df[df['codigo_cuenta'].isin(codigos)]
    elif usuario_id:
        # Fallback: buscar cuentas asignadas directamente al usuario para este CC
        user_cc_cuentas = db_get_usuario_cc_cuentas(usuario_id)
        codigos_usuario = user_cc_cuentas.get(codigo_cc, [])
        if codigos_usuario:
            df = df[df['codigo_cuenta'].isin(codigos_usuario)]
            codigos = codigos_usuario
        else:
            df = df.iloc[0:0]
    else:
        df = df.iloc[0:0]
    return df, bool(codigos)

def show():
    user = st.session_state.user
    
    # ── Session state local a la página ──────────────────────────────────────
    defaults = {
        'receipt_photos': [], 'editing_rid': None, 'submitted_rid': None,
        'alim_max_desayuno': 0, 'alim_max_almuerzo': 0, 'alim_max_cena': 0,
        'total_personas': 1, 'comision_counter': 0
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    for df_key in ['df_comision', 'df_aloj', 'df_alim', 'df_otros']:
        if df_key not in st.session_state or not isinstance(st.session_state[df_key], pd.DataFrame):
            if df_key == 'df_comision':
                st.session_state[df_key] = pd.DataFrame(
                    columns=["Traslado", "Desde oficina", "A localidad", "Fecha Inicio", "Fecha Término"]
                ).astype({"Fecha Inicio": "datetime64[ns]", "Fecha Término": "datetime64[ns]"})
            elif df_key == 'df_alim':
                st.session_state[df_key] = pd.DataFrame(
                    columns=["Detalle", "Tipo", "Fecha", "Doc", "Monto"]
                ).astype({"Fecha": "datetime64[ns]", "Monto": "float", "Tipo": "string"})
            else:
                st.session_state[df_key] = pd.DataFrame(
                    columns=["Detalle", "Fecha", "Doc", "Monto"]
                ).astype({"Fecha": "datetime64[ns]", "Monto": "float"})

    st.title("📝 Gestión de Rendiciones")
    
    tab_new, tab_mine = st.tabs(["🆕 Nueva / Editar Rendición", "🕒 Mis Rendiciones"])
    
    with tab_mine:
        st.subheader("Historial de mis solicitudes")
        df_mine = db_get_user_rendiciones(user['email'])
        
        if df_mine.empty:
            st.info("Aún no has enviado ninguna rendición.")
        else:
            st.dataframe(
                df_mine,
                column_config={
                    "id": "ID",
                    "total": st.column_config.NumberColumn("Monto", format="$ %.0f"),
                    "moneda": "Moneda",
                    "status": "Estado",
                    "fecha_registro": "Fecha",
                    "comentario_encargado": "Observaciones"
                },
                width='stretch',
                hide_index=True
            )
            
            # Acción para descargar o corregir
            st.markdown("---")
            c_hist1, c_hist2 = st.columns(2)
            
            rid_sel = c_hist1.selectbox("Seleccione una rendición", options=df_mine['id'].tolist(), key="sel_hist_rid")
            
            if c_hist2.button("📂 Cargar Datos", key="btn_load_hist"):
                data, pdf_fname, email_func, nombre_func, _ = db_get_rendicion(rid_sel)
                st.session_state.editing_rid = rid_sel
                st.session_state.df_comision = data['df_comision']
                st.session_state.df_aloj = data['df_alojamiento']
                st.session_state.df_alim = data['df_alimentacion']
                st.session_state.df_otros = data['df_otros']
                st.session_state.receipt_photos = data.get('receipt_photos', [])
                st.success(f"Rendición #{rid_sel} cargada.")
                st.rerun()

            # Botón de descarga para rendiciones aprobadas o enviadas
            data_dl, _, _, _, pdf_aprobado_dl = db_get_rendicion(rid_sel)
            if data_dl:
                if pdf_aprobado_dl:
                    pdf_bytes_dl = pdf_aprobado_dl
                else:
                    pdf_bytes_dl = generate_hgt_pdf(data_dl)
                    
                st.download_button(
                    label=f"⬇️ Descargar Rendición #{rid_sel} (PDF)",
                    data=pdf_bytes_dl,
                    file_name=f"Rendicion_{rid_sel}_{user['nombre'].replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    key=f"dl_hist_{rid_sel}"
                )

    with tab_new:
        if st.session_state.submitted_rid:
            st.toast(f"✅ ¡Rendición #{st.session_state.submitted_rid} enviada con éxito!")
            st.balloons()
            st.success(f"🎉 ¡Rendición #{st.session_state.submitted_rid} enviada con éxito a Jefatura!")
            if st.button("🆕 Crear Otra Rendición", key="btn_new_after"):
                st.session_state.submitted_rid = None
                st.rerun()
            st.divider()

        if st.session_state.editing_rid:
            st.warning(f"🛠️ Editando Rendición #{st.session_state.editing_rid}")
            if st.button("❌ Cancelar Edición", key="btn_cancel_edit"):
                st.session_state.editing_rid = None
                for k in ['df_comision', 'df_aloj', 'df_alim', 'df_otros', 'receipt_photos']:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()
        
        # ── SECCIÓN 1: Funcionario ─────────────────────────────────────────────
        st.markdown("### 1. Funcionario que rinde")
        c1, c2, c3, c4, c5 = st.columns(5)
        nombre = c1.text_input("Nombre", value=user.get('nombre', ''), disabled=True, key="f_nom")
        rut = c2.text_input("RUT", value=user.get('rut', ''), disabled=True, key="f_rut")
        moneda = c3.selectbox("Moneda", options=["CLP", "USD"], key="f_moneda")
        # Mostrar centros de costo asociados al usuario
        user_ccs = db_get_usuario_centros_costos(user['id'])
        df_ccs = db_get_centros_costos()
        df_all_cc_cuentas = db_get_all_centro_costo_cuentas()
        has_any_mappings = not df_all_cc_cuentas.empty
        if not has_any_mappings:
            st.warning("⚠️ No hay cuentas contables asociadas a centros de costo. Configure las relaciones en Mantención → Centros de Costos.")
        if user_ccs:
            df_ccs = df_ccs[df_ccs['codigo_cc'].isin(user_ccs)]
            cc_opts = {f"{r['codigo_cc']} - {r['detalle_cc']}": r['codigo_cc'] for _, r in df_ccs.iterrows()}
            cc_sel = c4.selectbox("Centro de costo", options=list(cc_opts.keys()), key="f_cc")
            codigo_cc = cc_opts[cc_sel]
            cc = codigo_cc
        else:
            codigo_cc = user.get('cc', '')
            cc = c4.text_input("Centro de costo", value=codigo_cc, disabled=True, key="f_cc")
        email_func = c5.text_input("Email funcionario", value=user.get('email', ''), disabled=True, key="f_mail")

        # ── SECCIÓN 2: Comisión ───────────────────────────────────────────────
        st.markdown("### 2. Detalle de Comisión de Servicios")
        trayectos_db = db_get_trayectos_dict()
        
        with st.expander("➕ Añadir Nueva Comisión", expanded=True):
            fc = st.session_state.comision_counter
            col_c1, col_c2, col_c3 = st.columns(3)
            c_traslado = col_c1.selectbox("Traslado", ["Uber", "Vehículo propio"], key=f"c_tras_{fc}")
            oficinas = ["Placilla", "Renca", "San Antonio", "Santiago"]
            c_desde = col_c2.selectbox("Desde oficina", oficinas, key=f"c_des_{fc}")
            c_hacia = col_c3.selectbox("A localidad", oficinas, key=f"c_hac_{fc}")
            
            col_c4, col_c5 = st.columns(2)
            c_f_inicio = col_c4.date_input("Fecha Inicio", value=datetime.today(), key=f"c_f_ini_{fc}")
            c_f_termino = col_c5.date_input("Fecha Término", value=datetime.today(), key=f"c_f_ter_{fc}")

            v_fac = 1.0; v_peaje_total = 0; v_multi_peaje = 1; con_acomp = False; n_acomp = 0; con_equipos = False; nombres_acomp = ""
            v_ali_des = 0; v_ali_alm = 0; v_ali_cen = 0
            
            if c_traslado == "Vehículo propio":
                st.markdown("##### 🚗 Cálculo Automático")
                _tsel = f"{c_desde} a {c_hacia}"
                if _tsel in trayectos_db:
                    _kb, _mps, _mpb, _vfac_db, _alimentacion_db, _ali_des, _ali_alm, _ali_cen = trayectos_db[_tsel]
                    v_fac = _vfac_db
                    v_peaje_total = _mpb * _mps
                    st.info(f"Ruta: **{_tsel}** | KM Base: **{_kb}** | Factor: **{v_fac}** | Peajes: **{format_curr(v_peaje_total)}** | Topes - Desayuno: **{format_curr(_ali_des)}**, Almuerzo: **{format_curr(_ali_alm)}**, Cena: **{format_curr(_ali_cen)}**")
                    ca1, ca2 = st.columns([2, 1])
                    con_acomp   = ca1.checkbox("¿Incluye Acompañante(s)?", key=f"chk_acomp_{fc}")
                    if con_acomp:
                        n_acomp = ca2.number_input("Cantidad", min_value=1, value=1, key=f"num_acomp_{fc}")
                        nombres_acomp = st.text_input("Nombres de acompañantes", key=f"txt_acomp_{fc}")
                    con_equipos = st.checkbox("¿Incluye Traslado de equipos?", key=f"chk_equipos_{fc}")
                else:
                    st.warning("⚠️ Ruta no configurada.")
                    v_fac = 0

            if st.button("Añadir Comisión", type="primary", key="btn_add_com"):
                df_ctas_all, _ = _cuentas_para_cc(codigo_cc)
                id_traslado_uber = df_ctas_all.loc[df_ctas_all['concepto_amigable'].str.contains("UBER", na=False, case=False), 'id']
                id_traslado_uber = str(id_traslado_uber.iloc[0]) if not id_traslado_uber.empty else ""
                id_movilizacion = df_ctas_all.loc[df_ctas_all['concepto_amigable'].str.contains("Movilización particular", na=False, case=False), 'id']
                id_movilizacion = str(id_movilizacion.iloc[0]) if not id_movilizacion.empty else ""

                nuevo = {"Traslado": c_traslado, "Desde oficina": c_desde, "A localidad": c_hacia,
                         "Fecha Inicio": pd.to_datetime(c_f_inicio), "Fecha Término": pd.to_datetime(c_f_termino)}
                st.session_state.df_comision = pd.concat([st.session_state.df_comision, pd.DataFrame([nuevo])], ignore_index=True)
                if c_traslado == "Vehículo propio":
                    _tsi = f"{c_desde} a {c_hacia}"
                    if _tsi in trayectos_db:
                        _kb, _mps, _mpb, _vfac_db, _alimentacion_db, _ali_des, _ali_alm, _ali_cen = trayectos_db[_tsi]
                        base_monto = float(_kb * 2 * v_fac)
                        gastos_auto = [{"Detalle": f"Traslado {_tsi}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": id_movilizacion, "Monto": base_monto}]
                        if v_peaje_total > 0: gastos_auto.append({"Detalle": f"Peajes {_tsi}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": id_movilizacion, "Monto": float(v_peaje_total)})
                        if con_equipos: gastos_auto.append({"Detalle": f"Equipos (20%) - {_tsi}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": id_movilizacion, "Monto": float(base_monto * 0.2)})
                        if con_acomp:
                            desc_acomp = f"Acompañantes x{n_acomp}"; 
                            if nombres_acomp: desc_acomp += f" ({nombres_acomp})"
                            monto_acomp = float(base_monto * 0.2 * n_acomp)
                            gastos_auto.append({"Detalle": f"Acompañantes {desc_acomp} (20% x{n_acomp})", "Fecha": pd.to_datetime(c_f_inicio), "Doc": id_movilizacion, "Monto": monto_acomp})
                        st.session_state.df_otros = pd.concat([st.session_state.df_otros, pd.DataFrame(gastos_auto)], ignore_index=True)
                else:
                    gasto_uber = {"Detalle": f"Uber {c_desde} a {c_hacia}", "Fecha": pd.to_datetime(c_f_inicio), "Doc": id_traslado_uber, "Monto": 0}
                    st.session_state.df_otros = pd.concat([st.session_state.df_otros, pd.DataFrame([gasto_uber])], ignore_index=True)
                total_personas = 1 + (n_acomp if con_acomp else 0)
                st.session_state.alim_max_desayuno = float(v_ali_des) * total_personas
                st.session_state.alim_max_almuerzo = float(v_ali_alm) * total_personas
                st.session_state.alim_max_cena = float(v_ali_cen) * total_personas
                st.session_state.total_personas = total_personas
                st.session_state.comision_counter += 1
                st.rerun()

        st.data_editor(st.session_state.df_comision, num_rows="dynamic", width='stretch', key="ed_comision")

        # ── SECCIÓN 3: Anticipo ───────────────────────────────────────────────
        st.markdown("### 3. Anticipo (A)")
        c1, c2 = st.columns(2)
        f_ant = c1.date_input("Fecha Egreso", value=datetime.today(), key="f_egreso")
        anticipo = c2.number_input("Monto Anticipo", min_value=0, value=0, key="v_anticipo")

        # ── SECCIÓN 4: Gastos ─────────────────────────────────────────────────
        st.markdown("### 4. Detalle de Gastos")
        tipo_gasto = st.selectbox("Tipo de gasto", ["Alimentación", "Alojamiento", "Otros"], key="tipo_gasto_upload")

        # ── Selector de cuenta contable (según tipo de gasto) ────────────────
        cta_id = None
        if tipo_gasto == "Alimentación":
            df_ctas, _ = _cuentas_para_cc(codigo_cc, usuario_id=user.get('id'))
            mask = (df_ctas['concepto_amigable'].str.lower().str.contains("alimentación|almuerzo", na=False)
                    | df_ctas['detalle_1'].str.lower().str.contains("alimentación|almuerzo", na=False))
            df_ctas_fil = df_ctas[mask]
            if df_ctas_fil.empty:
                df_ctas_fil = df_ctas  # fallback: mostrar todas las cuentas del CC
            if not df_ctas_fil.empty:
                opts = {f"{r['codigo_cuenta']} - {r['concepto_amigable']}": r['id'] for _, r in df_ctas_fil.iterrows()}
                sel = st.selectbox("Cuenta contable", options=list(opts.keys()), key="cta_sel_alim")
                cta_id = opts[sel]

        elif tipo_gasto == "Alojamiento":
            df_ctas, _ = _cuentas_para_cc(codigo_cc, usuario_id=user.get('id'))
            mask = (df_ctas['concepto_amigable'].str.lower().str.contains("alojamiento", na=False)
                    | df_ctas['detalle_1'].str.lower().str.contains("alojamiento", na=False))
            df_ctas_fil = df_ctas[mask]
            if df_ctas_fil.empty:
                df_ctas_fil = df_ctas  # fallback: mostrar todas las cuentas del CC
            if not df_ctas_fil.empty:
                opts = {f"{r['codigo_cuenta']} - {r['concepto_amigable']}": r['id'] for _, r in df_ctas_fil.iterrows()}
                sel = st.selectbox("Cuenta contable", options=list(opts.keys()), key="cta_sel_aloj")
                cta_id = opts[sel]

        elif tipo_gasto == "Otros":
            df_ctas, _ = _cuentas_para_cc(codigo_cc, usuario_id=user.get('id'))
            exclude_keywords = ["alimentación", "almuerzo", "traslado", "movilización", "vehiculo", "uber", "alojamiento"]
            pattern = '|'.join(exclude_keywords)
            mask = (df_ctas['concepto_amigable'].str.lower().str.contains(pattern, na=False)
                    | df_ctas['detalle_1'].str.lower().str.contains(pattern, na=False))
            df_ctas_fil = df_ctas[~mask]
            if df_ctas_fil.empty:
                df_ctas_fil = df_ctas  # fallback: mostrar todas las cuentas del CC
            if not df_ctas_fil.empty:
                opts = {f"{r['codigo_cuenta']} - {r['concepto_amigable']} ({r['detalle_1']})": r['id']
                        for _, r in df_ctas_fil.iterrows()}
                sel = st.selectbox("Cuenta contable", options=list(opts.keys()), key="cta_sel_otros")
                cta_id = opts[sel]

        # ── Subir Comprobantes y Escáner AI ──────────────────────────────────
        with st.expander("➕ Subir Comprobantes y Escáner AI", expanded=True):
            up_file = st.file_uploader("Seleccione comprobante", type=["jpg", "jpeg", "png"], key="up_file_receipt")
            if up_file:
                st.image(up_file, width=150)
                c_ai1, c_ai2 = st.columns(2)
                m_map = {"Alimentación": "df_alim", "Alojamiento": "df_aloj", "Otros": "df_otros"}
                if c_ai1.button("🔍 Escanear con IA", width='stretch', type="primary", key="btn_ai_scan"):
                    if cta_id is None:
                        st.error("Seleccione una cuenta contable primero.")
                    else:
                        with st.spinner("Analizando..."):
                            res = process_receipt_with_ai(up_file)
                            if res.get("success"):
                                data_ai = res["data"]
                                st.session_state.receipt_photos.append(up_file.getvalue())
                                monto = float(data_ai.get("Monto", 0))
                                if tipo_gasto == "Alimentación":
                                    limite_alim = st.session_state.alim_max_almuerzo
                                    if limite_alim > 0 and monto > limite_alim:
                                        monto = limite_alim
                                new_r = {"Detalle": data_ai.get("Detalle", ""), "Fecha": pd.to_datetime(data_ai.get("Fecha", datetime.today())), "Doc": str(cta_id), "Monto": monto}
                                if tipo_gasto == "Alimentación":
                                    new_r["Tipo"] = "Almuerzo"
                                st.session_state[m_map[tipo_gasto]] = pd.concat([st.session_state[m_map[tipo_gasto]], pd.DataFrame([new_r])], ignore_index=True)
                                st.rerun()
                            elif res.get("error") == "quota_exhausted":
                                st.warning(res.get("user_message", "Cuota de IA agotada."))
                            else:
                                st.error(f"Error al escanear: {res.get('error', 'desconocido')}")
                if c_ai2.button("📥 Solo Adjuntar Foto", width='stretch', key="btn_attach_only"):
                    st.session_state.receipt_photos.append(up_file.getvalue()); st.rerun()

        if st.session_state.receipt_photos:
            st.markdown("##### 📁 Documentos Cargados")
            cols_img = st.columns(4)
            for idx, img_b in enumerate(st.session_state.receipt_photos):
                with cols_img[idx % 4]:
                    st.image(img_b, width=100)
                    if st.button("🗑️", key=f"del_img_{idx}"):
                        st.session_state.receipt_photos.pop(idx); st.rerun()

        # ── Tablas de gastos acumulados ──────────────────────────────────────
        st.markdown("#### Alojamiento")
        st.session_state.df_aloj = st.data_editor(st.session_state.df_aloj, num_rows="dynamic", width='stretch', key="ed_aloj")
        st.markdown("#### Alimentación")
        st.session_state.df_alim = st.data_editor(
            st.session_state.df_alim, 
            num_rows="dynamic", 
            width='stretch', 
            key="ed_alim",
            column_config={
                "Tipo": st.column_config.SelectboxColumn(
                    "Tipo",
                    help="Desayuno, Almuerzo o Cena",
                    options=["Desayuno", "Almuerzo", "Cena", "Otros"],
                    required=True
                )
            }
        )
        st.markdown("#### Otros Gastos")
        st.session_state.df_otros = st.data_editor(st.session_state.df_otros, num_rows="dynamic", width='stretch', key="ed_otros")

        # ── ENVÍO ────────────────────────────────────────────────────────────
        st.divider()
        df_jefes = db_get_jefaturas()
        if df_jefes.empty:
            st.warning("No hay jefaturas."); email_jefe = None
        else:
            j_opts = {f"{r['nombre']} ({r['email']})": r['email'] for _, r in df_jefes.iterrows()}
            j_sel = st.selectbox("Seleccione jefatura", options=list(j_opts.keys()), key="sel_jefe")
            email_jefe = j_opts[j_sel]

        c_sub1, c_sub2 = st.columns(2)
        
        # Botón de Vista Previa
        if c_sub1.button("👁️ Vista Previa PDF", width='stretch'):
            if st.session_state.df_comision.empty and st.session_state.df_aloj.empty and st.session_state.df_alim.empty and st.session_state.df_otros.empty:
                st.error("⚠️ No puedes previsualizar una rendición vacía. Agrega al menos un gasto o comisión.")
            else:
                data_pv = _build_rendicion_data(
                    nombre, rut, cc, email_func, email_jefe or "", anticipo, f_ant, user,
                    st.session_state.df_comision, st.session_state.df_aloj, 
                    st.session_state.df_alim, st.session_state.df_otros,
                    st.session_state.receipt_photos, moneda=moneda
                )
                pdf_pv = generate_hgt_pdf(data_pv)
                b64_pdf = base64.b64encode(pdf_pv).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)

        if c_sub2.button("🚀 Enviar para Aprobación", type="primary", width='stretch', key="btn_submit_rend"):
            if not email_jefe: 
                st.error("Seleccione jefatura.")
            elif email_jefe == user.get('email'):
                st.error("⚠️ El funcionario no puede ser su propio jefe. Seleccione otra jefatura.")
            elif st.session_state.df_comision.empty and st.session_state.df_aloj.empty and st.session_state.df_alim.empty and st.session_state.df_otros.empty:
                st.error("⚠️ No puedes enviar una rendición vacía. Agrega al menos un gasto o comisión.")
            else:
                # Aplicar topes según moneda
                if moneda == 'USD':
                    topes_usd = db_get_topes_usd_dict()
                    for tipo in ["Desayuno", "Almuerzo", "Cena"]:
                        tope = topes_usd.get(tipo, 0)
                        if tope > 0:
                            mask = st.session_state.df_alim['Tipo'] == tipo
                            if mask.any():
                                st_alim_tipo = pd.to_numeric(st.session_state.df_alim.loc[mask, 'Monto'], errors='coerce').fillna(0).sum()
                                if st_alim_tipo > tope:
                                    st.session_state.df_alim.loc[mask, 'Monto'] = st.session_state.df_alim.loc[mask, 'Monto'].apply(lambda x: x * (tope / st_alim_tipo))
                                    st.warning(f"⚠️ Monto de {tipo} ajustado al tope USD: {format_curr(tope, 'USD')}")
                else:
                    for tipo, max_limite in [("Desayuno", st.session_state.alim_max_desayuno), 
                                             ("Almuerzo", st.session_state.alim_max_almuerzo), 
                                             ("Cena", st.session_state.alim_max_cena)]:
                        mask = st.session_state.df_alim['Tipo'] == tipo
                        if mask.any() and max_limite > 0:
                            st_alim_tipo = pd.to_numeric(st.session_state.df_alim.loc[mask, 'Monto'], errors='coerce').fillna(0).sum()
                            if st_alim_tipo > max_limite:
                                st.session_state.df_alim.loc[mask, 'Monto'] = st.session_state.df_alim.loc[mask, 'Monto'].apply(lambda x: x * (max_limite / st_alim_tipo))
                                st.warning(f"⚠️ Monto de {tipo} ajustado al límite permitido: {format_curr(max_limite)}")
                
                data = _build_rendicion_data(
                    nombre, rut, cc, email_func, email_jefe, anticipo, f_ant, user,
                    st.session_state.df_comision, st.session_state.df_aloj, 
                    st.session_state.df_alim, st.session_state.df_otros,
                    st.session_state.receipt_photos, moneda=moneda
                )
                if st.session_state.editing_rid:
                    db_update_rendicion(st.session_state.editing_rid, data); rid = st.session_state.editing_rid
                else:
                    rid = db_submit_rendicion(data)
                
                smtp_conf = st.secrets["smtp"]
                total = data.get('st_alojamiento', 0) + data.get('st_alimentacion', 0) + data.get('st_otros', 0)
                email_subject = f"Nueva Rendición de Gastos Pendiente - {nombre}"
                email_body = (
                    f"Estimado/a Jefe/a,\n\n"
                    f"Se ha ingresado una nueva rendición de gastos pendiente de su aprobación.\n\n"
                    f"Funcionario: {nombre}\n"
                    f"RUT: {rut}\n"
                    f"Centro de Costo: {cc}\n"
                    f"Moneda: {moneda}\n"
                    f"Monto Total: {format_curr(total, moneda)}\n\n"
                    f"Por favor, ingrese al sistema para revisar y aprobar o rechazar la rendición.\n\n"
                    f"Saludos cordiales,\n"
                    f"Sistema de Rendiciones HGT"
                )
                send_hgt_email(smtp_conf, email_jefe, email_subject, email_body)
                
                st.session_state.submitted_rid = rid
                st.session_state.editing_rid = None
                for k in ['df_comision', 'df_aloj', 'df_alim', 'df_otros', 'receipt_photos']:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()

if __name__ == "__main__":
    show()
