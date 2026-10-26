-- Fix devices schema: rename ip -> address, enabled -> is_enabled
-- This migration handles the schema change from old (ip, enabled) to new (address, is_enabled)
-- Live databases have the old schema with additional columns from 003_device_columns.sql

BEGIN TRANSACTION;

-- Create new table with correct schema
CREATE TABLE devices_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT,
    zone TEXT,
    address TEXT NOT NULL,
    port INTEGER DEFAULT 4370,
    password INTEGER DEFAULT 0,
    timeout INTEGER DEFAULT 5,
    protocol TEXT DEFAULT "tcp",
    status TEXT DEFAULT "unknown",
    is_enabled BOOLEAN DEFAULT 1,
    firmware_version TEXT,
    serial_number TEXT,
    last_seen DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Copy data from old table to new table
-- Old schema has: ip, enabled (no address, no is_enabled)
-- So we directly map: ip -> address, enabled -> is_enabled
INSERT INTO devices_new (
    id, name, location, zone, address, port, password, timeout,
    protocol, status, is_enabled, firmware_version, serial_number,
    last_seen, created_at, updated_at
)
SELECT 
    id, name, 
    location, zone,
    ip as address,
    port, 
    CASE 
        WHEN typeof(password) = "text" THEN CAST(password AS INTEGER)
        ELSE password
    END as password,
    timeout,
    protocol, 
    status,
    enabled as is_enabled,
    firmware_version, 
    serial_number,
    last_seen, 
    created_at, 
    updated_at
FROM devices;

-- Drop old table
DROP TABLE devices;

-- Rename new table
ALTER TABLE devices_new RENAME TO devices;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_devices_address ON devices(address);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);

COMMIT;
