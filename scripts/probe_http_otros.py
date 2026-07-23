import os, sys, re
BASE = r'C:\Users\aadamc\OneDrive - SAAM Ports\Documentos\Antigravity\Rendiciones_20260605'
sys.path.insert(0, BASE)
os.chdir(BASE)
import requests

BASE_URL = 'http://localhost:5000'
s = requests.Session()

# 1) Load login page to init session and CSRF
r = s.get(BASE_URL + '/login')
print('login status', r.status_code)

# 2) Login as admin to get authenticated session
payload = {'username':'admin','password':'123','csrf_token':''}
# we need csrf from form
m = re.search(r'name="csrf_token".*?value="([^"]+)"', r.text)
if m:
    payload['csrf_token'] = m.group(1)
r = s.post(BASE_URL + '/login', data=payload, allow_redirects=False)
print('login post', r.status_code, 'location', r.headers.get('Location'))

# 3) Open rendiciones form
r = s.get(BASE_URL + '/rendiciones')
print('rendiciones get', r.status_code, 'len', len(r.text))
m = re.search(r'name="csrf_token".*?value="([^"]+)"', r.text)
csrf = m.group(1) if m else ''
print('csrf found', bool(csrf))

# 4) Submit preview request with ONLY Otros Gastos filled
form = {
    'csrf_token': csrf,
    'nombre': 'Alejandro Adam',
    'rut': '11438753-1',
    'moneda': 'CLP',
    'centro_costo': 'SMLG00210',
    'email_funcionario': 'a@hgt.com',
    'email_jefe': 'j@hgt.com',
    'fecha_anticipo': '2026-07-06',
    'anticipo': '0',
    # Otros rows
    'otros_0_Detalle': 'Costanera Peaje 1',
    'otros_0_Fecha': '2026-06-30',
    'otros_0_Doc': '227053169',
    'otros_0_Monto': '17949',
    'otros_1_Detalle': 'Peaje Ruta 5',
    'otros_1_Fecha': '2026-06-30',
    'otros_1_Doc': '453221',
    'otros_1_Monto': '3200',
}

r = s.post(BASE_URL + '/rendiciones/preview', data=form, allow_redirects=False)
print('preview status', r.status_code)
ct = r.headers.get('Content-Type','')
print('preview ct', ct)
body = r.content[:200]
print('preview body head', body)

out = os.path.join(r'C:\Users\aadamc\AppData\Roaming\Hermes\composer-images', 'prueba_http_otros.pdf')
if 'pdf' in ct.lower():
    with open(out, 'wb') as f:
        f.write(r.content)
    print('saved pdf len', len(r.content), out)
else:
    print('no pdf, first 500 chars:', r.text[:500])
