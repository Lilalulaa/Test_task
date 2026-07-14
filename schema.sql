DROP TABLE IF EXISTS documents;

CREATE TABLE documents (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source TEXT NOT NULL,

    snapshot_date DATE NOT NULL,

    organization TEXT NOT NULL,

    sales_department TEXT,

    department TEXT NOT NULL,

    team TEXT,

    manager TEXT,

    contractor TEXT,

    contract TEXT,

    document_name TEXT NOT NULL,

    realization_date DATE,

    plan_payment_date DATE,

    days_to_plan INTEGER,

    amount REAL NOT NULL,

    debt_total REAL NOT NULL,

    debt_share REAL NOT NULL,

    overdue REAL NOT NULL,

    days_overdue INTEGER,

    our_debt REAL NOT NULL
);

CREATE INDEX idx_snapshot
ON documents(snapshot_date);

CREATE INDEX idx_department
ON documents(department);

CREATE INDEX idx_manager
ON documents(manager);

CREATE INDEX idx_contractor
ON documents(contractor);