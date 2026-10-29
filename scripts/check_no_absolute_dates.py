#!/usr/bin/env python3
"""CI Guard: Ban absolute dates in tests (MYK-466).

Scans test files for hardcoded absolute dates like:
- date(2026, ...) / datetime(2026, ...)
- "2026-..." string literals in test data/setup (not assertions)

Allows relative dates:
- date.today() + timedelta
- _day(offset) helper
- datetime.now(), datetime.utcnow()
- String literals in assertions (output validation)

Some test files legitimately use absolute dates for timezone/integration testing.
These are in ALLOWED_FILES list below.
"""

import ast
import re
import sys
from pathlib import Path


FORBIDDEN_YEARS = {2025, 2026, 2027, 2028, 2029, 2030}

# Files with legitimate absolute dates (timezone tests, integration tests, etc.)
ALLOWED_FILES = {
    "tests/test_attendance_timezone.py",
    "tests/test_attendance_stats.py",
    "tests/test_attendance_stats_routes.py",
    "tests/test_attendance_stats_ui.py",
    "tests/test_attendance_integrity.py",
    "tests/test_attendance_date_filter.py",
    "tests/test_buffer.py",
    "tests/test_clock_sync.py",
    "tests/test_export_legal.py",
    "tests/test_medical_leaves.py",
    "tests/test_work_centers.py",
    "tests/test_medical_leaves_routes.py",
    "tests/test_medical_leaves_repository.py",
    "tests/test_mi_asistencia.py",
    "tests/test_mcp_server.py",
    "tests/integration/test_e2e_flow.py",
    "tests/test_zk_client_detailed.py",
}

# Allowed patterns (relative dates) - these should not trigger errors
ALLOWED_PATTERNS = [
    r"date\.today\(\)",
    r"datetime\.today\(\)",
    r"datetime\.now\(\)",
    r"datetime\.utcnow\(\)",
    r"_day\s*\(",
    r"timedelta\(",
    r"date\.fromordinal\(",
    r"datetime\.fromtimestamp\(",
]


def is_assertion_line(line: str) -> bool:
    """Check if line is an assertion (output validation)."""
    stripped = line.strip()
    return (
        stripped.startswith("assert ")
        or stripped.startswith("self.assert")
        or "assert " in stripped[:20]
    )


def check_file(filepath: Path) -> list[tuple[int, str, str]]:
    """Check a single file for absolute date string literals in test data (not assertions)."""
    errors = []
    content = filepath.read_text(encoding="utf-8")
    lines = content.splitlines()

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#"):
            continue

        # Skip assertion lines (output validation)
        if is_assertion_line(line):
            continue

        # Check if line contains any allowed pattern
        allowed = False
        for pattern in ALLOWED_PATTERNS:
            if re.search(pattern, line):
                allowed = True
                break

        if allowed:
            continue

        # Check for forbidden YYYY-MM-DD string literals (not in assertions)
        if re.search(r'["\']202[5-9]-\d{2}-\d{2}["\']', line) or re.search(r'["\']2030-\d{2}-\d{2}["\']', line):
            errors.append((i, "YYYY-MM-DD string literal in test data", line.strip()))

    return errors


def check_ast(filepath: Path) -> list[tuple[int, str, str]]:
    """AST-based check for date/datetime constructors with literal year args."""
    errors = []
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except SyntaxError:
        return errors

    lines = content.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in ("date", "datetime") and node.args:
                first_arg = node.args[0]
                # Check if first arg is a literal integer in forbidden range
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, int):
                    if first_arg.value in FORBIDDEN_YEARS:
                        line_num = node.lineno
                        line = lines[line_num - 1] if line_num <= len(lines) else ""
                        # Skip assertion lines (output validation)
                        if is_assertion_line(line):
                            continue
                        errors.append((line_num, f"{func_name}({first_arg.value}, ...)", line.strip()))

    return errors


def main():
    test_dir = Path("tests")
    if not test_dir.exists():
        print("No tests/ directory found")
        return 0

    all_errors = []

    for test_file in test_dir.rglob("test_*.py"):
        if "__pycache__" in str(test_file):
            continue

        # Skip allowed files
        if str(test_file) in ALLOWED_FILES:
            continue

        # AST-based check for date/datetime constructors
        ast_errors = check_ast(test_file)
        # Regex check for string literals (only in non-assertion lines)
        regex_errors = check_file(test_file)

        for line_num, pattern, line in ast_errors:
            all_errors.append((str(test_file), line_num, pattern, line))
        for line_num, pattern, line in regex_errors:
            all_errors.append((str(test_file), line_num, pattern, line))

    # Deduplicate by file:line:pattern
    seen = set()
    unique_errors = []
    for filepath, line_num, pattern, line in all_errors:
        key = (filepath, line_num, pattern)
        if key not in seen:
            seen.add(key)
            unique_errors.append((filepath, line_num, pattern, line))

    if unique_errors:
        print("❌ CI GUARD FAILED: Absolute dates found in tests (MYK-466)")
        print("=" * 60)
        for filepath, line_num, pattern, line in unique_errors:
            print(f"  {filepath}:{line_num} - {pattern}")
            print(f"    {line}")
        print("=" * 60)
        print("Use relative dates instead:")
        print("  - date.today() + timedelta(days=N)")
        print("  - _day(offset) helper (from test_alerts.py)")
        print("  - datetime.now() / datetime.utcnow()")
        return 1

    print("✅ CI GUARD PASSED: No absolute dates found in tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())