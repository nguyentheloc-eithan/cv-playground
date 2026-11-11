"""Step 3: everything that is saved lives in one SQLite file (no database server needed).

Tables
    user    : who can log in (username, password hash, role admin|viewer)
    person  : an enrolled person (name, custom fields, status, consent record)
    photo   : one row per saved enrollment photo (file kept on disk)
    vector  : one row per photo, the 128 numbers used for matching
    event   : one row per finished recognition (used by the camera, see camera.py)
    audit   : who did what and when

All methods take a lock, so the web server can call them from many threads safely.
"""
import hashlib
import json
import shutil
import sqlite3
import threading
import time

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    pw_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'viewer', 'resident')),
    active INTEGER NOT NULL DEFAULT 1,
    epoch INTEGER NOT NULL DEFAULT 0,
    pin_hash TEXT,
    pin_enabled INTEGER NOT NULL DEFAULT 0,
    face_enabled INTEGER NOT NULL DEFAULT 0,
    last_method TEXT,
    face_login INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS user_face (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
    data BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS step_up_grant (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    method TEXT NOT NULL,
    expires REAL NOT NULL,
    used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS person (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    person_type TEXT NOT NULL DEFAULT 'resident',
    unit TEXT NOT NULL DEFAULT '',
    valid_from REAL,
    valid_until REAL,
    notes TEXT NOT NULL DEFAULT '',
    watch TEXT NOT NULL DEFAULT '{}',
    fields TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    consent_at REAL,
    consent_version TEXT,
    created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS photo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    filename TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vector (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    data BLOB NOT NULL,
    photo_id INTEGER);
CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    camera_id TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    decision TEXT NOT NULL,
    person_id INTEGER REFERENCES person(id) ON DELETE SET NULL,
    score REAL NOT NULL,
    snapshot TEXT,
    reviewed INTEGER NOT NULL DEFAULT 0,
    access TEXT,
    reason TEXT NOT NULL DEFAULT '',
    alert TEXT);
CREATE TABLE IF NOT EXISTS alert (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    last_ts REAL NOT NULL,
    level TEXT NOT NULL,
    confidence TEXT NOT NULL,
    person_id INTEGER REFERENCES person(id) ON DELETE SET NULL,
    event_id INTEGER REFERENCES event(id) ON DELETE SET NULL,
    camera_id TEXT NOT NULL,
    score REAL NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'open',
    ack_by TEXT,
    ack_at REAL,
    ack_note TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS alert_status ON alert(status, ts DESC);
CREATE INDEX IF NOT EXISTS event_ts ON event(ts DESC);
CREATE TABLE IF NOT EXISTS camera (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL CHECK (kind IN ('browser', 'rtsp')),
    direction TEXT NOT NULL DEFAULT 'in',
    host TEXT NOT NULL DEFAULT '',
    port INTEGER NOT NULL DEFAULT 554,
    path TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    password TEXT NOT NULL DEFAULT '',
    transport TEXT NOT NULL DEFAULT 'tcp',
    fps REAL NOT NULL DEFAULT 10,
    enabled INTEGER NOT NULL DEFAULT 1,
    builtin INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS camera_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL DEFAULT '',
    port INTEGER NOT NULL DEFAULT 554,
    username TEXT NOT NULL DEFAULT '',
    transport TEXT NOT NULL DEFAULT 'tcp',
    note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '{}',
    prev_hash TEXT,
    hash TEXT);
CREATE TABLE IF NOT EXISTS login_attempt (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    username TEXT NOT NULL,
    ip TEXT NOT NULL DEFAULT '',
    success INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS login_attempt_ts ON login_attempt(ts);
"""


def _locked(method):
    """Run a Database method while holding the lock."""
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return wrapper


class Database:
    def __init__(self, path, photos_dir, snapshots_dir=None, id_prefix="EG"):
        path.parent.mkdir(parents=True, exist_ok=True)
        photos_dir.mkdir(parents=True, exist_ok=True)
        self.photos_dir = photos_dir
        self.snapshots_dir = snapshots_dir or photos_dir.parent / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.id_prefix = id_prefix
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA foreign_keys = ON")  # deleting a person deletes their rows
        self.db.executescript(SCHEMA)
        self._upgrade_schema()
        self._seed_laptop_camera()

    def _upgrade_schema(self):
        """Databases made by earlier versions have fewer columns. Add what is missing."""
        wanted = {
            "person": {"status": "TEXT NOT NULL DEFAULT 'active'", "consent_at": "REAL", "consent_version": "TEXT",
                       "created_at": "REAL NOT NULL DEFAULT 0", "code": "TEXT", "phone": "TEXT NOT NULL DEFAULT ''",
                       "person_type": "TEXT NOT NULL DEFAULT 'resident'", "unit": "TEXT NOT NULL DEFAULT ''",
                       "valid_from": "REAL", "valid_until": "REAL", "notes": "TEXT NOT NULL DEFAULT ''",
                       "watch": "TEXT NOT NULL DEFAULT '{}'"},
            "vector": {"photo_id": "INTEGER"},
            "event": {"access": "TEXT", "reason": "TEXT NOT NULL DEFAULT ''", "alert": "TEXT"},
            "audit": {"prev_hash": "TEXT", "hash": "TEXT"},
            "user": {"epoch": "INTEGER NOT NULL DEFAULT 0", "pin_hash": "TEXT", "pin_enabled": "INTEGER NOT NULL DEFAULT 0",
                     "face_enabled": "INTEGER NOT NULL DEFAULT 0", "last_method": "TEXT",
                     "face_login": "INTEGER NOT NULL DEFAULT 0"},
        }
        with self.db:
            for table, columns in wanted.items():
                have = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})")}
                for column, definition in columns.items():
                    if column not in have:
                        self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            # people registered before IDs existed get one now
            for (person_id,) in self.db.execute("SELECT id FROM person WHERE code IS NULL").fetchall():
                self.db.execute("UPDATE person SET code = ? WHERE id = ?", (self._code(person_id), person_id))
            self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS person_code ON person(code)")
        self._link_old_vectors_to_photos()
        self._allow_resident_role()

    def _link_old_vectors_to_photos(self):
        """Vectors saved before photo management have no photo_id. Photos and vectors were always saved in the same
        order, so when a person has as many of each, pair them up (this lets single photos be removed later)."""
        with self.db:
            for (person_id,) in self.db.execute("SELECT DISTINCT person_id FROM vector WHERE photo_id IS NULL").fetchall():
                photos = [r[0] for r in self.db.execute("SELECT id FROM photo WHERE person_id = ? ORDER BY id", (person_id,))]
                vectors = [r[0] for r in self.db.execute("SELECT id FROM vector WHERE person_id = ? ORDER BY id", (person_id,))]
                if len(photos) == len(vectors):
                    for photo_id, vector_id in zip(photos, vectors):
                        self.db.execute("UPDATE vector SET photo_id = ? WHERE id = ?", (photo_id, vector_id))

    def _allow_resident_role(self):
        """Older databases only allow the roles admin/viewer in a CHECK rule. SQLite cannot alter a
        rule, so rebuild the (small) user table once when it is missing 'resident'."""
        sql = self.db.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'user'").fetchone()[0]
        if "'resident'" in sql:
            return
        # Safe order for SQLite: build the new table, copy, drop the old one, rename the new one.
        # (Renaming the OLD table first would rewrite other tables' foreign keys to point at it.)
        # Foreign keys are paused so that dropping the old table cannot cascade into user_face.
        self.db.execute("PRAGMA foreign_keys = OFF")
        try:
            with self.db:
                self.db.execute("""CREATE TABLE user_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, pw_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'viewer', 'resident')),
                    active INTEGER NOT NULL DEFAULT 1, epoch INTEGER NOT NULL DEFAULT 0, pin_hash TEXT,
                    pin_enabled INTEGER NOT NULL DEFAULT 0, face_enabled INTEGER NOT NULL DEFAULT 0, last_method TEXT,
                    face_login INTEGER NOT NULL DEFAULT 0)""")
                have = {row[1] for row in self.db.execute("PRAGMA table_info(user)")}
                columns = ", ".join(c for c in ("id", "username", "pw_hash", "role", "active", "epoch", "pin_hash",
                                                "pin_enabled", "face_enabled", "last_method", "face_login") if c in have)
                self.db.execute(f"INSERT INTO user_new({columns}) SELECT {columns} FROM user")
                self.db.execute("DROP TABLE user")
                self.db.execute("ALTER TABLE user_new RENAME TO user")
        finally:
            self.db.execute("PRAGMA foreign_keys = ON")

    def _code(self, person_id):
        """The automatic, human-friendly ID of a person, for example EG-00042."""
        return f"{self.id_prefix}-{person_id:05d}"

    def _seed_laptop_camera(self):
        """The laptop (browser) camera always exists, so the console works with no IP camera."""
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO camera(id, name, location, kind, builtin, created_at) "
                "VALUES ('laptop', 'Laptop camera', 'This computer', 'browser', 1, ?)", (time.time(),))

    # ---------------------------------------------------------------- cameras
    _CAMERA_COLUMNS = ("id, name, location, kind, direction, host, port, path, username, password, "
                       "transport, fps, enabled, builtin")

    @staticmethod
    def _camera(r):
        keys = ("id", "name", "location", "kind", "direction", "host", "port", "path", "username",
                "password", "transport", "fps", "enabled", "builtin")
        cam = dict(zip(keys, r))
        cam["enabled"], cam["builtin"] = bool(cam["enabled"]), bool(cam["builtin"])
        return cam

    @_locked
    def list_cameras(self):
        rows = self.db.execute(f"SELECT {self._CAMERA_COLUMNS} FROM camera "
                               "ORDER BY builtin DESC, created_at").fetchall()
        return [self._camera(r) for r in rows]

    @_locked
    def get_camera(self, camera_id):
        r = self.db.execute(f"SELECT {self._CAMERA_COLUMNS} FROM camera WHERE id = ?",
                            (camera_id,)).fetchone()
        return self._camera(r) if r else None

    @_locked
    def add_camera(self, camera_id, data):
        with self.db:
            self.db.execute(
                "INSERT INTO camera(id, name, location, kind, direction, host, port, path, username, "
                "password, transport, fps, enabled, created_at) "
                "VALUES (:id, :name, :location, 'rtsp', :direction, :host, :port, :path, :username, "
                ":password, :transport, :fps, :enabled, :created_at)",
                {**data, "id": camera_id, "created_at": time.time()})

    @_locked
    def update_camera(self, camera_id, data):
        if not data:
            return
        columns = ", ".join(f"{key} = :{key}" for key in data)
        with self.db:
            self.db.execute(f"UPDATE camera SET {columns} WHERE id = :id", {**data, "id": camera_id})

    @_locked
    def delete_camera(self, camera_id):
        with self.db:
            self.db.execute("DELETE FROM camera WHERE id = ? AND builtin = 0", (camera_id,))

    # ------------------------------------------------- camera templates (user made)
    @_locked
    def list_templates(self):
        rows = self.db.execute("SELECT id, name, path, port, username, transport, note "
                               "FROM camera_template ORDER BY name").fetchall()
        return [dict(zip(("id", "name", "path", "port", "username", "transport", "note"), r)) for r in rows]

    @_locked
    def save_template(self, name, path, port, username, transport, note=""):
        """Create or replace a template with this name."""
        with self.db:
            self.db.execute(
                "INSERT INTO camera_template(name, path, port, username, transport, note) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET path = excluded.path, "
                "port = excluded.port, username = excluded.username, transport = excluded.transport, "
                "note = excluded.note", (name, path, port, username, transport, note))

    @_locked
    def delete_template(self, template_id):
        with self.db:
            self.db.execute("DELETE FROM camera_template WHERE id = ?", (template_id,))

    # ------------------------------------------------------------------ users
    @_locked
    def add_user(self, username, pw_hash, role):
        with self.db:
            cur = self.db.execute("INSERT INTO user(username, pw_hash, role) VALUES (?, ?, ?)",
                                  (username, pw_hash, role))
        return cur.lastrowid

    _USER_COLUMNS = "id, username, pw_hash, role, active, epoch"

    @staticmethod
    def _user(r):
        return {"id": r[0], "username": r[1], "pw_hash": r[2], "role": r[3], "active": bool(r[4]), "epoch": r[5]}

    @_locked
    def get_user(self, username=None, user_id=None):
        if username is not None:
            r = self.db.execute(f"SELECT {self._USER_COLUMNS} FROM user WHERE username = ?", (username,)).fetchone()
        else:
            r = self.db.execute(f"SELECT {self._USER_COLUMNS} FROM user WHERE id = ?", (user_id,)).fetchone()
        return self._user(r) if r else None

    @_locked
    def list_users(self):
        rows = self.db.execute(f"SELECT {self._USER_COLUMNS} FROM user ORDER BY username").fetchall()
        return [self._user(r) for r in rows]

    @_locked
    def count_users(self):
        return self.db.execute("SELECT COUNT(*) FROM user").fetchone()[0]

    @_locked
    def count_active_admins(self):
        return self.db.execute("SELECT COUNT(*) FROM user WHERE role = 'admin' AND active = 1").fetchone()[0]

    @_locked
    def update_user(self, user_id, role=None, active=None, pw_hash=None):
        """Change a user. Changing the password, role or active flag also signs the user out
        everywhere (the session counter `epoch` goes up, which invalidates old session cookies)."""
        with self.db:
            if role is not None:
                self.db.execute("UPDATE user SET role = ? WHERE id = ?", (role, user_id))
            if active is not None:
                self.db.execute("UPDATE user SET active = ? WHERE id = ?", (1 if active else 0, user_id))
            if pw_hash is not None:
                self.db.execute("UPDATE user SET pw_hash = ? WHERE id = ?", (pw_hash, user_id))
            self.db.execute("UPDATE user SET epoch = epoch + 1 WHERE id = ?", (user_id,))

    # ------------------------------------------------- step-up security settings
    @_locked
    def get_security(self, user_id):
        r = self.db.execute("SELECT pin_hash, pin_enabled, face_enabled, last_method, face_login FROM user WHERE id = ?",
                            (user_id,)).fetchone()
        faces = self.db.execute("SELECT COUNT(*) FROM user_face WHERE user_id = ?", (user_id,)).fetchone()[0]
        return {"pin_set": bool(r[0]), "pin_enabled": bool(r[1] and r[0]), "face_enrolled": faces > 0,
                "face_enabled": bool(r[2] and faces), "last_method": r[3], "face_login": bool(r[4] and faces)}

    @_locked
    def get_pin_hash(self, user_id):
        return self.db.execute("SELECT pin_hash FROM user WHERE id = ?", (user_id,)).fetchone()[0]

    @_locked
    def set_pin(self, user_id, pin_hash):
        with self.db:
            self.db.execute("UPDATE user SET pin_hash = ?, pin_enabled = 1 WHERE id = ?", (pin_hash, user_id))

    @_locked
    def remove_pin(self, user_id):
        with self.db:
            self.db.execute("UPDATE user SET pin_hash = NULL, pin_enabled = 0 WHERE id = ?", (user_id,))

    @_locked
    def set_security_flags(self, user_id, pin_enabled=None, face_enabled=None, last_method=None, face_login=None):
        with self.db:
            if face_login is not None:
                self.db.execute("UPDATE user SET face_login = ? WHERE id = ?", (1 if face_login else 0, user_id))
            if pin_enabled is not None:
                self.db.execute("UPDATE user SET pin_enabled = ? WHERE id = ?", (1 if pin_enabled else 0, user_id))
            if face_enabled is not None:
                self.db.execute("UPDATE user SET face_enabled = ? WHERE id = ?", (1 if face_enabled else 0, user_id))
            if last_method is not None:
                self.db.execute("UPDATE user SET last_method = ? WHERE id = ?", (last_method, user_id))

    @_locked
    def save_face(self, user_id, vectors):
        """Replace the user's face template (a few vectors) and switch face confirmation on."""
        with self.db:
            self.db.execute("DELETE FROM user_face WHERE user_id = ?", (user_id,))
            for vector in vectors:
                self.db.execute("INSERT INTO user_face(user_id, data) VALUES (?, ?)",
                                (user_id, vector.astype(np.float32).tobytes()))
            self.db.execute("UPDATE user SET face_enabled = 1 WHERE id = ?", (user_id,))

    @_locked
    def delete_face(self, user_id):
        with self.db:
            self.db.execute("DELETE FROM user_face WHERE user_id = ?", (user_id,))
            self.db.execute("UPDATE user SET face_enabled = 0, face_login = 0 WHERE id = ?", (user_id,))

    @_locked
    def face_vectors(self, user_id):
        rows = self.db.execute("SELECT data FROM user_face WHERE user_id = ?", (user_id,)).fetchall()
        return [np.frombuffer(r[0], dtype=np.float32) for r in rows]

    @_locked
    def create_grant(self, token_hash, user_id, action, method, expires):
        with self.db:
            self.db.execute("DELETE FROM step_up_grant WHERE expires < ? OR used = 1", (time.time(),))
            self.db.execute("INSERT INTO step_up_grant(token_hash, user_id, action, method, expires) VALUES (?, ?, ?, ?, ?)",
                            (token_hash, user_id, action, method, expires))

    @_locked
    def consume_grant(self, token_hash, user_id, action):
        """Use a confirmation. True only once, only for the same user and action, only before it expires."""
        with self.db:
            cur = self.db.execute("UPDATE step_up_grant SET used = 1 WHERE token_hash = ? AND user_id = ? AND action = ? "
                                  "AND used = 0 AND expires > ?", (token_hash, user_id, action, time.time()))
        return cur.rowcount == 1

    # ---------------------------------------------------------- login attempts
    @_locked
    def record_login(self, username, ip, success):
        with self.db:
            self.db.execute("INSERT INTO login_attempt(ts, username, ip, success) VALUES (?, ?, ?, ?)",
                            (time.time(), username, ip, 1 if success else 0))

    @_locked
    def clear_failed_logins(self, username):
        """Forget the failed sign-in, face sign-in and confirmation attempts of one user (lockout reset)."""
        with self.db:
            cur = self.db.execute("DELETE FROM login_attempt WHERE username IN (?, ?, ?)",
                                  (username, f"face:{username}", f"stepup:{username}"))
        return cur.rowcount

    @_locked
    def failed_logins(self, username=None, ip=None, since=0):
        """Failed attempts since a time, counted after the last success for that username/ip."""
        column, value = ("username", username) if username is not None else ("ip", ip)
        last_ok = self.db.execute(f"SELECT COALESCE(MAX(ts), 0) FROM login_attempt WHERE {column} = ? AND success = 1",
                                  (value,)).fetchone()[0]
        rows = self.db.execute(f"SELECT ts FROM login_attempt WHERE {column} = ? AND success = 0 AND ts > ? "
                               "ORDER BY ts", (value, max(since, last_ok))).fetchall()
        return [r[0] for r in rows]

    # ----------------------------------------------------------------- people
    _CORE_FIELDS = ("name", "phone", "person_type", "unit", "valid_from", "valid_until", "notes", "watch")

    @_locked
    def add_person(self, profile, vectors, photos, consent_version):
        """Save a person, their vectors and their photo files. All or nothing.

        profile: name, phone, person_type, unit, valid_from, valid_until, notes, fields (a dict).
        vectors: list of numpy arrays;  photos: list of JPEG bytes (same length).
        """
        folder = None
        try:
            with self.db:  # one transaction
                cur = self.db.execute(
                    "INSERT INTO person(name, phone, person_type, unit, valid_from, valid_until, notes, watch, fields, "
                    "consent_at, consent_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (profile["name"], profile.get("phone", ""), profile.get("person_type", "resident"),
                     profile.get("unit", ""), profile.get("valid_from"), profile.get("valid_until"),
                     profile.get("notes", ""), json.dumps(profile.get("watch") or {}), json.dumps(profile.get("fields", {})),
                     time.time(), consent_version, time.time()))
                person_id = cur.lastrowid
                self.db.execute("UPDATE person SET code = ? WHERE id = ?", (self._code(person_id), person_id))
                folder = self.photos_dir / str(person_id)
                folder.mkdir(parents=True, exist_ok=True)
                for number, (vector, jpeg) in enumerate(zip(vectors, photos), start=1):
                    filename = f"{number}.jpg"
                    (folder / filename).write_bytes(jpeg)
                    photo_id = self.db.execute("INSERT INTO photo(person_id, filename) VALUES (?, ?)",
                                               (person_id, filename)).lastrowid
                    self.db.execute("INSERT INTO vector(person_id, data, photo_id) VALUES (?, ?, ?)",
                                    (person_id, vector.astype(np.float32).tobytes(), photo_id))
            return person_id
        except Exception:
            if folder:
                shutil.rmtree(folder, ignore_errors=True)  # do not leave photos without a person
            raise

    _PERSON_COLUMNS = ("id, code, name, phone, person_type, unit, valid_from, valid_until, notes, fields, "
                       "status, consent_at, consent_version, created_at, watch")

    @staticmethod
    def _person(r):
        keys = ("id", "code", "name", "phone", "person_type", "unit", "valid_from", "valid_until", "notes")
        person = dict(zip(keys, r[:9]))
        person.update(fields=json.loads(r[9]), status=r[10], consent_at=r[11], consent_version=r[12], created_at=r[13],
                      watch=json.loads(r[14] or "{}"))
        return person

    @_locked
    def list_people(self):
        rows = self.db.execute(f"SELECT {self._PERSON_COLUMNS} FROM person ORDER BY id").fetchall()
        return [self._person(r) for r in rows]

    @_locked
    def get_person(self, person_id):
        r = self.db.execute(f"SELECT {self._PERSON_COLUMNS} FROM person WHERE id = ?", (person_id,)).fetchone()
        return self._person(r) if r else None

    @_locked
    def find_person(self, phone=None, exclude_id=None):
        """A person with this phone number (used to stop double registration)."""
        # compare digits only, so "+0912345678" and "0912345678" count as the same number
        r = self.db.execute(f"SELECT {self._PERSON_COLUMNS} FROM person "
                            "WHERE phone != '' AND REPLACE(phone, '+', '') = ? AND id != ?",
                            ((phone or "").lstrip("+"), exclude_id or 0)).fetchone()
        return self._person(r) if r else None

    @_locked
    def known_units(self):
        rows = self.db.execute("SELECT DISTINCT unit FROM person WHERE unit != '' ORDER BY unit").fetchall()
        return [r[0] for r in rows]

    @_locked
    def update_person(self, person_id, fields=None, status=None, **core):
        """Change a person. `core` may hold name, phone, person_type, unit, valid_from, valid_until, notes."""
        unknown = set(core) - set(self._CORE_FIELDS)
        if unknown:
            raise ValueError(f"unknown person fields: {sorted(unknown)}")
        with self.db:
            for column, value in core.items():
                if column == "watch":
                    value = json.dumps(value or {})
                self.db.execute(f"UPDATE person SET {column} = ? WHERE id = ?", (value, person_id))
            if fields is not None:
                self.db.execute("UPDATE person SET fields = ? WHERE id = ?", (json.dumps(fields), person_id))
            if status is not None:
                self.db.execute("UPDATE person SET status = ? WHERE id = ?", (status, person_id))

    @_locked
    def delete_person(self, person_id):
        """Erase the person, their vectors and their photo files (FR-10)."""
        with self.db:
            self.db.execute("DELETE FROM person WHERE id = ?", (person_id,))
        shutil.rmtree(self.photos_dir / str(person_id), ignore_errors=True)

    @_locked
    def list_photos(self, person_id):
        rows = self.db.execute("SELECT id, filename FROM photo WHERE person_id = ? ORDER BY id", (person_id,)).fetchall()
        return [{"id": r[0], "filename": r[1]} for r in rows]

    @_locked
    def photo_path(self, person_id, photo_id):
        r = self.db.execute("SELECT filename FROM photo WHERE id = ? AND person_id = ?", (photo_id, person_id)).fetchone()
        return self.photos_dir / str(person_id) / r[0] if r else None

    @_locked
    def change_photos(self, person_id, vectors, jpegs, replace):
        """Add new photos for a person, and (replace=True) remove ALL the old ones. The new photos are written
        first, so a failure never leaves the person without a face. Returns how many photos the person has now."""
        folder = self.photos_dir / str(person_id)
        folder.mkdir(parents=True, exist_ok=True)
        old = self.list_photos(person_id) if replace else []
        written = []
        try:
            with self.db:
                for vector, jpeg in zip(vectors, jpegs):
                    filename = f"{int(time.time() * 1000)}-{len(written)}.jpg"
                    (folder / filename).write_bytes(jpeg)
                    written.append(filename)
                    photo_id = self.db.execute("INSERT INTO photo(person_id, filename) VALUES (?, ?)",
                                               (person_id, filename)).lastrowid
                    self.db.execute("INSERT INTO vector(person_id, data, photo_id) VALUES (?, ?, ?)",
                                    (person_id, vector.astype(np.float32).tobytes(), photo_id))
                for photo in old:
                    self.db.execute("DELETE FROM vector WHERE photo_id = ? OR (person_id = ? AND photo_id IS NULL)",
                                    (photo["id"], person_id))
                    self.db.execute("DELETE FROM photo WHERE id = ?", (photo["id"],))
        except Exception:
            for filename in written:
                (folder / filename).unlink(missing_ok=True)
            raise
        for photo in old:
            (folder / photo["filename"]).unlink(missing_ok=True)
        return len(self.list_photos(person_id))

    @_locked
    def delete_photo(self, person_id, photo_id):
        """Remove one photo and its face vector. The last photo cannot be removed. Returns True if removed."""
        photos = self.list_photos(person_id)
        target = next((p for p in photos if p["id"] == photo_id), None)
        if not target or len(photos) <= 1:
            return False
        with self.db:
            self.db.execute("DELETE FROM vector WHERE photo_id = ?", (photo_id,))
            self.db.execute("DELETE FROM photo WHERE id = ?", (photo_id,))
        (self.photos_dir / str(person_id) / target["filename"]).unlink(missing_ok=True)
        return True

    @_locked
    def first_photo(self, person_id):
        """Path of the first enrollment photo, or None."""
        r = self.db.execute("SELECT filename FROM photo WHERE person_id = ? ORDER BY id LIMIT 1",
                            (person_id,)).fetchone()
        return self.photos_dir / str(person_id) / r[0] if r else None

    @_locked
    def all_vectors(self):
        """[(person_id, vector), ...] for every photo of every registered person.

        Disabled and blocked people are included on purpose: they must be RECOGNISED so the system
        can say "access denied: account disabled" instead of treating them as a stranger."""
        rows = self.db.execute("SELECT person_id, data FROM vector").fetchall()
        return [(pid, np.frombuffer(data, dtype=np.float32)) for pid, data in rows]

    # ----------------------------------------------------------------- events
    @_locked
    def add_event(self, ts, camera_id, decision, person_id, score, snapshot_jpeg=None,
                  access=None, reason="", alert=None):
        """Record one finished scan. A cropped snapshot is kept only when one is given.
        `access` is "granted" or "denied" (the entry decision) and `reason` says why."""
        with self.db:
            cur = self.db.execute(
                "INSERT INTO event(ts, camera_id, track_id, decision, person_id, score, access, reason, alert) "
                "VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?)", (ts, camera_id, decision, person_id, score, access, reason, alert))
            event_id = cur.lastrowid
            if snapshot_jpeg:
                name = f"{event_id}.jpg"
                (self.snapshots_dir / name).write_bytes(snapshot_jpeg)
                self.db.execute("UPDATE event SET snapshot = ? WHERE id = ?", (name, event_id))
        return event_id

    _EVENT_SELECT = ("SELECT e.id, e.ts, e.camera_id, e.decision, e.person_id, e.score, e.snapshot, "
                     "e.reviewed, p.name, p.fields, e.access, e.reason, p.unit, p.code, p.person_type, e.alert "
                     "FROM event e LEFT JOIN person p ON p.id = e.person_id")

    @staticmethod
    def _event(r):
        return {"id": r[0], "ts": r[1], "camera_id": r[2], "decision": r[3], "person_id": r[4],
                "score": r[5], "has_snapshot": bool(r[6]), "reviewed": bool(r[7]),
                "person": r[8], "fields": json.loads(r[9]) if r[9] else {}, "access": r[10],
                "reason": r[11], "unit": r[12], "code": r[13], "person_type": r[14], "alert": r[15]}

    @_locked
    def list_events(self, decision=None, person_id=None, since=None, until=None, search=None,
                    reviewed=None, after_id=None, limit=50, offset=0, access=None):
        """Return (events newest first, total matching). Every filter is optional."""
        where, args = [], []
        if decision:
            where.append("e.decision = ?"); args.append(decision)
        if person_id:
            where.append("e.person_id = ?"); args.append(person_id)
        if since:
            where.append("e.ts >= ?"); args.append(since)
        if until:
            where.append("e.ts <= ?"); args.append(until)
        if reviewed is not None:
            where.append("e.reviewed = ?"); args.append(1 if reviewed else 0)
        if after_id:
            where.append("e.id > ?"); args.append(after_id)
        if access:
            where.append("e.access = ?"); args.append(access)
        if search:
            where.append("(p.name LIKE ? OR p.fields LIKE ? OR p.unit LIKE ? OR p.code LIKE ? OR p.phone LIKE ?)")
            args += [f"%{search}%"] * 5
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        total = self.db.execute("SELECT COUNT(*) FROM event e LEFT JOIN person p ON p.id = e.person_id"
                                + clause, args).fetchone()[0]
        rows = self.db.execute(self._EVENT_SELECT + clause + " ORDER BY e.id DESC LIMIT ? OFFSET ?",
                               args + [limit, offset]).fetchall()
        return [self._event(r) for r in rows], total

    @_locked
    def get_event(self, event_id):
        r = self.db.execute(self._EVENT_SELECT + " WHERE e.id = ?", (event_id,)).fetchone()
        return self._event(r) if r else None

    @_locked
    def set_reviewed(self, event_id, reviewed):
        with self.db:
            self.db.execute("UPDATE event SET reviewed = ? WHERE id = ?",
                            (1 if reviewed else 0, event_id))

    @_locked
    def snapshot_path(self, event_id):
        r = self.db.execute("SELECT snapshot FROM event WHERE id = ?", (event_id,)).fetchone()
        return self.snapshots_dir / r[0] if r and r[0] else None

    @_locked
    def event_stats(self, since):
        """Counts since a time. `pending_review` = unknown, uncertain or denied scans nobody looked at yet."""
        counts = {d: n for d, n in self.db.execute(
            "SELECT decision, COUNT(*) FROM event WHERE ts >= ? GROUP BY decision", (since,))}
        access = {a: n for a, n in self.db.execute(
            "SELECT access, COUNT(*) FROM event WHERE ts >= ? AND access IS NOT NULL GROUP BY access", (since,))}
        pending = self.db.execute(
            "SELECT COUNT(*) FROM event WHERE ts >= ? AND reviewed = 0 AND (decision != 'resident' OR access = 'denied')",
            (since,)).fetchone()[0]
        return {"total": sum(counts.values()), "resident": counts.get("resident", 0),
                "unknown": counts.get("unknown", 0), "uncertain": counts.get("uncertain", 0),
                "granted": access.get("granted", 0), "denied": access.get("denied", 0),
                "pending_review": pending}

    @_locked
    def purge_snapshots(self, older_than):
        """Delete snapshot files older than a time (FR-21). The event rows stay."""
        rows = self.db.execute("SELECT id, snapshot FROM event WHERE snapshot IS NOT NULL AND ts < ?",
                               (older_than,)).fetchall()
        with self.db:
            for event_id, name in rows:
                (self.snapshots_dir / name).unlink(missing_ok=True)
                self.db.execute("UPDATE event SET snapshot = NULL WHERE id = ?", (event_id,))
        return len(rows)

    # ------------------------------------------------------------------ alerts
    _ALERT_SELECT = ("SELECT a.id, a.ts, a.last_ts, a.level, a.confidence, a.person_id, a.event_id, a.camera_id, a.score, "
                     "a.count, a.status, a.ack_by, a.ack_at, a.ack_note, p.name, p.code, p.person_type, p.unit, p.watch, "
                     "e.snapshot FROM alert a LEFT JOIN person p ON p.id = a.person_id "
                     "LEFT JOIN event e ON e.id = a.event_id")

    @staticmethod
    def _alert(r):
        keys = ("id", "ts", "last_ts", "level", "confidence", "person_id", "event_id", "camera_id", "score", "count",
                "status", "ack_by", "ack_at", "ack_note", "person", "code", "person_type", "unit")
        alert = dict(zip(keys, r[:18]))
        alert.update(watch=json.loads(r[18] or "{}"), has_snapshot=bool(r[19]))
        return alert

    @_locked
    def raise_alert(self, level, confidence, person_id, event_id, camera_id, score, cooldown):
        """Open a new alert, or add to the one already open for this person (same person re-detected
        within `cooldown` seconds). Returns (alert, is_new)."""
        now = time.time()
        row = self.db.execute("SELECT id, level FROM alert WHERE status = 'open' AND person_id IS ? AND last_ts > ?",
                              (person_id, now - cooldown)).fetchone()
        with self.db:
            if row:
                stronger = "critical" if "critical" in (row[1], level) else level
                self.db.execute("UPDATE alert SET last_ts = ?, count = count + 1, event_id = ?, score = MAX(score, ?), "
                                "level = ? WHERE id = ?", (now, event_id, score, stronger, row[0]))
                return self.get_alert(row[0]), False
            cur = self.db.execute(
                "INSERT INTO alert(ts, last_ts, level, confidence, person_id, event_id, camera_id, score) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (now, now, level, confidence, person_id, event_id, camera_id, score))
        return self.get_alert(cur.lastrowid), True

    @_locked
    def get_alert(self, alert_id):
        r = self.db.execute(self._ALERT_SELECT + " WHERE a.id = ?", (alert_id,)).fetchone()
        return self._alert(r) if r else None

    @_locked
    def list_alerts(self, status=None, limit=50):
        clause, args = (" WHERE a.status = ?", [status]) if status else ("", [])
        rows = self.db.execute(self._ALERT_SELECT + clause + " ORDER BY a.status = 'open' DESC, a.last_ts DESC LIMIT ?",
                               args + [limit]).fetchall()
        return [self._alert(r) for r in rows]

    @_locked
    def acknowledge_alert(self, alert_id, username, note):
        with self.db:
            self.db.execute("UPDATE alert SET status = 'acknowledged', ack_by = ?, ack_at = ?, ack_note = ? "
                            "WHERE id = ? AND status = 'open'", (username, time.time(), note, alert_id))
        return self.get_alert(alert_id)

    @_locked
    def alert_snapshot_path(self, alert_id):
        r = self.db.execute("SELECT e.snapshot FROM alert a JOIN event e ON e.id = a.event_id WHERE a.id = ?",
                            (alert_id,)).fetchone()
        return self.snapshots_dir / r[0] if r and r[0] else None

    # ------------------------------------------------------------------ audit
    @staticmethod
    def _audit_hash(prev_hash, ts, username, action, detail_json):
        return hashlib.sha256(f"{prev_hash}|{ts!r}|{username}|{action}|{detail_json}".encode()).hexdigest()

    @_locked
    def audit(self, username, action, detail=None):
        """Add an audit line. Each line stores a hash of itself AND the previous line, so changing
        or removing an old line breaks the chain (see verify_audit)."""
        ts, detail_json = time.time(), json.dumps(detail or {}, sort_keys=True)
        last = self.db.execute("SELECT hash FROM audit WHERE hash IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
        prev_hash = last[0] if last else "GENESIS"
        with self.db:
            self.db.execute(
                "INSERT INTO audit(ts, username, action, detail, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)",
                (ts, username, action, detail_json, prev_hash,
                 self._audit_hash(prev_hash, ts, username, action, detail_json)))

    @_locked
    def verify_audit(self):
        """Check the hash chain. Returns {"ok", "checked", "legacy", "broken_at"}.
        `legacy` counts old lines written before the chain existed (they cannot be verified)."""
        prev, checked, legacy = "GENESIS", 0, 0
        for row_id, ts, username, action, detail, prev_hash, digest in self.db.execute(
                "SELECT id, ts, username, action, detail, prev_hash, hash FROM audit ORDER BY id"):
            if digest is None:
                legacy += 1
                continue
            if prev_hash != prev or digest != self._audit_hash(prev_hash, ts, username, action, detail):
                return {"ok": False, "checked": checked, "legacy": legacy, "broken_at": row_id}
            prev, checked = digest, checked + 1
        return {"ok": True, "checked": checked, "legacy": legacy, "broken_at": None}

    @_locked
    def list_audit(self, limit=100, offset=0):
        rows = self.db.execute(
            "SELECT id, ts, username, action, detail FROM audit ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset)).fetchall()
        return [{"id": r[0], "ts": r[1], "username": r[2], "action": r[3],
                 "detail": json.loads(r[4])} for r in rows]
