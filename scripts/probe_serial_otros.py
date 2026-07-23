import os, sys, json, base64, sqlite3, tempfile
from datetime import datetime
from io import BytesIO
import pandas as pd

BASE = r'C:\Users\aadamc\OneDrive - SAAM Ports\Documentos\Antigravity\Rendiciones_20260605'
sys.path.insert(0, BASE)
os.chdir(BASE)

from app.database import serialize_data, deserialize_data, init_db, DB_PATH
from app.utils.pdf_generator import generate_hgt_pdf

init_db()

sample = {
    'nombre': 'Alejandro Adam',
    'rut': '11438753-1',
    'centro_costo': 'SMLG00210',
    'email_funcionario': 'a@hgt.com',
    'email_jefatura': 'j@hgt.com',
    'user_id': 1,
    'user_sid': 'sid_test',
    'moneda': 'CLP',
    'df_comision': pd.DataFrame(columns=['Traslado','Desde oficina','A localidad','Fecha Inicio','Fecha Término','Num_acompanantes','Nombres_acompanantes']),
    'df_alojamiento': pd.DataFrame(columns=['Detalle','Fecha','Doc','Monto']),
    'df_alimentacion': pd.DataFrame(columns=['Detalle','Tipo','Fecha','Doc','Monto']),
    'df_otros': pd.DataFrame([
        {'Detalle':'Costanera Peaje 1','Fecha':'2026-06-30','Doc':'227053169','Monto':17949},
        {'Detalle':'Peaje Ruta 5','Fecha':'2026-06-30','Doc':'453221','Monto':3200},
    ]),
    'anticipo': 0,
    'fecha_anticipo': datetime.today().date(),
    'st_alojamiento': 0.0,
    'st_alimentacion': 0.0,
    'st_otros': 17949+3200,
    'fecha_rendicion': datetime.now().strftime('%d/%m/%Y'),
    'receipt_photos': [],
    'fecha_aprobacion': '',
    'jefe_nombre': '',
    'jefe_rut': '',
    'status': 'pendiente',
}

json_str = serialize_data(sample)
print('serialized len=', len(json_str))

out = os.path.join(r'C:\Users\aadamc\AppData\Roaming\Hermes\composer-images', 'prueba_serial_01.json')
with open(out, 'w', encoding='utf-8') as f:
    f.write(json_str)

back = deserialize_data(json_str)
print('df_otros from serialize/deserialize:')
print(back['df_otros'].to_dict('records'))
print('st_otros=', back['st_otros'])
print('sum df_otros=', back['df_otros']['Monto'].sum() if 'Monto' in back['df_otros'].columns and not back['df_otros'].empty else 0)

# Write to SQLite like real submit
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('INSERT INTO rendiciones_workflow (nombre, email_funcionario, centro_costo, total, status, data_json) VALUES (?,?,?,?,?,?)',
          (sample['nombre'], sample['email_funcionario'], sample['centro_costo'], float(back['st_otros']), 'pendiente', json_str))
conn.commit()
rid = c.lastrowid
row = c.execute('SELECT data_json FROM rendiciones_workflow WHERE id=?', (rid,)).fetchone()
conn.close()
from_db = deserialize_data(row[0])
print('df_otros from DB:')
print(from_db['df_otros'].to_dict('records'))
print('st_otros from DB=', from_db['st_otros'])

pdf = generate_hgt_pdf(from_db)
out_pdf = os.path.join(r'C:\Users\aadamc\AppData\Roaming\Hermes\composer-images', 'prueba_serial_01.pdf')
with open(out_pdf, 'wb') as f:
    f.write(pdf)
print('pdf=', len(pdf), out_pdf)
