-- Initial schema for WebGUI database

-- Devices table
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT,
    zone TEXT,
    address TEXT NOT NULL,
    port INTEGER DEFAULT 4370,
    password INTEGER DEFAULT 0,
    timeout INTEGER DEFAULT 5,
    protocol TEXT DEFAULT 'tcp',
    status TEXT DEFAULT 'unknown',
    is_enabled BOOLEAN DEFAULT 1,
    firmware_version TEXT,
    serial_number TEXT,
    last_seen DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT DEFAULT 'user',
    is_active BOOLEAN DEFAULT 1,
    last_login DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Device users (users enrolled on devices)
CREATE TABLE IF NOT EXISTS device_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT,
    privilege INTEGER DEFAULT 0,
    password TEXT,
    group_id TEXT,
    user_role TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

-- System configuration
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_devices_address ON devices(address);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_device_users_device_id ON device_users(device_id);
CREATE INDEX IF NOT EXISTS idx_device_users_user_id ON device_users(user_id);

-- Insert default system config
INSERT OR IGNORE INTO system_config (key, value, description) VALUES
    ('smtp_host', '', 'SMTP server hostname'),
    ('smtp_port', '587', 'SMTP server port'),
    ('smtp_username', '', 'SMTP username'),
    ('smtp_password', '', 'SMTP password'),
    ('smtp_from_email', '', 'From email address'),
    ('smtp_use_tls', 'true', 'Use TLS for SMTP'),
    ('smtp_configured', 'false', 'Whether SMTP is configured');
