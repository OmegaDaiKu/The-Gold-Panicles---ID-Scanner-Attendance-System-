-- The Gold Panicles Local QR Attendance System - Database DDL Schema

PRAGMA foreign_keys = ON;

-- 1. Staff Directory Table
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id_no TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    designation TEXT NOT NULL DEFAULT 'Staffer',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

-- 2. Staff Attendance Sessions Table (Independent Timestamps)
CREATE TABLE IF NOT EXISTS attendance_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('Duty', 'Visit')),
    time_in TEXT NOT NULL,
    time_out TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'COMPLETED', 'OVERDUE', 'RESOLVED')),
    resolution_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE RESTRICT
);

DROP INDEX IF EXISTS idx_unique_open_staff_session;
DROP INDEX IF EXISTS idx_unique_open_staff_session_per_day;
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_open_staff_session
ON attendance_sessions (staff_id)
WHERE status = 'OPEN';

-- 3. Guest Visitor Visits Table (Independent Timestamps)
CREATE TABLE IF NOT EXISTS visitor_visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id_no TEXT NOT NULL,
    visitor_name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Visit' CHECK(category IN ('Duty', 'Visit')),
    time_in TEXT NOT NULL,
    time_out TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'COMPLETED', 'OVERDUE', 'RESOLVED')),
    resolution_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

DROP INDEX IF EXISTS idx_unique_open_visitor_visit;
DROP INDEX IF EXISTS idx_unique_open_visitor_visit_per_day;
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_open_visitor_visit
ON visitor_visits (student_id_no)
WHERE status = 'OPEN';

-- 4. Administrator Accounts Table
CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('MASTER_ADMIN', 'STAFF_ADMIN')),
    is_active INTEGER NOT NULL DEFAULT 1,
    last_login TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

-- 5. Audit Log Trail Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER,
    action_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    old_values_json TEXT,
    new_values_json TEXT,
    reason TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (admin_id) REFERENCES admin_users(id) ON DELETE RESTRICT
);