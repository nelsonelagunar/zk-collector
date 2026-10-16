# HANDOFF: MYK-166 → FRONTEND-DEV — Attendance Page (P0-3)

## Status: LOCAL DONE — BLOCKED ON P0-1 MERGE

**Branch**: `origin/feature/myk-92-dashboard-modernization` (NOT merged to `fix/p0-1-supervisord-clean`)
**Commit**: `a328184` (feat: add attendance export UI + password reset template)
**Validated**: Feature branch has 134/135 tests passing, ruff CLEAN

---

## What's Implemented (on feature branch)

### 1. Routes (`src/webgui/routes/attendance.py`)
- `GET /attendance` — Main attendance page with Alpine.js UI
- `GET /api/devices` — Devices for filter dropdown
- `GET /api/attendance` — Paginated, filtered attendance records (JSON)
- `GET /attendance/export` / `GET /api/export/attendance` — CSV/Excel export streaming

### 2. Template (`src/webgui/templates/attendance/list.html`)
- Full Tailwind/Alpine.js implementation
- Filters: date range, user_id, device dropdown
- Paginated table (50/page)
- Export buttons (CSV + Excel)
- Dark mode support
- Responsive design

### 3. Buffer Repository Extensions (`src/buffer/repository.py`)
- `get_attendance_records()` — Filtered, paginated query
- `get_attendance_count()` — Total count for pagination
- `stream_attendance_records()` — Chunked streaming for large exports

### 4. Dependencies Added
- `openpyxl` in `pyproject.toml` (for Excel export)
- `flatpickr` via CDN (date pickers)

---

## What Needs Integration

**MERGE STRATEGY**: Merge `origin/feature/myk-92-dashboard-modernization` → `fix/p0-1-supervisord-clean`

### Files to merge (key differences):
| File | Action |
|------|--------|
| `src/webgui/routes/attendance.py` | NEW — copy entirely |
| `src/webgui/templates/attendance/list.html` | NEW — copy entirely |
| `src/buffer/repository.py` | MERGE — add 3 methods |
| `pyproject.toml` | ADD `openpyxl>=3.1.0` to dependencies |
| `src/webgui/server.py` | REGISTER `attendance_bp` blueprint |
| `migrations/004_device_users.sql` | NEW — user lookup for attendance page |

---

## Acceptance Criteria (from SPRINT-2.md)
```
P0-3: Página asistencia WebGUI: tabla + filtros + paginación
- Ruta `/attendance` con tabla, filtros (fecha, user, device), paginación 25/page
- Registros attendance_buffer visibles y navegables en :8081
```

---

## Next Steps (When Platform Unblocks)
1. Merge feature branch into `fix/p0-1-supervisord-clean`
2. Run tests: `pytest tests/integration/test_webgui_integration.py -k attendance`
3. Verify `ruff check src/ tests/` still CLEAN
4. Deploy to staging → verify at https://zk-receiver.tail5276ec.ts.net/attendance
5. Mark MYK-166 as DONE with deploy evidence

---

## Related
- `HANDOFF_MYK171_TO_TESTER.md` — Integration tests need this page working first
- `INTERACTION_MYK183_SMTP_DECISION.md` — Password reset decision (also on feature branch)
