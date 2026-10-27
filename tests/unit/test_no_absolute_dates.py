"""Self-test del guard CI anti-fechas-absolutas (MYK-466, RETRO-3 A1).

Test trampa (AC1): demuestra que el guard detecta fechas absolutas modernas
sin necesidad de romper CI con un test real con fecha 2026. Las lineas con
snippets trampa llevan '# allow-absolute-date' porque SON datos de este test.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_no_absolute_dates import collect_files, main, scan_text, scan_path  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestTrapSnippets:
    """AC1: un test con fecha absoluta 2026 ES detectado por el guard."""

    def test_trampa_datetime_literal(self):
        trap = "record = datetime(2026, 10, 16, 8, 0, 0)"  # allow-absolute-date
        violations = scan_text(trap)
        assert len(violations) == 1 and violations[0][0] == 1
        assert ("datetime" + "(2026") in violations[0][1]

    def test_trampa_date_literal(self):
        trap = "start = date(2026, 10, 16)"  # allow-absolute-date
        assert len(scan_text(trap)) == 1

    def test_trampa_string_iso(self):
        trap = 'row = {"date": "2026-10-16", "justified": 0}'  # allow-absolute-date
        assert len(scan_text(trap)) == 1

    def test_trampa_multilinea_reporta_linea_correcta(self):
        trap = "ok = date.today()\nbad = datetime(2026, 10, 17)\ntam = date.today()"  # allow-absolute-date
        violations = scan_text(trap)
        assert [v[0] for v in violations] == [2]


class TestSnippetsLimpios:
    """Lo que NO debe marcarse: fechas relativas y constantes historicas."""

    def test_relativos_pas(self):
        clean = "ts = date.today() - timedelta(days=3)\nnow = datetime.now()"
        assert scan_text(clean) == []

    def test_relativo_iso_derivado(self):
        clean = 'd = (date.today() + timedelta(days=1)).isoformat()'
        assert scan_text(clean) == []

    def test_constante_protocolo_zk_epoch_2000(self):
        clean = "assert encode_time(datetime(2000, 1, 1, 0, 0, 0)) == 0"
        assert scan_text(clean) == []

    def test_anio_historico_no_moderno(self):
        clean = "legacy = date(1984, 1, 1)"
        assert scan_text(clean) == []

    def test_escape_hatch(self):
        line = "fixed = date(2026, 10, 16)  # allow-absolute-date"
        assert scan_text(line) == []

    def test_llamadas_no_fecha_no_se_miran(self):
        clean = "rows.update(2026)\nuptodate(2026)"
        assert scan_text(clean) == []


class TestRepoLimpio:
    """AC2: el arbol migrado no tiene fechas absolutas; CI rompe si alguien
    introduce una nueva (main() devuelve 1)."""

    def test_tests_y_mock_sin_fechas_absolutas(self):
        files = collect_files(["tests", "mock"])
        assert files, "no se encontraron archivos a escanear"
        for path in files:
            assert scan_path(path) == [], f"violacion(es) en {path}"

    def test_main_exit_0_sobre_repositorio(self):
        assert main(["tests", "mock"]) == 0
