---
name: zk-157-password-reset
description: MYK-157 password reset flow implementation status and design
metadata:
  type: project
---

Implementing BACKLOG Task 15 — password reset email integration. The issue context claims commits a574654/3b7baba implement it, but they do NOT exist in this repo. Actual state: `/forgot-password` POST is stubbed (src/webgui/routes/auth.py:131-142); no reset route; no reset templates; no SMTP integration; no rate limiting.

Design decisions:
- SMTP config lives in `system_config` table (smtp_host/port/username/password/from_email/use_tls/configured), written by docker-entrypoint.sh. Read from there; fallback to env if needed.
- Reset token = JWT (type=password_reset, 1h expiry, jti), signed by WEBGUI_SECRET_KEY, stored hashed (sha256) in new `password_reset_tokens` table for single-use enforcement.
- Rate limit: max 3 requests/hour per email in `password_reset_rate_limit` table.
- Admin fallback: when SMTP not configured, flash the reset token in the UI.
- New migration `migrations/002_password_reset.sql`.
- Templates: src/webgui/templates/auth/forgot_password.html, reset_password.html.
- Routes: POST /auth/forgot-password, GET/POST /auth/reset-password/<token> (blueprint prefixed /auth).

Acceptance criteria (all to implement):
1. POST /forgot-password sends reset email via SMTP (when configured)
2. Email contains reset link with valid JWT token (1h expiry)
3. GET /reset-password/<token> validates token, shows form if valid
4. POST /reset-password/<token> updates password, invalidates token
5. Admin fallback: token displayed in UI when SMTP not configured
6. Rate limiting on /forgot-password (max 3 requests/hour per email)
7. Integration test: full flow with mock SMTP
8. Security: tokens single-use, expire, constant-time comparison

Status: NOT STARTED — baseline tests not yet run.
