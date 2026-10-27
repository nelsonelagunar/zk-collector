"""
Personal Access Tokens (PAT) para la API REST externa — MYK-407.

Tokens opaque (no JWT) con hash SHA256, scopes y revocacion.
Se emiten via POST /auth/api/tokens (sesion admin) y se consumen
con Authorization: Bearer <token> en los endpoints /api/*.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import cast

VALID_SCOPES = ("read", "write")
SCOPE_SEPARATOR = " "


class ApiTokenService:
    """Emision, verificacion y revocacion de tokens de API."""

    def __init__(self, db):
        self.db = db

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _token_secret() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_scopes(scopes: list[str]) -> list[str]:
        """Normaliza y valida la lista de scopes. ValueError si hay uno invalido."""
        normalized = sorted({s.strip() for s in scopes if s and s.strip()})
        invalid = [s for s in normalized if s not in VALID_SCOPES]
        if invalid:
            raise ValueError(f"scopes invalidos: {', '.join(invalid)}")
        return normalized

    def issue_token(
        self,
        user_id: int,
        name: str,
        scopes: list[str],
        expires_in_days: int | None = 90,
    ) -> dict:
        """Crea un token. Devuelve el token plano (unica vez) + registro."""
        normalized = self.validate_scopes(scopes)
        token = self._token_secret()
        token_hash = self.hash_token(token)

        expires_at = None
        if expires_in_days:
            expires_at = (
                datetime.now() + timedelta(days=expires_in_days)
            ).strftime("%Y-%m-%d %H:%M:%S")

        token_id = self.db.insert(
            "api_tokens",
            {
                "user_id": user_id,
                "name": name,
                "token_hash": token_hash,
                "scopes": SCOPE_SEPARATOR.join(normalized),
                "expires_at": expires_at,
            },
        )
        record = self.db.fetch_one("SELECT * FROM api_tokens WHERE id = ?", (token_id,))
        return {"token": token, "record": record}

    def verify_token(self, token: str, required_scope: str | None = None) -> dict | None:
        """Devuelve el registro del token si es valido (no revocado, no expirado)."""
        token_hash = self.hash_token(token)
        record = self.db.fetch_one("SELECT * FROM api_tokens WHERE token_hash = ?", (token_hash,))
        if not record:
            return None

        if record["revoked_at"]:
            return None

        if record["expires_at"]:
            try:
                expires = datetime.strptime(record["expires_at"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
            if expires <= datetime.now():
                return None

        if required_scope:
            token_scopes = (record["scopes"] or "").split(SCOPE_SEPARATOR)
            if required_scope not in token_scopes:
                return None

        # Actualizar last_used_at sin bloquear la respuesta
        self.db.update(
            "api_tokens",
            {"last_used_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            "id = ?",
            (record["id"],),
        )
        return cast("dict | None", record)

    def list_tokens(self, user_id: int | None = None) -> list[dict]:
        """Lista tokens (sin hash). Opcionalmente filtrados por usuario."""
        columns = (
            "id, user_id, name, scopes, last_used_at, revoked_at, expires_at, created_at"
        )
        if user_id is not None:
            return cast(
                "list[dict]",
                self.db.fetch_all(
                    f"SELECT {columns} FROM api_tokens "
                    "WHERE user_id = ? ORDER BY id DESC",
                    (user_id,),
                ),
            )
        return cast(
            "list[dict]",
            self.db.fetch_all(f"SELECT {columns} FROM api_tokens ORDER BY id DESC"),
        )

    def revoke_token(self, token_id: int, user_id: int | None = None) -> bool:
        """Revoca un token. Si user_id se da, solo revoca tokens de ese usuario."""
        conditions = ["id = ?", "revoked_at IS NULL"]
        params: list = [token_id]
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)

        count = self.db.update(
            "api_tokens",
            {"revoked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            " AND ".join(conditions),
            tuple(params),
        )
        return bool(count)
