"""Migration des bases créées avant l'inscription par nom d'utilisateur."""

from __future__ import annotations

import sqlite3

from sqlalchemy import create_engine

from app import db as db_module

OLD_SCHEMA = """
CREATE TABLE users (
    id VARCHAR(32) PRIMARY KEY, email VARCHAR(255) NOT NULL UNIQUE, password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(120), email_verified BOOLEAN, plan VARCHAR(20), plan_renews_at DATETIME,
    stripe_customer_id VARCHAR(64), stripe_subscription_id VARCHAR(64), prefs JSON,
    credits_period VARCHAR(7), credits_used INTEGER, token_version INTEGER, created_at DATETIME
);
CREATE TABLE projects (
    id VARCHAR(32) PRIMARY KEY, user_id VARCHAR(32) REFERENCES users(id) ON DELETE CASCADE, title VARCHAR(200)
);
INSERT INTO users VALUES ('u1', 'Awa@Example.com', 'hash1', 'Awa', 1, 'pro', NULL, NULL, NULL, '{}', '2026-10', 1, 0, '2026-10-01');
INSERT INTO users VALUES ('u2', 'awa@other.com', 'hash2', '', 0, 'free', NULL, NULL, NULL, '{}', '', 0, 0, '2026-10-02');
INSERT INTO projects VALUES ('p1', 'u1', 'Montage');
"""


def test_old_database_keeps_accounts_and_projects(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.executescript(OLD_SCHEMA)
    raw.close()

    engine = create_engine(f"sqlite:///{path.as_posix()}")
    monkeypatch.setattr(db_module, "engine", engine)
    db_module._migrate_users()

    check = sqlite3.connect(path)
    rows = check.execute("SELECT id, username, email, password_hash, plan FROM users ORDER BY id").fetchall()
    assert rows == [
        ("u1", "awa", "Awa@Example.com", "hash1", "pro"),
        ("u2", "awa2", "awa@other.com", "hash2", "free"),
    ]
    assert check.execute("SELECT id, user_id FROM projects").fetchall() == [("p1", "u1")]
    nullable = {r[1]: r[3] for r in check.execute("PRAGMA table_info(users)")}
    assert nullable["email"] == 0 and nullable["password_hash"] == 0
    check.close()

    db_module._migrate_users()  # idempotente
