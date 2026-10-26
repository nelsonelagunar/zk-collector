-- Fix device_users schema: rename device_ip -> device_id (FK to devices.id)
-- Live databases have device_users with device_ip column from old migration 004
-- New schema expects device_id INTEGER REFERENCES devices(id)

BEGIN TRANSACTION;

-- Create new table with correct schema
CREATE TABLE device_users_new (
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

-- Copy data from old table to new table
-- Map device_ip to device_id via devices table
-- Live schema has: device_ip, user_id, name, privilege, group_id (INTEGER), user_role, synced_at, created_at, updated_at
-- Note: no password column in live schema
INSERT INTO device_users_new (
    id, device_id, user_id, name, privilege, password,
    group_id, user_role, created_at, updated_at
)
SELECT 
    du.id,
    d.id as device_id,
    du.user_id,
    du.name,
    du.privilege,
    NULL as password,
    CAST(du.group_id AS TEXT) as group_id,
    du.user_role,
    du.created_at,
    du.updated_at
FROM device_users du
JOIN devices d ON d.address = du.device_ip;

-- Drop old table
DROP TABLE device_users;

-- Rename new table
ALTER TABLE device_users_new RENAME TO device_users;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_device_users_device_id ON device_users(device_id);
CREATE INDEX IF NOT EXISTS idx_device_users_user_id ON device_users(user_id);

COMMIT;
