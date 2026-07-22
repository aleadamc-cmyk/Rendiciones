import os
from io import BytesIO
import pandas as pd
from fpdf import FPDF
from app.database import LOGO_PATH, format_curr, BASE_DIR


class HGTPDF(FPDF):
    def __init__(self, *args, moneda='CLP', **kwargs):
        super().__init__(*args, **kwargs)
        self._moneda = moneda

    def header(self):
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, 13, 8, 30)
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'RENDICIÓN DE GASTOS', 0, 0, 'C')
        self.set_font('Helvetica', 'B', 7)
        moneda_label = 'DÓLARES AMERICANOS' if self._moneda == 'USD' else 'PESOS CHILENOS'
        self.cell(0, 10, moneda_label, 0, 1, 'R')
        self.ln(2)
        self.set_xy(13, 33)
        self.set_font('Helvetica', 'B', 8)
        self.cell(0, 5, 'HGT Chile Logistics', 0, 1, 'L')
        self.ln(2)

    def draw_section_header(self, title):
        self.set_fill_color(240, 240, 240)
        self.set_font('Helvetica', 'B', 9)
        self.cell(0, 6, title, 1, 1, 'L', fill=True)


def clean(t):
    return str(t).replace('\u2192', ' a ').encode('latin-1', 'replace').decode('latin-1')


def fmt_date(val):
    if hasattr(val, 'strftime'):
        try:
            if pd.isnull(val):
                return ''
        except Exception:
            pass
        return val.strftime('%d/%m/%Y')
    return str(val)


def generate_hgt_pdf(data):
    tr = (len(data['df_comision']) + len(data['df_alojamiento'])
          + len(data['df_alimentacion']) + len(data['df_otros']))
    p_format = 'letter' if tr <= 25 else (216, 330)
    moneda = data.get('moneda', 'CLP')
    pdf = HGTPDF(orientation='P', unit='mm', format=p_format, moneda=moneda)
    pdf.set_left_margin(13)
    pdf.set_right_margin(13)
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()

    pdf.draw_section_header('Funcionario que rinde')
    pdf.set_font('Helvetica', '', 8)
    pdf.cell(20, 6, 'Nombre:', 'LTB')
    pdf.cell(75, 6, clean(data['nombre']), 'RTB')
    pdf.cell(20, 6, 'Rut:', 'LTB')
    pdf.cell(75, 6, clean(data['rut']), 'RTB', 1)
    pdf.cell(20, 6, 'C. Costo:', 'LTB')
    pdf.cell(75, 6, clean(data.get('centro_costo', '')), 'RTB')
    pdf.cell(20, 6, 'Email:', 'LTB')
    pdf.cell(75, 6, clean(data.get('email_funcionario', '')), 'RTB', 1)
    pdf.cell(20, 6, 'Jefatura:', 'LTB')
    pdf.cell(0, 6, clean(data.get('email_jefatura', '')), 'RTB', 1)
    pdf.ln(4)

    pdf.draw_section_header('Detalle de Comisión de Servicios')
    pdf.set_font('Helvetica', 'B', 7)
    for label, w in [('traslado / cuenta contable', 40),
                     ('desde oficina', 28), ('a localidad', 28),
                     ('Fecha Inicio', 18), ('Fecha Término', 18),
                     ('Acompañados', 30), ('Cta. Contable', 30)]:
        pdf.cell(w, 5, label, 1, 0, 'C', fill=True)
    pdf.ln()
    pdf.set_font('Helvetica', '', 7)
    for _, row in data['df_comision'].iterrows():
        num_acomp = row.get('Num_acompanantes', '')
        nombres_acomp = row.get('Nombres_acompanantes', '')
        if pd.notna(num_acomp) and str(num_acomp).strip() and str(num_acomp) != '0':
            acomp_text = f"{int(float(num_acomp))} pers."
            if pd.notna(nombres_acomp) and str(nombres_acomp).strip():
                nombres = str(nombres_acomp).strip()
                if len(nombres) > 25:
                    nombres = nombres[:22] + '...'
                acomp_text += f" ({nombres})"
        else:
            acomp_text = ''
        pdf.cell(40, 5, clean(row.get('Traslado', '')), 1)
        pdf.cell(28, 5, clean(row.get('Desde oficina', '')), 1)
        pdf.cell(28, 5, clean(row.get('A localidad', '')), 1)
        pdf.cell(18, 5, fmt_date(row.get('Fecha Inicio', '')), 1, 0, 'C')
        pdf.cell(18, 5, fmt_date(row.get('Fecha Término', '')), 1, 0, 'C')
        pdf.cell(30, 5, clean(acomp_text), 1, 0, 'C')
        pdf.cell(30, 5, clean(row.get('Cuenta Contable', '')), 1, 1, 'C')
    pdf.ln(4)

    pdf.set_font('Helvetica', 'B', 9)
    curr_y = pdf.get_y()
    pdf.cell(100, 10, 'Anticipo sujeto a rendición', 1, 0, 'L')
    pdf.cell(40, 5, 'Fecha Egreso', 1, 0, 'C')
    pdf.cell(30, 10, 'Total (A)', 1, 0, 'C', fill=True)
    pdf.cell(20, 10, format_curr(data['anticipo'], moneda), 1, 1, 'R')
    pdf.set_xy(113, curr_y + 5)
    pdf.set_font('Helvetica', '', 7)
    pdf.cell(40, 5, fmt_date(data.get('fecha_anticipo', '')), 1, 1, 'C')
    pdf.ln(4)

    def draw_concept_table(title, items, total_label, total_val, include_doc=True):
        pdf.draw_section_header(title)
        pdf.set_font('Helvetica', 'B', 8)
        monto_label = 'Monto US$' if moneda == 'USD' else 'Monto $'
        if include_doc:
            pdf.cell(70, 5, 'Lugar / Detalle', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, 'Fecha Docto', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, 'N° Documento', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, monto_label, 1, 1, 'C', fill=True)
        else:
            pdf.cell(110, 5, 'Lugar / Detalle', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, 'Fecha Docto', 1, 0, 'C', fill=True)
            pdf.cell(40, 5, monto_label, 1, 1, 'C', fill=True)
        pdf.set_font('Helvetica', '', 8)
        for _, row in items.iterrows():
            detalle = str(row.get('Detalle') or row.get('detalle') or row.get('Lugar') or "").strip()
            tipo = str(row.get('Tipo') or row.get('tipo') or "").strip()
            if tipo and tipo != "nan":
                detalle = f"{detalle} ({tipo})"
            raw_monto = row.get('Monto')
            if raw_monto is None or (hasattr(raw_monto, '__bool__') and pd.isna(raw_monto)):
                monto = 0
            else:
                try:
                    monto = float(raw_monto)
                except (ValueError, TypeError):
                    monto = 0
            fecha = row.get('Fecha') or row.get('fecha') or ""
            doc = str(row.get('Doc') or row.get('doc') or "").strip()
            if not detalle and monto == 0:
                continue
            if include_doc:
                pdf.cell(70, 5, clean(detalle), 1)
                pdf.cell(40, 5, fmt_date(fecha), 1, 0, 'C')
                pdf.cell(40, 5, clean(doc), 1, 0, 'C')
                pdf.cell(40, 5, format_curr(monto, moneda), 1, 1, 'R')
            else:
                pdf.cell(110, 5, clean(detalle), 1)
                pdf.cell(40, 5, fmt_date(fecha), 1, 0, 'C')
                pdf.cell(40, 5, format_curr(monto, moneda), 1, 1, 'R')
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(150, 6, total_label, 1, 0, 'R', fill=True)
        pdf.cell(40, 6, format_curr(total_val, moneda), 1, 1, 'R')
        pdf.ln(3)

    draw_concept_table('ALOJAMIENTO', data['df_alojamiento'], 'SUBTOTAL (B)', data['st_alojamiento'])
    draw_concept_table('ALIMENTACIÓN', data['df_alimentacion'], 'SUBTOTAL (C)', data['st_alimentacion'])
    draw_concept_table('OTROS GASTOS', data['df_otros'], 'SUBTOTAL (D)', data['st_otros'])

    td = float(data.get('st_alojamiento', 0)) + float(data.get('st_alimentacion', 0)) + float(data.get('st_otros', 0))
    delta = data['anticipo'] - td
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(150, 6, 'Total Desembolsos (B+C+D)', 1, 0, 'R')
    pdf.cell(40, 6, format_curr(td, moneda), 1, 1, 'R', fill=True)
    pdf.ln(1)
    pdf.cell(120, 6, 'Diferencia a favor de HGT CHILE LOGISTICS', 'LT', 0, 'L')
    pdf.cell(30, 6, '[ A - (B+C+D) ]', 'TR', 0, 'C')
    pdf.cell(40, 6, format_curr(max(0, delta), moneda) if delta >= 0 else "-", 1, 1, 'R')
    pdf.cell(150, 6, 'Diferencia a favor de Funcionario ( - )', 1, 0, 'L')
    pdf.cell(40, 6, format_curr(abs(delta), moneda) if delta < 0 else "-", 1, 1, 'R')
    pdf.ln(5)

    pdf.set_auto_page_break(False)
    firma_y = pdf.h - 28
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', 'I', 7)
    pdf.set_xy(88, firma_y - 4)
    pdf.cell(65, 4, clean(data['rut']), 0, 0, 'C')
    pdf.set_xy(88, firma_y - 8)
    pdf.cell(65, 4, clean(data['nombre']), 0, 0, 'C')
    is_approved = data.get('status') in ['APROBADO_POR_JEFATURA', 'PROCESADO_FINAL', 'PROCESADO_ENCARGADO'] or data.get('fecha_aprobacion')
    if is_approved:
        j_nom = data.get('jefe_nombre', 'Jefatura')
        j_rut = data.get('jefe_rut', '')
        pdf.set_xy(163, firma_y - 4)
        pdf.cell(40, 4, clean(j_rut), 0, 0, 'C')
        pdf.set_xy(163, firma_y - 8)
        pdf.cell(40, 4, clean(j_nom), 0, 0, 'C')
    pdf.set_xy(13, firma_y)
    pdf.set_font('Helvetica', '', 8)
    pdf.cell(65, 5, data.get('fecha_rendicion', ''), 'T', 0, 'C')
    pdf.cell(10, 5, '', 0, 0)
    pdf.cell(65, 5, 'Firma Funcionario', 'T', 0, 'C')
    pdf.cell(10, 5, '', 0, 0)
    pdf.cell(40, 5, 'Firma Jefe Directo', 'T', 1, 'C')
    if data.get('fecha_aprobacion') and data.get('jefe_rut'):
        texto_validacion = f"El documento fue aprobado mediante firma digital vinculada a la Cédula {data['jefe_rut']} en fecha {data['fecha_aprobacion']}"
        pdf.set_xy(13, pdf.h - 12)
        pdf.set_font('Helvetica', 'I', 7)
        pdf.cell(0, 4, texto_validacion, 0, 0, 'C')
    try:
        import qrcode
        user_sid = data.get('user_sid', '')
        qr = qrcode.QRCode(version=1, box_size=2, border=1)
        qr_data = f"Firma Digital Segura HGT\nFuncionario: {data.get('nombre')}\nID Funcionario: {user_sid[:8] if user_sid else 'N/A'}"
        if is_approved:
            qr_data += f"\nAprobado por Jefatura\nFecha: {data.get('fecha_aprobacion', 'OK')}"
        qr.add_data(qr_data)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        qr_bytes = BytesIO()
        img_qr.save(qr_bytes, format='PNG')
        qr_bytes.seek(0)
        pdf.image(qr_bytes, x=112.5, y=firma_y - 26, w=16)
        if is_approved:
            pdf.image(qr_bytes, x=175, y=firma_y - 26, w=16)
    except ImportError:
        pass

    receipt_images = data.get('receipt_photos', [])
    if receipt_images:
        from PIL import Image
        positions = [(18, 60), (113, 60), (18, 168), (113, 168)]
        max_w, max_h = 85, 95
        for i in range(0, len(receipt_images), 4):
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Documentos de Respaldo / Comprobantes de Gasto', 0, 1, 'C')
            for idx, img_b in enumerate(receipt_images[i:i + 4]):
                try:
                    s = BytesIO(img_b)
                    with Image.open(s) as img:
                        iw, ih = img.size
                    sc = min(max_w / iw, max_h / ih)
                    fw3, fh3 = iw * sc, ih * sc
                    x, y = positions[idx]
                    s.seek(0)
                    pdf.image(s, x=x + (max_w - fw3) / 2, y=y, w=fw3, h=fh3)
                except Exception:
                    x, y = positions[idx]
                    pdf.set_xy(x, y)
                    pdf.set_font('Helvetica', 'I', 8)
                    pdf.cell(max_w, 10, f"Error imagen", 0, 0)
    return bytes(pdf.output())
