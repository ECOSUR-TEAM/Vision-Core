CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at_utc REAL NOT NULL,
    finished_at_utc REAL,
    camera_id TEXT,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS persons (
    person_id TEXT PRIMARY KEY,
    first_seen_utc REAL NOT NULL,
    last_seen_utc REAL NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS zones (
    name TEXT PRIMARY KEY,
    points_json TEXT NOT NULL,
    updated_at_utc REAL NOT NULL,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    person_id TEXT NOT NULL,
    session_id TEXT,
    timestamp_utc REAL NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_events_person_timestamp ON events(person_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);

CREATE TABLE IF NOT EXISTS zone_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT,
    person_id TEXT NOT NULL,
    zone TEXT NOT NULL,
    position_json TEXT NOT NULL,
    timestamp_utc REAL NOT NULL,
    created_at_utc TEXT NOT NULL,
    UNIQUE (event_id)
);

CREATE INDEX IF NOT EXISTS idx_zone_observations_person_timestamp
    ON zone_observations(person_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_zone_observations_timestamp ON zone_observations(timestamp_utc);

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    person_id TEXT NOT NULL,
    bbox_json TEXT NOT NULL,
    timestamp_utc REAL NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tracks_session_timestamp ON tracks(session_id, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_tracks_timestamp ON tracks(timestamp_utc);

CREATE TABLE IF NOT EXISTS identity_gallery (
    person_id TEXT PRIMARY KEY,
    embedding_json TEXT NOT NULL,
    last_seen_at_utc REAL NOT NULL,
    created_at_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_identity_last_seen ON identity_gallery(last_seen_at_utc);
