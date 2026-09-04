-- Coordinator persistence (Phase 5): aggregates, exams, drift, merge flags.
-- No per-student attendance identity on coordinator (constraint 4).

CREATE TABLE IF NOT EXISTS session_aggregates (
    session_id TEXT PRIMARY KEY NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    attended_count INTEGER NOT NULL CHECK (attended_count >= 0),
    member_total INTEGER NOT NULL CHECK (member_total > 0)
);

CREATE TABLE IF NOT EXISTS session_kinds (
    session_id TEXT PRIMARY KEY NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'regular'
        CHECK (kind IN ('regular', 'exam_season'))
);

CREATE TABLE IF NOT EXISTS exam_dates (
    exam_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL,
    exam_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drift_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    triggered_at TEXT NOT NULL,
    consecutive_low INTEGER NOT NULL,
    new_slot INTEGER,
    status TEXT NOT NULL CHECK (status IN ('triggered', 'renegotiated', 'failed'))
);

CREATE TABLE IF NOT EXISTS merge_flags (
    flag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    course_code TEXT NOT NULL,
    active_member_count INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (group_id)
);

CREATE INDEX IF NOT EXISTS idx_exam_dates_course ON exam_dates(course_code);
CREATE INDEX IF NOT EXISTS idx_drift_group ON drift_events(group_id);
