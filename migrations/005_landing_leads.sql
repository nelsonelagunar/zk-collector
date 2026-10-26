-- Landing page contact leads (MYK-409): public /landing contact-form submissions.
-- No SMTP required: leads are stored for the operator to follow up later.

CREATE TABLE IF NOT EXISTS landing_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT,
    phone TEXT,
    message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_landing_leads_created_at ON landing_leads(created_at);
CREATE INDEX IF NOT EXISTS idx_landing_leads_email ON landing_leads(email);
