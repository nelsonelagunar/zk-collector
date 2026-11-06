-- Personal Access Tokens para API REST externa (MYK-407)
-- No reusar JWT de sesion para integraciones: tokens separados con scopes y revocacion.

CREATE TABLE IF NOT EXISTS api_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,                          -- etiqueta para el usuario
    token_hash TEXT NOT NULL UNIQUE,             -- SHA256 del token plano
    scopes TEXT NOT NULL DEFAULT 'read',         -- espacio-separado: read write
    last_used_at DATETIME,
    revoked_at DATETIME,
    expires_at DATETIME,                         -- NULL = no expira
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id ON api_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_token_hash ON api_tokens(token_hash);
