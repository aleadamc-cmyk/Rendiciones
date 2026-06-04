import sqlite3
import json
import pandas as pd
from datetime import datetime
import io

DB_PATH = "rendiciones_hgt.db"

def sync_all():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, data_json, status FROM rendiciones_workflow")
    rows = c.fetchall()
    
    c.execute("DELETE FROM rendiciones_detalles")
    
    inserted = 0
    for rid, data_json, status in rows:
        if not data_json: continue
        try:
            data = json.loads(data_json)
        except:
            continue
            
        colaborador_id = data.get('user_id')
        cc = data.get('centro_costo')
        
        fallback_cta = 1
        
        items = []
        for df_key in ["df_alojamiento", "df_alimentacion", "df_otros", "df_comision"]:
            df_str = data.get(df_key)
            if not df_str:
                continue
            try:
                df = pd.read_json(io.StringIO(df_str))
            except:
                continue
            if df.empty:
                continue
            for _, row in df.iterrows():
                if df_key == "df_comision":
                    doc = row.get('Traslado')
                    monto = row.get('Monto Viaje', row.get('Monto', 0))
                    fecha = row.get('Fecha Inicio', row.get('Fecha'))
                    detalle = f"Traslado: {row.get('Desde oficina', '')} → {row.get('A localidad', '')}"
                else:
                    doc = row.get('Doc')
                    monto = row.get('Monto', 0)
                    fecha = row.get('Fecha')
                    detalle = row.get('Detalle', '')
                
                if pd.notna(doc) and str(doc).isdigit():
                    cuenta_id = int(doc)
                else:
                    cuenta_id = fallback_cta
                    
                if pd.notna(fecha):
                    if hasattr(fecha, 'strftime'):
                        fecha_str = fecha.strftime('%Y-%m-%d')
                    else:
                        fecha_str = str(fecha)[:10]
                else:
                    fecha_str = datetime.now().strftime('%Y-%m-%d')
                    
                items.append({
                    'rendicion_id': rid,
                    'colaborador_id': colaborador_id,
                    'centro_costo_codigo': cc,
                    'cuenta_id': cuenta_id,
                    'ruta_id': None,
                    'es_ida_vuelta': 0,
                    'lleva_acompanante': 0,
                    'detalle_gasto': detalle,
                    'monto_total': float(monto) if pd.notna(monto) else 0,
                    'fecha_gasto': fecha_str
                })
                    
        for item in items:
            c.execute("""
                INSERT INTO rendiciones_detalles 
                (rendicion_id, colaborador_id, centro_costo_codigo, cuenta_id, ruta_id,
                 es_ida_vuelta, lleva_acompanante, detalle_gasto, monto_total, fecha_gasto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item['rendicion_id'], item['colaborador_id'], item['centro_costo_codigo'], item['cuenta_id'],
                  item['ruta_id'], item['es_ida_vuelta'], item['lleva_acompanante'], 
                  item['detalle_gasto'], item['monto_total'], item['fecha_gasto']))
            inserted += 1
            
    conn.commit()
    conn.close()
    print(f"Sincronizados {inserted} detalles de gastos.")

if __name__ == "__main__":
    sync_all()
