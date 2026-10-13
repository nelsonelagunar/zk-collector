# MYK-168 Delegation Summary

**Parent Issue:** MYK-168 [P1-1] Vista usuarios del device (mapear user_id → nombre)

**Delegated to (created 2026-10-13):**

| Child Issue | Assignee | Scope |
|-------------|----------|-------|
| MYK-175 | backend-dev (051c0b6e-43e9-422a-b3fc-b96323a07a5d) | ZKClient.get_users, device_users migration, sync endpoint, APIs |
| MYK-176 | frontend-dev (d9be0232-0306-4b59-9323-747997bad616) | Device detail sync button, users table, attendance name display |

**Status:** Both child issues created with `todo` status, `high` priority.

**Dependencies:** 
- MYK-168 requires MYK-164, MYK-165, MYK-166 (P0 sprint 2 items)
- Frontend (MYK-176) blocked on backend API completion (MYK-175)

**Sprint Context:** Per SPRINT-2.md scope update, P1 items (including MYK-168) are slated for Sprint 3 Planning. Current Sprint 2 focuses on P0 items only.

**Acceptance Criteria (from MYK-168):**
```bash
curl -s "http://10.0.0.16:8081/api/device-users?device_ip=192.168.1.101"
# → [{"user_id":"123","name":"Juan Pérez"}]

curl -s "http://10.0.0.16:8081/api/attendance"
# → Records incluyen campo "user_name" (o "name") junto a "user_id"
```

**Definition of Done for MYK-168:**
1. Both child issues complete (code merged, CI green, reviewed, QA)
2. Verification against deploy: UI device detail → "Sincronizar usuarios" → tabla asistencia muestra nombres
