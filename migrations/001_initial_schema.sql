-- Initial schema for WebGUI database
-- Creates all core tables: users, system_config, devices, attendance_buffer

-- Users table for WebGUI admin authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'admin' CHECK (role IN ('admin', 'operator')),
    is_active INTEGER DEFAULT 1 CHECK (is_active IN (0, 1)),
    last_login DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Index on username for fast lookups
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- System configuration table
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Devices table for ZKTeco device management
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ip TEXT NOT NULL,
    port INTEGER DEFAULT 4370,
    password TEXT DEFAULT '0',
    timeout INTEGER DEFAULT 5,
    status TEXT DEFAULT 'unknown' CHECK (status IN ('online', 'offline', 'unknown', 'error')),
    last_seen DATETIME,
    enabled INTEGER DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Index on IP for fast lookups
CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(ip);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);

-- Attendance buffer table for local storage before cloud sync
CREATE TABLE IF NOT EXISTS attendance_buffer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    status INTEGER NOT NULL,
    device_ip TEXT NOT NULL,
    punch_type TEXT,
    synced INTEGER DEFAULT 0 CHECK (synced IN (0, 1)),
    sync_attempts INTEGER DEFAULT 0,
    last_sync_attempt DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for attendance_buffer
CREATE INDEX IF NOT EXISTS idx_attendance_synced ON attendance_buffer(synced, timestamp);
CREATE INDEX IF NOT EXISTS idx_attendance_timestamp ON attendance_buffer(timestamp);
CREATE INDEX IF NOT EXISTS idx_attendance_user_id ON attendance_buffer(user_id);
CREATE INDEX IF NOT EXISTS idx_attendance_device_ip ON attendance_buffer(device_ip);

-- Insert default system config
INSERT OR IGNORE INTO system_config (key, value, description) VALUES
    ('setup_completed', 'false', 'Whether initial setup has been completed'),
    ('smtp_configured', 'false', 'Whether SMTP is configured for email'),
    ('smtp_host', '', 'SMTP server hostname'),
    ('smtp_port', '587', 'SMTP server port'),
    ('smtp_username', '', 'SMTP username'),
    'smtp_password', '', 'SMTP password (encrypted)'),
    ('smtp_from_email', '', 'From email address'),
    ('smtp_use_tls', 'true', 'Use TLS for SMTP connection');