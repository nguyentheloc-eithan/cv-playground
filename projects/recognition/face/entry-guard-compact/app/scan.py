"""Step 5: the security console's brain. One call = one camera picture.

    scan(image) -> the same results as Recognizer.check, and each finished recognition is
                   written to the event log (so the console shows a history of who was seen).

A person standing in front of the camera is seen many times a second. To avoid thousands of log
lines, the same person (or "unknown") is logged at most once per `cooldown_seconds`.
"""
import threading
import time


class Scanner:
    def __init__(self, cfg, recognizer, db, engine, alerts=None):
        self.cfg, self.recognizer, self.db, self.engine = cfg, recognizer, db, engine
        self.alerts = alerts           # AlertService: opens alerts and sends notifications
        self.cooldown = cfg["scan"]["cooldown_seconds"]
        self.retention_days = cfg["scan"]["snapshot_retention_days"]
        self.last_logged = {}          # (camera, who) -> time of the last log line
        self.last_purge = 0.0
        self.lock = threading.Lock()

    def scan(self, image, camera_id=None):
        camera_id = camera_id or self.cfg["scan"]["camera_id"]
        results = self.recognizer.check(image)
        now = time.time()
        for r in results:
            r["event_id"] = None
            if r["decision"] == "no_face" or not self._due(camera_id, r, now):
                continue
            # Granted residents are logged without a picture; unknown, uncertain and DENIED scans keep a snapshot.
            snapshot = None
            if r["decision"] != "resident" or not r["access"]["granted"]:
                with self.recognizer.engine_lock:
                    snapshot = self.engine.crop_jpeg(image, r["bbox"])
            granted = r["access"]["granted"]
            r["event_id"] = self.db.add_event(now, camera_id, r["decision"], r["person_id"], r["score"], snapshot,
                                              "granted" if granted else "denied", r["access"]["reason"],
                                              r["alert"]["level"] if r["alert"] else None)
            if r["alert"] and self.alerts:     # a watch-list match: raise the alert (and notify) straight away
                r["alert_id"] = self.alerts.raise_for(r, r["event_id"], camera_id, snapshot,
                                                      self.db.get_person(r["person_id"]))["id"]
        self._purge_if_due(now)
        return results

    def _due(self, camera_id, result, now):
        """True if this person has not been logged during the cooldown."""
        who = result["person_id"] if result["person_id"] else result["decision"]
        key = (camera_id, who)
        with self.lock:
            if now - self.last_logged.get(key, 0) < self.cooldown:
                return False
            self.last_logged[key] = now
            return True

    def _purge_if_due(self, now):
        """Once an hour, delete snapshots older than the retention period."""
        if now - self.last_purge > 3600:
            self.last_purge = now
            self.db.purge_snapshots(now - self.retention_days * 86400)
