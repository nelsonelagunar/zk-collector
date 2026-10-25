-- Razon social (empresas) y su vinculacion con relojes checadores (MYK-405, MYK-403 items 3-4)
-- Numerada 008: 005_alerts (MYK-227), 006_alert_default_rules y 007_demo_seed ya ocupan 005-007.
-- Idempotente (IF NOT EXISTS) como migration 002: safe re-aplicar sobre DB existente.

-- Empresas / razones sociales del grupo que opera los relojes
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    razon_social TEXT NOT NULL,
    rfc TEXT,
    imss_registro_patronal TEXT,
    domicilio_fiscal TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Vinculo empresa <-> reloj checador: 1:N hoy (UNIQUE device_serial), puente relajable a N:M.
-- Referencia por device_serial TEXT (convencion de employee_device_links) porque
-- devices.serial_number es nullable y sin indice unico.
CREATE TABLE IF NOT EXISTS company_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    device_serial TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
-- RFC es opcional: indice unico parcial solo cuando tiene valor (NULL/'' repetibles).
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_rfc ON companies(rfc) WHERE rfc IS NOT NULL AND rfc <> '';
CREATE INDEX IF NOT EXISTS idx_company_devices_company_id ON company_devices(company_id);

-- Backfill una sola vez: si ya existia company_name en system_config (p.ej. seed demo 007),
-- materializa la primera razon social. NO-op si no hay company_name o si ya hay empresas.
INSERT INTO companies (razon_social)
SELECT value
FROM system_config
WHERE key = 'company_name'
  AND value IS NOT NULL
  AND TRIM(value) <> ''
  AND NOT EXISTS (SELECT 1 FROM companies);
