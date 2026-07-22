import re
import logging
from io import BytesIO

from rapidocr import RapidOCR

_ocr_engine = None

logger = logging.getLogger(__name__)


def _get_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine


def _run_ocr(uploaded_bytes, mime_type=None):
    engine = _get_engine()
    result = engine(uploaded_bytes)
    if result is None or result.txts is None:
        return ""
    return "\n".join(result.txts)


def _clean_amount(raw):
    raw = re.sub(r'[^\d.,]', '', raw)
    raw = raw.replace('.', '').replace(',', '')
    try:
        return int(raw)
    except ValueError:
        return 0


def _extract_date(text):
    m = re.search(r'(0[1-9]|[12]\d|3[01])[/\-.](0[1-9]|1[0-2])[/\-.](20\d{2})', text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.search(r'(20\d{2})[/\-.](0[1-9]|1[0-2])[/\-.](0[1-9]|[12]\d|3[01])', text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


def _extract_rut(text):
    matches = re.findall(r'(\d{1,3}(?:\.\d{3}){2}-[\dkK])', text)
    if matches:
        return matches[0]
    matches = re.findall(r'(\d{7,8}-[\dkK])', text)
    if matches:
        return matches[0]
    return ""


def _extract_receipt_fields(ocr_text):
    lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]

    razon_social = ""
    for line in lines[:5]:
        cleaned = re.sub(r'[^\w\sáéíóúñÁÉÍÓÚÑ.]', '', line).strip()
        if len(cleaned) >= 3 and not re.match(r'^[\d\s/\-\.]+$', cleaned):
            razon_social = cleaned
            break

    fecha = _extract_date(ocr_text)

    monto_total = 0
    for pattern in [
        r'(?:TOTAL\s*A\s*PAGAR|TOTAL\s*NETO|TOTAL)\s*\$?\s*([\d\.\,]+)',
        r'(?:Monto\s*Total|MONTO\s*TOTAL)\s*\$?\s*([\d\.\,]+)',
        r'\$\s*([\d\.\,]+)',
    ]:
        m = re.search(pattern, ocr_text, re.IGNORECASE)
        if m:
            monto_total = _clean_amount(m.group(1))
            if monto_total > 0:
                break

    doc = ""
    for pattern in [
        r'(?:Folio|N[uú]mero|N[°º]|Boleta|Factura)\s*#?\s*:?\s*(\d+)',
        r'(?:Doc|D[Oo]c)\s*#?\s*:?\s*(\d+)',
    ]:
        m = re.search(pattern, ocr_text, re.IGNORECASE)
        if m:
            doc = m.group(1)
            break

    return {
        "Detalle": razon_social,
        "RazonSocial": razon_social,
        "Fecha": fecha,
        "FechaEmision": fecha,
        "Doc": doc,
        "Monto": monto_total,
        "MontoTotal": monto_total,
    }


def _extract_idcard_fields(ocr_text):
    lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]

    rut = _extract_rut(ocr_text)

    nombre = ""
    stop_words = {'REPÚBLICA', 'REPUBLICA', 'CHILE', 'IDENTIDAD', 'CEDULA', 'CÉDULA',
                  'REGISTRO', 'CIVIL', 'NOMBRE', 'RUT', 'NACIMIENTO', 'FECHA',
                  'NACIONALIDAD', 'SEXO', 'M', 'F', 'VIGENTE', 'DOCUMENTO'}
    for line in lines:
        cleaned = re.sub(r'[^\w\sáéíóúñÁÉÍÓÚÑ]', '', line).strip()
        upper = cleaned.upper()
        if upper in stop_words or len(cleaned) < 3:
            continue
        if re.match(r'^[\d\.\-\s]+$', cleaned):
            continue
        if cleaned == rut or cleaned.replace('.', '').replace('-', '') == rut.replace('.', '').replace('-', ''):
            continue
        words = cleaned.split()
        if len(words) >= 2 and all(w[0].isupper() or not w.isalpha() for w in words if len(w) > 1):
            nombre = cleaned
            break

    return {"nombre": nombre, "rut": rut}


def process_receipt_with_ai(api_key, uploaded_bytes, mime_type=None):
    if not uploaded_bytes:
        return {"success": False, "error": "No hay archivo cargado"}
    try:
        ocr_text = _run_ocr(uploaded_bytes, mime_type)
        if not ocr_text.strip():
            return {"success": False, "error": "No se pudo extraer texto de la imagen. Intente con una imagen más clara."}
        data = _extract_receipt_fields(ocr_text)
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("Error en OCR de comprobante")
        return {"success": False, "error": str(e)}


def process_id_card_with_ai(api_key, uploaded_bytes, mime_type=None):
    if not uploaded_bytes:
        return {"success": False, "error": "No hay archivo cargado"}
    try:
        ocr_text = _run_ocr(uploaded_bytes, mime_type)
        if not ocr_text.strip():
            return {"success": False, "error": "No se pudo extraer texto de la imagen. Intente con una imagen más clara."}
        data = _extract_idcard_fields(ocr_text)
        if not data.get("nombre") and not data.get("rut"):
            return {"success": False, "error": "No se pudieron detectar nombre ni RUT. Intente con una imagen más clara."}
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("Error en OCR de cédula")
        return {"success": False, "error": str(e)}
