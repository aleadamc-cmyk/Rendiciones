import sys, os
BASE = r'C:\Users\aadamc\OneDrive - SAAM Ports\Documentos\Antigravity\Rendiciones_20260605'
sys.path.insert(0, BASE)
os.chdir(BASE)

from app.routes.rendiciones import _parse_df_from_form

class FakeForm(dict):
    def __init__(self, data):
        super().__init__(data)

data = FakeForm({
    'otros_0_Detalle': 'Costanera',
    'otros_0_Fecha': '2026-06-30',
    'otros_0_Doc': '227053169',
    'otros_0_Monto': '17949',
})

df_otros = _parse_df_from_form(data, 'otros', ['Detalle', 'Fecha', 'Doc', 'Monto'])
print('shape=', df_otros.shape)
print(df_otros.to_dict('records'))
print('subtotal=', df_otros['Monto'].sum() if 'Monto' in df_otros.columns and not df_otros.empty else 0)

# Caso 2: varias filas, una vacía parcial
data2 = FakeForm({
    'otros_0_Detalle': 'Costanera',
    'otros_0_Fecha': '2026-06-30',
    'otros_0_Doc': '227053169',
    'otros_0_Monto': '17949',
    'otros_1_Detalle': '',
    'otros_1_Fecha': '',
    'otros_1_Doc': '',
    'otros_1_Monto': '',
})
df_otros2 = _parse_df_from_form(data2, 'otros', ['Detalle', 'Fecha', 'Doc', 'Monto'])
print('case2 shape=', df_otros2.shape)
print(df_otros2.to_dict('records'))
