-- Coordinator negotiation state (Phase 2).
-- Leakage-safe: per-candidate aggregate accept_count only.
-- NO per-member per-candidate verdict table.

CREATE TABLE IF NOT EXISTS negotiation_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negotiation_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    proposed_slot INTEGER,              -- week-bitmap start index; NULL for init row
    accept_count INTEGER NOT NULL DEFAULT 0,
    outcome TEXT NOT NULL,              -- init | confirmed | rejected | no_unanimous
    budget INTEGER NOT NULL DEFAULT 40,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS negotiation_candidates (
    negotiation_id TEXT NOT NULL,
    slot INTEGER NOT NULL,              -- week-bitmap legal start index
    accept_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'rejected', 'confirmed')),
    score REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (negotiation_id, slot)
);

CREATE INDEX IF NOT EXISTS idx_neg_rounds_neg ON negotiation_rounds(negotiation_id);
CREATE INDEX IF NOT EXISTS idx_neg_cand_neg ON negotiation_candidates(negotiation_id);
