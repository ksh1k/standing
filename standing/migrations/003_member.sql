-- Member persistence (Phase 5): local sessions + notifications only (no email).

CREATE TABLE IF NOT EXISTS local_sessions (
    session_id TEXT PRIMARY KEY NOT NULL,
    group_id TEXT,
    scheduled_datetime TEXT NOT NULL,
    location TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL REFERENCES student_profile(student_id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('reminder', 'dormancy_checkin')),
    body TEXT NOT NULL,
    session_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (student_id, kind, session_id)
);

CREATE INDEX IF NOT EXISTS idx_notifications_student ON notifications(student_id);
CREATE INDEX IF NOT EXISTS idx_local_sessions_dt ON local_sessions(scheduled_datetime);
