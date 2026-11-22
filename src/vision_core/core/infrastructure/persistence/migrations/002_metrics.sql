CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    value REAL NOT NULL,
    timestamp_utc REAL NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_metrics_session ON metrics(session_id);
