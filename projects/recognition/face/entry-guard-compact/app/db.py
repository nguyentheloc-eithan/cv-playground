"""Step 3: save people and their face vectors in a SQLite file (no server needed).

Two tables:
    person  : id, name, extra fields as JSON (e.g. {"unit_no": "302"})
    vector  : one row per registered photo, linked to a person
"""
import json
import sqlite3

import numpy as np


class Database:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys = ON")  # deleting a person deletes their vectors
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS person (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                fields TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS vector (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
                data BLOB NOT NULL);
        """)

    def add_person(self, name, fields, vectors):
        with self.db:  # one transaction: person and vectors are saved together or not at all
            cur = self.db.execute(
                "INSERT INTO person(name, fields) VALUES (?, ?)", (name, json.dumps(fields)))
            for v in vectors:
                self.db.execute("INSERT INTO vector(person_id, data) VALUES (?, ?)",
                                (cur.lastrowid, v.astype(np.float32).tobytes()))
            return cur.lastrowid

    def list_people(self):
        rows = self.db.execute("SELECT id, name, fields FROM person ORDER BY id").fetchall()
        return [{"id": r[0], "name": r[1], "fields": json.loads(r[2])} for r in rows]

    def get_person(self, person_id):
        r = self.db.execute("SELECT id, name, fields FROM person WHERE id = ?",
                            (person_id,)).fetchone()
        return {"id": r[0], "name": r[1], "fields": json.loads(r[2])} if r else None

    def delete_person(self, person_id):
        with self.db:
            self.db.execute("DELETE FROM person WHERE id = ?", (person_id,))

    def all_vectors(self):
        """Return [(person_id, vector), ...] for every registered photo."""
        rows = self.db.execute("SELECT person_id, data FROM vector").fetchall()
        return [(pid, np.frombuffer(data, dtype=np.float32)) for pid, data in rows]
