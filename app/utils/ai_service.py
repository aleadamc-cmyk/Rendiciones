import json
import time
from io import BytesIO
from google import genai
from google.genai import types


def _call_gemini_with_fallback(client, prompt, img_part):
    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
    last_error = None
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, img_part]
                )
                text = response.text
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                return json.loads(text.strip())
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error or "404" in last_error or "NOT_FOUND" in last_error:
                    if attempt == 0 and ("429" in last_error or "RESOURCE_EXHAUSTED" in last_error):
                        time.sleep(10)
                        continue
                    else:
                        break
                else:
                    raise e
    raise Exception(f"Cuota agotada o modelos no disponibles. Último error: {last_error}")


def process_receipt_with_ai(api_key, uploaded_bytes, mime_type):
    if not api_key:
        return {"error": "API AI no configurada"}
    if not uploaded_bytes:
        return {"error": "No hay archivo cargado"}
    try:
        client = genai.Client(api_key=api_key)
        img_part = types.Part.from_bytes(data=uploaded_bytes, mime_type=mime_type or "image/png")
        prompt = """
        Analiza esta imagen de una boleta o factura chilena.
        Extrae la siguiente información y entrégala ÚNICAMENTE en formato JSON:
        {
            "Detalle": "Razón Social o nombre del comercio",
            "RazonSocial": "Razón Social o nombre del comercio",
            "Fecha": "Fecha de emisión en formato YYYY-MM-DD",
            "FechaEmision": "Fecha de emisión en formato YYYY-MM-DD",
            "Doc": "Número de boleta, factura o documento",
            "Monto": monto_total_como_número_entero_sin_puntos_ni_simbolos,
            "MontoTotal": monto_total_como_número_entero_sin_puntos_ni_simbolos
        }
        Si no encuentras algún dato, deja el campo vacío o en 0 para el monto.
        Asegúrate de que los campos RazonSocial, FechaEmision y MontoTotal estén siempre presentes.
        """
        data = _call_gemini_with_fallback(client, prompt, img_part)
        return {"success": True, "data": data}
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
            return {
                "success": False,
                "error": "quota_exhausted",
                "user_message": "Cuota de Gemini API agotada. Ingresa los datos manualmente.",
            }
        return {"success": False, "error": err}


def process_id_card_with_ai(api_key, uploaded_bytes, mime_type):
    if not api_key:
        return {"success": False, "error": "API AI no configurada"}
    try:
        client = genai.Client(api_key=api_key)
        img_part = types.Part.from_bytes(data=uploaded_bytes, mime_type=mime_type or "image/png")
        prompt = """
        Analiza esta Cédula de Identidad chilena. 
        1. Extrae el nombre completo.
        2. Extrae el RUT.
        Entrega la respuesta ÚNICAMENTE en este formato JSON:
        {
            "nombre": "Nombre Apellido",
            "rut": "12.345.678-9"
        }
        """
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, img_part]
        )
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        res = json.loads(text.strip())
        return {"success": True, "data": res}
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
            return {"success": False, "error": "quota_exhausted",
                    "user_message": "Cuota de Gemini API agotada. Ingresa los datos manualmente."}
        return {"success": False, "error": err}
