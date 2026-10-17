-- Employees (colaboradores) module - base schema for HR module (Sprint 3, MYK-220)
-- Modela un colaborador real; device_users solo mapea user_id -> nombre leido del reloj.

-- Employees table
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT UNIQUE NOT NULL,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    department TEXT,
    position TEXT,
    hire_date DATE,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Employee <-> device badge links
-- Un colaborador puede tener N badges/enlaces a devices (altas/bajas/cambios de reloj).
CREATE TABLE IF NOT EXISTS employee_device_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    device_serial TEXT NOT NULL,
    device_user_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    UNIQUE (device_serial, device_user_id)
);

-- Indexes
-- employee_code ya tiene un indice unico implicito por la restriccion UNIQUE.
CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);
CREATE INDEX IF NOT EXISTS idx_employee_device_links_employee_id ON employee_device_links(employee_id);
