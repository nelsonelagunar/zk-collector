-- Password reset tokens table for secure single-use tokens
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,  -- SHA256 hash of the token
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,  -- NULL = not used, timestamp = used
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token_hash ON password_reset_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_used_at ON password_reset_tokens(used_at);

-- Rate limiting table for password reset requests
CREATE TABLE IF NOT EXISTS password_reset_rate_limit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_hash TEXT NOT NULL,  -- SHA256 hash of email for privacy
    request_count INTEGER DEFAULT 1,
    first_request_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_request_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(email_hash)
);

-- Index for rate limiting cleanup
CREATE INDEX IF NOT EXISTS idx_password_reset_rate_limit_last_request_at ON password_reset_rate_limit(last_request_at);