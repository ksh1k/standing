-- Course wait pools for multi-student product MVP (Phase 8).
-- Availability never stored here — member DB only.

CREATE TABLE IF NOT EXISTS course_pool (
    course_code TEXT NOT NULL,
    student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'waiting'
        CHECK (status IN ('waiting', 'matched', 'left')),
    PRIMARY KEY (course_code, student_id)
);

CREATE INDEX IF NOT EXISTS idx_course_pool_waiting
    ON course_pool(course_code, status);
