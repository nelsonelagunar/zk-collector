-- Add missing device columns for auto-discovery support
-- Adds: protocol, mac, model, firmware_version, serial_number, location, zone

-- Add protocol column
ALTER TABLE devices ADD COLUMN protocol TEXT DEFAULT 'tcp' CHECK (protocol IN ('tcp', 'udp'));

-- Add mac address column
ALTER TABLE devices ADD COLUMN mac TEXT DEFAULT '';

-- Add model column
ALTER TABLE devices ADD COLUMN model TEXT DEFAULT '';

-- Add firmware_version column
ALTER TABLE devices ADD COLUMN firmware_version TEXT DEFAULT '';

-- Add serial_number column
ALTER TABLE devices ADD COLUMN serial_number TEXT DEFAULT '';

-- Add location column
ALTER TABLE devices ADD COLUMN location TEXT DEFAULT '';

-- Add zone column
ALTER TABLE devices ADD COLUMN zone TEXT DEFAULT '';

-- Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_devices_mac ON devices(mac);
CREATE INDEX IF NOT EXISTS idx_devices_model ON devices(model);
CREATE INDEX IF NOT EXISTS idx_devices_protocol ON devices(protocol);