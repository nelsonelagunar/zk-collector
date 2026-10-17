-- Create medical_leaves table (MYK-238)
CREATE TABLE IF NOT EXISTS medical_leaves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    leave_type TEXT NOT NULL CHECK(leave_type IN ('enfermedad','maternidad','accidente','otro')),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    days INTEGER NOT NULL,
    doctor_name TEXT,
    document_ref TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','cancelled')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    CHECK (end_date >= start_date)
);

-- Indexes per spec
CREATE INDEX IF NOT EXISTS idx_medical_leaves_employee_start ON medical_leaves(employee_id, start_date);
