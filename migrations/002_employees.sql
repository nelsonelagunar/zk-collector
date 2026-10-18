-- Create employees table (MYK-220)
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    department TEXT,
    position TEXT,
    hire_date DATETIME,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Link employees to device users (many-to-many via serial/user_id)
CREATE TABLE IF NOT EXISTS employee_device_links (
    employee_id INTEGER NOT NULL,
    device_serial TEXT NOT NULL,
    device_user_id TEXT NOT NULL,
    PRIMARY KEY (employee_id, device_serial, device_user_id),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

-- Indexes per spec
CREATE INDEX IF NOT EXISTS idx_employees_code ON employees(employee_code);
CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);
CREATE INDEX IF NOT EXISTS idx_employee_device_links_serial ON employee_device_links(device_serial);
CREATE INDEX IF NOT EXISTS idx_employee_device_links_user ON employee_device_links(device_user_id);
