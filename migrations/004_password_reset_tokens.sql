-- Password Reset Tokens table for secure password recovery (MYK-303)

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,  -- SHA256 hash of the reset token
    expires_at DATETIME NOT NULL,
    used_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Index for token lookup and cleanup
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at);

-- SMTP defaults for password reset email (MYK-303); existing values win
INSERT OR IGNORE INTO system_config (key, value, description) VALUES
    ('smtp_configured', 'false', 'Whether SMTP is configured for email'),
    ('smtp_host', '', 'SMTP server hostname'),
    ('smtp_port', '587', 'SMTP server port'),
    ('smtp_username', '', 'SMTP username'),
    ('smtp_password', '', 'SMTP password (encrypted)'),
    ('smtp_from_email', '', 'From email address'),
    ('smtp_use_tls', 'true', 'Use TLS for SMTP connection');
