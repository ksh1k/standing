-- Member agent database schema (Phase 1)
-- Holds full student profile including availability bitmap and private attendance.
-- NEVER share availability or individual attendance outside this DB.

CREATE TABLE IF NOT EXISTS student_profile (
    student_id TEXT PRIMARY KEY NOT NULL,
    display_name TEXT NOT NULL,
    year TEXT NOT NULL CHECK (year IN ('freshman', 'sophomore', 'junior', 'senior', 'grad')),
    courses TEXT NOT NULL DEFAULT '[]',  -- JSON array of normalized course codes
    availability TEXT NOT NULL,         -- 224-slot bitmap (ONLY in member DB)
    preferred_group_size INTEGER NOT NULL CHECK (preferred_group_size BETWEEN 4 AND 6),
    preferred_zones TEXT NOT NULL DEFAULT '[]',  -- JSON array of CampusZone values
    study_style TEXT NOT NULL CHECK (study_style IN ('quiet_parallel', 'discussion', 'problem_drilling')),
    time_of_day_preference TEXT NOT NULL DEFAULT '{"morning":1.0,"afternoon":1.0,"evening":1.0}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Per-member attendance: visible only to that student (constraint 4)
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL REFERENCES student_profile(student_id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    attended INTEGER NOT NULL CHECK (attended IN (0, 1)),
    recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (student_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);
CREATE INDEX IF NOT EXISTS idx_attendance_session ON attendance(session_id);
