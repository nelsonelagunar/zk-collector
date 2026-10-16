# INTERACTION CARD: MYK-183 / MYK-194 — Password Reset Decision

## Status: PENDING BOARD DECISION

**Issue**: Password reset flow exists in code but has no SMTP configured
**Options**: A) SMTP real via Infisical | B) Remove /forgot-password from MVP
**Blocker**: MYK-184 (Infisical universal auth credentials)

---

## Context

The `origin/feature/myk-92-dashboard-modernization` branch includes:
- `/auth/forgot-password` route + template (`forgot_password.html`)
- `/auth/reset-password/<token>` route + template (`reset_password.html`)
- SMTP wiring in `docker-entrypoint.sh` and `configs/collector.yaml.example`
- Token generation/validation in `src/webgui/auth.py`
- Rate limiting by email (not IP) — security fix `c0a66e3`
- Timing attack fix in reset token verification — security fix `c0a66e3`

**BUT**: No SMTP credentials configured → emails never send → flow is broken in production.

---

## Option A: SMTP Real via Infisical

**Pros**:
- Complete auth flow for production
- Users can self-recover accounts
- Standard SaaS feature

**Cons**:
- Requires MYK-184: Infisical universal auth credentials (machine identity)
- Adds operational complexity (SMTP provider, delivery monitoring)
- Extra secrets to manage: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `WEBGUI_BASE_URL`

**Required if chosen**:
1. Board provides Infisical universal auth (MYK-184)
2. Create 6 SMTP secrets in Infisical
3. Update `docker-entrypoint.sh` to inject from Infisical
4. Test email delivery in staging

---

## Option B: Remove /forgot-password from MVP

**Pros**:
- Simplifies deployment (no SMTP dependency)
- Reduces attack surface
- Faster to production
- Admin can manually reset via DB if needed

**Cons**:
- No self-service password recovery
- Manual admin intervention required
- Not "production-ready" for external users

**Required if chosen**:
1. Delete `/auth/forgot-password` route + template
2. Delete `/auth/reset-password/<token>` route + template
3. Remove SMTP config from `docker-entrypoint.sh`, `configs/collector.yaml.example`
4. Remove `SMTP_*` env vars from docs

---

## Decision Needed

**Board must choose**: `A` or `B` with justification.

```markdown
DECISIÓN: A|B
JUSTIFICACIÓN: <one-line reason>
```

---

## Files Affected (on feature branch)

| File | Action if A | Action if B |
|------|-------------|-------------|
| `src/webgui/routes/auth.py` | Keep | Remove reset routes |
| `src/webgui/templates/forgot_password.html` | Keep | Delete |
| `src/webgui/templates/reset_password.html` | Keep | Delete |
| `docker-entrypoint.sh` | Keep SMTP wiring | Remove SMTP section |
| `configs/collector.yaml.example` | Keep SMTP section | Remove SMTP section |
| `docs/configuration.md` | Document SMTP | Remove SMTP docs |

---

## Security Notes (Already Implemented on Feature Branch)

- ✅ Rate limit by email (not IP) — prevents enumeration
- ✅ Constant-time token verification — prevents timing attacks
- ✅ Token expiry (1 hour) + single-use + invalidation on use
- ✅ Secure token generation (secrets.token_urlsafe)

---

## Next Steps
1. Board posts decision in this interaction
2. PM implements chosen option
3. Update SPRINT-2.md / BACKLOG.md accordingly
4. If A: trigger MYK-184 for Infisical credentials
