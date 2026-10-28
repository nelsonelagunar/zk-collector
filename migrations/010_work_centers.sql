-- Migration 010: Entidad centro de trabajo (CT-1, MYK-410 / MYK-427).
-- Crea tabla work_centers y añade FK device.work_center_id.
-- target: webgui.db

-- 1) Tabla de centros de trabajo
CREATE TABLE IF NOT EXISTS work_centers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    rfc_pattern TEXT,
    imss_registro_patronal TEXT,
    direccion TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Índice para búsqueda por nombre
CREATE INDEX IF NOT EXISTS idx_work_centers_nombre ON work_centers(nombre);

-- 2) FK en devices -> work_centers (columna nullable para no romper dispositivos existentes)
ALTER TABLE devices ADD COLUMN work_center_id INTEGER;

-- 3) Índice para la FK
CREATE INDEX IF NOT EXISTS idx_devices_work_center_id ON devices(work_center_id);
