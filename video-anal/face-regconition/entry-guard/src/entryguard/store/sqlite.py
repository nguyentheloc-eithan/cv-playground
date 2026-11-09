from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from ..core.types import Embedding, Person

SCHEMA = """
CREATE TABLE IF NOT EXISTS person (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, attributes TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'active', created_at REAL NOT NULL DEFAULT (strftime('%s','now')));
CREATE TABLE IF NOT EXISTS embedding (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  person_id TEXT NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  space_id TEXT NOT NULL, dim INTEGER NOT NULL, vec BLOB NOT NULL);
CREATE INDEX IF NOT EXISTS embedding_space ON embedding(space_id);
CREATE TABLE IF NOT EXISTS event (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, camera_id TEXT NOT NULL,
  decision TEXT NOT NULL, person_id TEXT, score REAL NOT NULL);
CREATE INDEX IF NOT EXISTS event_ts ON event(ts DESC);
"""


class SqliteStore:
    def __init__(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)

    def add_person(self, person: Person) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO person(id,name,attributes,status) VALUES(?,?,?,?)",
                (person.id, person.name, json.dumps(person.attributes), person.status))

    @staticmethod
    def _person(r) -> Person:
        return Person(id=r[0], name=r[1], attributes=json.loads(r[2]), status=r[3])

    def get_person(self, person_id: str) -> Person | None:
        r = self.db.execute("SELECT id,name,attributes,status FROM person WHERE id=?",
                            (person_id,)).fetchone()
        return self._person(r) if r else None

    def list_persons(self) -> list[Person]:
        rows = self.db.execute(
            "SELECT id,name,attributes,status FROM person ORDER BY created_at").fetchall()
        return [self._person(r) for r in rows]

    def set_status(self, person_id: str, status: str) -> None:
        with self.db:
            self.db.execute("UPDATE person SET status=? WHERE id=?", (status, person_id))

    def delete_person(self, person_id: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM person WHERE id=?", (person_id,))

    def add_embeddings(self, items: list[Embedding]) -> None:
        with self.db:
            self.db.executemany(
                "INSERT INTO embedding(person_id,space_id,dim,vec) VALUES(?,?,?,?)",
                [(e.person_id, e.space_id, len(e.vec),
                  np.asarray(e.vec, dtype=np.float32).tobytes()) for e in items])

    def embeddings(self, space_id: str) -> tuple[list[str], np.ndarray]:
        rows = self.db.execute(
            "SELECT e.person_id, e.vec FROM embedding e JOIN person p ON p.id=e.person_id "
            "WHERE e.space_id=? AND p.status='active'", (space_id,)).fetchall()
        if not rows:
            return [], np.zeros((0, 0), dtype=np.float32)
        return ([r[0] for r in rows],
                np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows]))

    def log_event(self, ts, camera_id, decision, person_id, score) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO event(ts,camera_id,decision,person_id,score) VALUES(?,?,?,?,?)",
                (ts, camera_id, decision, person_id, score))

    def list_events(self, limit: int = 50) -> list[dict]:
        rows = self.db.execute(
            "SELECT ts,camera_id,decision,person_id,score FROM event ORDER BY ts DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(zip(("ts", "camera_id", "decision", "person_id", "score"), r)) for r in rows]
