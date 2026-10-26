-- Add attendance_buffer table for local storage (collector)
-- This table is used by BufferRepository for offline-first polling

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

-- Unique index to prevent duplicates (idempotent polling)
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_attendance 
ON attendance_buffer(user_id, timestamp, device_ip);

-- Sync log table
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    records_synced INTEGER,
    records_failed INTEGER,
    status TEXT,
    error_message TEXT,
    duration_seconds REAL
);

