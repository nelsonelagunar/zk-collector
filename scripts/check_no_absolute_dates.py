#!/usr/bin/env python3
"""Guard CI anti-fechas-absolutas en tests y mocks (MYK-466, RETRO-3 A1).

Los tests con fechas absolutas hardcodeadas (ej. datetime(2026, 10, 16)) pasan
CI al mergear y vencen dias despues, rompiendo CI de PRs que no las tocan
(time-bomb del Sprint 3, PR #69). Este check falla CI si un test/mock usa una
fecha absoluta de era moderna en lugar de fechas relativas a date.today().

Reglas (sobre tests/ y mock/, archivos .py y .json):
- date(YYYY...)/datetime(YYYY...) con 2020 <= YYYY <= 2100 -> violacion.
- Strings ISO "YYYY-MM-DD..." con 2020 <= YYYY <= 2100 -> violacion
  (cubre timestamps de fixtures, seeds JSON y query params de test).

Anios historicos/constantes de protocolo (< 2020, ej. epoch ZK 2000-01-01)
pasan: solo las fechas de era moderna caducan respecto a date.today().

Escape hatch: agregar '# allow-absolute-date' al final de la linea.

Uso: python scripts/check_no_absolute_dates.py [rutas...]  (default: tests mock)
Salida: 0 = limpio, 1 = violaciones (formato path:line: detalle).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MIN_YEAR = 2020
MAX_YEAR = 2100
ESCAPE = "allow-absolute-date"

# date(...)/datetime(...) con literal de anio absoluto. El lookbehind evita
# matchear update(/mydate(/x.date( y llamadas sin literal (date.today()).
ABSOLUTE_CALL = re.compile(r"(?<![\w.])(?:date|datetime)\s*\(\s*(\d{4})\b")

# Fecha ISO en string: "2026-10-16", "2026-10-13T08:00:00", "2026-10-23 08:00".
ABSOLUTE_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})")

SCANNED_SUFFIXES = {".py", ".json"}


def _is_modern(year: int) -> bool:
    return MIN_YEAR <= year <= MAX_YEAR


def scan_line(line: str) -> str | None:
    """Devuelve la descripcion de la violacion de la linea, o None si esta limpia."""
    if ESCAPE in line:
        return None
    match = ABSOLUTE_CALL.search(line)
    if match and _is_modern(int(match.group(1))):
        return f"fecha absoluta {match.group(0)!r}: usa date.today()/timedelta"
    match = ABSOLUTE_ISO.search(line)
    if match and _is_modern(int(match.group(1))):
        return f"fecha absoluta {match.group(0)!r}: usa date.today()/timedelta"
    return None


def scan_text(text: str) -> list[tuple[int, str]]:
    """Devuelve [(linea_1_based, descripcion)] de las violaciones del texto."""
    violations = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        detail = scan_line(line)
        if detail:
            violations.append((lineno, detail))
    return violations


def scan_path(path: Path) -> list[tuple[int, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [(0, f"no legible: {exc}")]
    return scan_text(text)


def collect_files(roots: list[str]) -> list[Path]:
    files = []
    for root in roots:
        base = Path(root)
        if base.is_file():
            files.append(base)
        elif base.is_dir():
            files.extend(
                p for p in sorted(base.rglob("*")) if p.suffix in SCANNED_SUFFIXES and p.is_file()
            )
        else:
            print(f"check_no_absolute_dates: ruta inexistente: {root}", file=sys.stderr)
    return files


def main(argv: list[str]) -> int:
    roots = argv or ["tests", "mock"]
    total = 0
    for path in collect_files(roots):
        for lineno, detail in scan_path(path):
            print(f"{path}:{lineno}: {detail} (MYK-466; escape: # {ESCAPE})")
            total += 1
    if total:
        print(f"check_no_absolute_dates: {total} fecha(s) absoluta(s) en {roots}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
