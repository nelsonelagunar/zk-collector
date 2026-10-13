-- Device Users table for mapping ZKTeco user_id to readable names
-- Stores users synced from ZKTeco devices

CREATE TABLE IF NOT EXISTS device_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_ip TEXT NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    privilege INTEGER DEFAULT 0,
    group_id INTEGER DEFAULT 1,
    user_role INTEGER DEFAULT 0,
    synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(device_ip, user_id)
);

CREATE INDEX IF NOT EXISTS idx_device_users_device_ip ON device_users(device_ip);
CREATE INDEX IF NOT EXISTS idx_device_users_user_id ON device_users(user_id);