"""
Validadores de formato para los datos laborales del empleado (MYK-423).

Formatos de referencia:
- CURP (RENAPO): 18 caracteres — 4 letras, fecha YYMMDD, sexo H/M, clave de
  entidad federativa, 3 consonantes interiores, homoclave alfanumerica y
  digito verificador.
- RFC (SAT): persona moral 12 caracteres (3 letras + fecha + homoclave) o
  persona fisica 13 (4 letras + fecha + homoclave).
- NSS (IMSS): 11 digitos.

La validacion es de ESTRUCTURA, no semantica: no se recalcula el digito
verificador del CURP ni se coteja contra padrones RENAPO/SAT (eso exigiria
tablas oficiales). `tipo_jornada` se limita a las jornadas de LFT 58-60.
"""

import re

CURP_ENTIDADES = (
    "AS",
    "BC",
    "BS",
    "CC",
    "CH",
    "CL",
    "CM",
    "CS",
    "DF",
    "DG",
    "GR",
    "GT",
    "HG",
    "JC",
    "MC",
    "MN",
    "MS",
    "NE",
    "NL",
    "NT",
    "OC",
    "PL",
    "QR",
    "QT",
    "SL",
    "SP",
    "SR",
    "TC",
    "TL",
    "TS",
    "VZ",
    "YN",
    "ZS",
)

TIPO_JORNADA_VALUES = ("diurna", "mixta", "nocturna")

_FECHA = r"[0-9]{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])"
_CURP_RE = re.compile(
    rf"^[A-ZÑ]{{4}}{_FECHA}[HM](?:{'|'.join(CURP_ENTIDADES)})"
    r"[B-DF-HJ-NP-TV-ZÑ]{3}[0-9A-Z][0-9]$"
)
_RFC_RE = re.compile(rf"^(?:[A-ZÑ&]{{4}}|[A-ZÑ&]{{3}}){_FECHA}[0-9A-Z]{{3}}$")
_NSS_RE = re.compile(r"^[0-9]{11}$")

LABOR_FIELDS = ("curp", "rfc", "nss", "imss_numero_seguro", "tipo_jornada", "turno")


def _clean(value: object) -> str | None:
    """''/None -> None; texto -> strip."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def validate_curp(value: str) -> str:
    """CURP valido (18 caracteres, estructura RENAPO) o ValueError."""
    curp = value.upper()
    if not _CURP_RE.match(curp):
        raise ValueError(
            f"curp con formato invalido: {value!r} (se esperan 18 caracteres con estructura RENAPO)"
        )
    return curp


def validate_rfc(value: str) -> str:
    """RFC valido (12 persona moral / 13 persona fisica, estructura SAT) o ValueError."""
    rfc = value.upper()
    if not _RFC_RE.match(rfc):
        raise ValueError(
            f"rfc con formato invalido: {value!r} (se esperan 12 o 13 caracteres "
            "con estructura SAT)"
        )
    return rfc


def validate_nss(value: str) -> str:
    """NSS valido (11 digitos IMSS) o ValueError."""
    if not _NSS_RE.match(value):
        raise ValueError(f"nss con formato invalido: {value!r} (se esperan 11 digitos)")
    return value


def validate_imss_numero_seguro(value: str) -> str:
    """Numero de seguro IMSS valido (11 digitos, mismo formato que NSS) o ValueError."""
    if not _NSS_RE.match(value):
        raise ValueError(
            f"imss_numero_seguro con formato invalido: {value!r} (se esperan 11 digitos)"
        )
    return value


def validate_tipo_jornada(value: str) -> str:
    """Tipo de jornada dentro del catalogo LFT 58-60 o ValueError."""
    if value not in TIPO_JORNADA_VALUES:
        raise ValueError(
            f"tipo_jornada invalido: {value!r} (esperado uno de {TIPO_JORNADA_VALUES})"
        )
    return value


def normalize_labor_fields(data: dict) -> None:
    """Normaliza y valida en sitio los campos laborales presentes en `data`.

    - Solo toca las claves presentes: los ausentes no se agregan (un update
      parcial no debe limpiar campos que no fueron enviados).
    - Vacios ('' o espacios) -> None (no capturado).
    - CURP/RFC -> mayusculas; NSS/IMSS -> digitos sin espacios.
    - Lanza ValueError con el primer campo invalido.
    """
    if "curp" in data:
        curp = _clean(data["curp"])
        data["curp"] = validate_curp(curp) if curp else None

    if "rfc" in data:
        rfc = _clean(data["rfc"])
        data["rfc"] = validate_rfc(rfc) if rfc else None

    if "nss" in data:
        nss = _clean(data["nss"])
        data["nss"] = validate_nss(nss) if nss else None

    if "imss_numero_seguro" in data:
        imss = _clean(data["imss_numero_seguro"])
        data["imss_numero_seguro"] = validate_imss_numero_seguro(imss) if imss else None

    if "tipo_jornada" in data:
        tipo_jornada = _clean(data["tipo_jornada"])
        data["tipo_jornada"] = validate_tipo_jornada(tipo_jornada) if tipo_jornada else None

    if "turno" in data:
        data["turno"] = _clean(data["turno"])
