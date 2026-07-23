import os, sys, json, pandas as pd
from datetime import datetime
from io import BytesIO

BASE = r'C:\Users\aadamc\OneDrive - SAAM Ports\Documentos\Antigravity\Rendiciones_20260605'
sys.path.insert(0, BASE)

from app.utils.pdf_generator import generate_hgt_pdf

sample = {
    'nombre': 'Alejandro Adam',
    'rut': '11438753-1',
    'centro_costo': 'SMLG00210',
    'email_funcionario': 'a@hgt.com',
    'email_jefatura': 'j@hgt.com',
    'anticipo': 0,
    'fecha_anticipo': datetime.today().date(),
    'user_id': 1,
    'user_sid': 'sid_test',
    'moneda': 'CLP',
    'df_comision': pd.DataFrame(columns=['Traslado','Desde oficina','A localidad','Fecha Inicio','Fecha Término','Num_acompanantes','Nombres_acompanantes']),
    'df_alojamiento': pd.DataFrame(columns=['Detalle','Fecha','Doc','Monto']),
    'df_alimentacion': pd.DataFrame(columns=['Detalle','Tipo','Fecha','Doc','Monto']),
    'df_otros': pd.DataFrame([{'Detalle':'Costanera','Fecha':'2026-06-30','Doc':'227053169','Monto':17949}]),
    'st_alojamiento': 0.0,
    'st_alimentacion': 0.0,
    'st_otros': 17949.0,
    'fecha_rendicion': datetime.now().strftime('%d/%m/%Y'),
    'receipt_photos': [],
    'fecha_aprobacion': '',
    'jefe_nombre': '',
    'jefe_rut': '',
    'status': 'pendiente'
}

pdf = generate_hgt_pdf(sample)
out = os.path.join(r'C:\Users\aadamc\AppData\Roaming\Hermes\composer-images', 'prueba_otras_01.pdf')
with open(out, 'wb') as f:
    f.write(pdf)
print('OK', len(pdf), out)
