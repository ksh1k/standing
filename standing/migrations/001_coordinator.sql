-- Coordinator agent database schema (Phase 1)
-- Students table MUST NOT include availability (constraint 3).
-- Sessions MUST NOT include per-member attended columns (constraint 4).
-- No residence / address / dorm fields anywhere (constraint 2).

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY NOT NULL,
    year TEXT NOT NULL CHECK (year IN ('freshman', 'sophomore', 'junior', 'senior', 'grad')),
    courses TEXT NOT NULL DEFAULT '[]',  -- JSON array of normalized course codes
    preferred_group_size INTEGER NOT NULL CHECK (preferred_group_size BETWEEN 4 AND 6),
    preferred_zones TEXT NOT NULL DEFAULT '[]',  -- JSON array of public CampusZone values
    study_style TEXT NOT NULL CHECK (study_style IN ('quiet_parallel', 'discussion', 'problem_drilling')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS groups (
    group_id TEXT PRIMARY KEY NOT NULL,
    course_code TEXT NOT NULL,
    member_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array of student_id
    scheduled_slot INTEGER,                 -- legal meeting start index 0–209 conceptually; nullable until scheduled
    zone TEXT,                              -- CampusZone value; public places only
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'forming' CHECK (status IN ('forming', 'active', 'disbanded'))
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY NOT NULL,
    group_id TEXT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    scheduled_datetime TEXT NOT NULL,
    location TEXT NOT NULL,  -- public campus zone / place label only; never residential
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
    -- NO per-member attended columns (constraint 4)
);

CREATE INDEX IF NOT EXISTS idx_groups_course ON groups(course_code);
CREATE INDEX IF NOT EXISTS idx_sessions_group ON sessions(group_id);
