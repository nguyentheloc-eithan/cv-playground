"""Step 4: the product logic.

    register(profile, images, consent)  -> save a new person
    check(image)                        -> who is in this picture, and may they enter?

Everything else in the project exists to feed these functions.
"""
import re
import threading
import time
from datetime import datetime

from . import access, alerts
from .faces import similarity


class RegisterError(Exception):
    """A problem the user can fix. `code` is for the UI, `field` says what to highlight
    (for example "photos[2]")."""
    def __init__(self, code, message, field=None):
        super().__init__(message)
        self.code, self.field = code, field


# ---- small validators (also used when editing a person) -----------------------------------------
def normalize_phone(text, minimum=7):
    """'+84 (912) 345-678' -> '+84912345678'. Raises RegisterError when it cannot be a phone number."""
    text = (text or "").strip()
    digits = re.sub(r"\D", "", text)
    if not re.fullmatch(r"\+?[\d\s().\-]+", text) or not minimum <= len(digits) <= 15:
        raise RegisterError("BAD_PHONE", "Enter a valid phone number (digits, optional leading +)", "phone")
    return ("+" if text.startswith("+") else "") + digits


def parse_date(text, end_of_day=False, field="valid_until"):
    """'2026-12-31' -> timestamp (start of that day, or its last second). Empty -> None."""
    if text in (None, ""):
        return None
    try:
        day = datetime.strptime(str(text), "%Y-%m-%d")
    except ValueError:
        raise RegisterError("BAD_DATE", "Use the date format YYYY-MM-DD", field)
    return day.replace(hour=23, minute=59, second=59).timestamp() if end_of_day else day.timestamp()


class Recognizer:
    def __init__(self, cfg, engine, db):
        self.cfg, self.engine, self.db = cfg, engine, db
        # The OpenCV models are not safe to call from two threads at once.
        self.engine_lock = threading.Lock()

    # --------------------------------------------------------------- profile checks
    def clean_profile(self, data, existing=None):
        """Validate the person's details and return them ready to save.

        `existing` is the current record when editing (so unchanged values are not re-checked
        against themselves, for example the phone number)."""
        reg, site = self.cfg["registration"], self.cfg["site"]
        out = {}

        name = (data.get("name") or "").strip()
        if not name:
            raise RegisterError("MISSING_NAME", "Enter a name", "name")
        out["name"] = name[:120]

        phone = (data.get("phone") or "").strip()
        if not phone and reg["require_phone"]:
            raise RegisterError("MISSING_FIELD", "Phone number is required", "phone")
        out["phone"] = normalize_phone(phone) if phone else ""
        if out["phone"] and reg["unique_phone"]:
            other = self.db.find_person(out["phone"], exclude_id=existing["id"] if existing else None)
            if other:
                raise RegisterError("DUPLICATE_PHONE",
                                    f"This phone number is already registered to {other['name']} ({other['code']})", "phone")

        type_id = data.get("person_type") or "resident"
        kinds = {t["id"]: t for t in self.cfg["person_types"]}
        if type_id not in kinds:
            raise RegisterError("BAD_TYPE", "Unknown person type", "person_type")
        kind = kinds[type_id]
        out["person_type"] = type_id

        unit = str(data.get("unit") or "").strip()
        if kind.get("needs_unit") and not unit:
            raise RegisterError("MISSING_FIELD", f"{site['unit_label']} is required", "unit")
        if unit and site["units"] and unit not in [str(u) for u in site["units"]]:
            raise RegisterError("BAD_UNIT", f"'{unit}' is not a known {site['unit_label'].lower()}", "unit")
        out["unit"] = unit[:40]

        valid_from = parse_date(data.get("valid_from"), False, "valid_from")
        valid_until = parse_date(data.get("valid_until"), True, "valid_until")
        if valid_until is None and kind.get("default_days") and not existing:
            valid_until = parse_date(datetime.fromtimestamp(time.time() + kind["default_days"] * 86400)
                                     .strftime("%Y-%m-%d"), True)
        if kind.get("needs_expiry") and valid_until is None:
            raise RegisterError("MISSING_FIELD", f"{kind['label']}s need a 'valid until' date", "valid_until")
        if valid_from and valid_until and valid_until < valid_from:
            raise RegisterError("BAD_DATE", "'Valid until' must be after 'valid from'", "valid_until")
        out["valid_from"], out["valid_until"] = valid_from, valid_until

        out["notes"] = str(data.get("notes") or "").strip()[:500]

        # Watch-list types (criminal / banned) need a reason and a source, so every entry can be justified and reviewed.
        out["watch"] = {}
        if kind.get("watchlist"):
            given = data.get("watch") or {}
            reason, source = str(given.get("reason") or "").strip(), str(given.get("source") or "").strip()
            if len(reason) < 3:
                raise RegisterError("MISSING_FIELD", "Reason for the watch list is required", "watch_reason")
            if len(source) < 2:
                raise RegisterError("MISSING_FIELD", "Source is required (who reported this, e.g. police, security company)", "watch_source")
            kept = (existing or {}).get("watch") or {}
            out["watch"] = {
                "reason": reason[:300], "source": source[:150], "reference": str(given.get("reference") or "").strip()[:80],
                "instructions": str(given.get("instructions") or "").strip()[:300],
                "review_by": parse_date(given.get("review_by"), True, "watch_review_by"),
                "added_by": given.get("added_by") or kept.get("added_by") or "", "added_at": kept.get("added_at") or time.time()}

        fields = {k: str(v).strip() for k, v in (data.get("fields") or {}).items() if str(v).strip()}
        known = {f["key"] for f in self.cfg["person_fields"]}
        for f in self.cfg["person_fields"]:
            if f.get("required") and not fields.get(f["key"]):
                raise RegisterError("MISSING_FIELD", f"'{f['label']}' is required", f["key"])
        extra = set(fields) - known
        if extra:
            raise RegisterError("UNKNOWN_FIELD", f"Unknown field(s): {sorted(extra)}")
        out["fields"] = fields
        return out

    # ---------------------------------------------------------------- register
    def register(self, data, images, consent):
        """Validate everything, then save. Returns {"id": ..., "code": ...}."""
        cfg = self.cfg["registration"]
        profile = self.clean_profile(data)
        kind = access.person_type(self.cfg, profile["person_type"])
        if kind.get("watchlist"):    # no consent from the person; the operator confirms the legal basis instead
            if not consent:
                raise RegisterError("NO_CONSENT", "Confirm you are authorised to record this information", "consent")
        elif cfg["require_consent"] and not consent:
            raise RegisterError("NO_CONSENT", "Consent must be confirmed", "consent")

        if not cfg["min_photos"] <= len(images) <= cfg["max_photos"]:
            raise RegisterError(
                "PHOTO_COUNT", f"Send {cfg['min_photos']} to {cfg['max_photos']} photos", "photos")

        # Each photo must be a clear, front-facing picture of exactly one face.
        vectors, jpegs = [], []
        with self.engine_lock:
            for number, image in enumerate(images, start=1):
                faces = self.engine.find_faces(image)
                problem = self._photo_problem(image, faces)
                if problem:
                    code, message = problem
                    raise RegisterError(code, f"Photo {number}: {message}", f"photos[{number}]")
                vectors.append(self.engine.face_vector(image, faces[0]))
                jpegs.append(self.engine.to_jpeg(image))

        # Security: the same face must not be registered twice (stops double identities).
        if cfg["block_duplicate_faces"]:
            known = self.db.all_vectors()
            for vector in vectors:
                person_id, score = self._best_match(vector, known)
                if person_id is not None and score >= self.cfg["policy"]["accept_threshold"]:
                    other = self.db.get_person(person_id)
                    raise RegisterError("DUPLICATE_FACE",
                                        f"This face is already registered as {other['name']} ({other['code']})", "photos")

        person_id = self.db.add_person(profile, vectors, jpegs, cfg["consent_text_version"])
        return {"id": person_id, "code": self.db.get_person(person_id)["code"]}

    # ----------------------------------------------------------- photo quality
    def _photo_problem(self, image, faces):
        """Is this a good enrollment photo? Return (code, message) for the first problem, or None."""
        cfg = self.cfg["registration"]
        if len(faces) == 0:
            return "NO_FACE", "No face found"
        if len(faces) > 1:
            return "MANY_FACES", "More than one face in view"
        face = faces[0]
        if face.size < cfg["min_face_px"]:
            return "FACE_SMALL", "Face too small, move closer"
        if self.engine.sharpness(image, face) < cfg["min_sharpness"]:
            return "PHOTO_BLURRY", "Image is blurry, hold still"
        if face.yaw > cfg["max_yaw"]:
            return "FACE_ANGLE", "Look straight at the camera"
        return None

    def assess(self, image):
        """Live feedback while capturing: is the camera picture good enough to use right now?"""
        with self.engine_lock:
            faces = self.engine.find_faces(image)
            problem = self._photo_problem(image, faces)
        face = faces[0] if len(faces) == 1 else None
        return {"ok": problem is None, "code": problem[0] if problem else None,
                "message": problem[1] if problem else "Looking good",
                "bbox": [face.x, face.y, face.w, face.h] if face else None}

    # ------------------------------------------------------------------- check
    def check(self, image):
        """Return one result per face found.

        `decision` says who it is:  resident (a registered person) / uncertain / unknown.
        `access`   says whether they may enter now: {"granted", "reason", "alert"}."""
        policy = self.cfg["policy"]
        with self.engine_lock:
            faces = [f for f in self.engine.find_faces(image) if f.size >= policy["min_face_px"]]
            vectors = [self.engine.face_vector(image, f) for f in faces]
        if not faces:
            return [{"decision": "no_face", "score": 0, "person": None, "person_id": None, "fields": {},
                     "bbox": None, "access": None, "alert": None, "watch": None}]

        known = self.db.all_vectors()
        results = []
        for face, vector in zip(faces, vectors):
            person_id, score = self._best_match(vector, known)

            # The decision rule: compare the score with two thresholds from the config.
            alert = watch = None
            if person_id is None or score < policy["reject_threshold"]:
                decision, person = "unknown", None
                decided = {"granted": False, "reason": "Not registered", "alert": False}
            elif score >= policy["accept_threshold"]:
                decision, person = "resident", self.db.get_person(person_id)
                decided = access.evaluate(person, self.cfg)
                if decided["alert"]:   # a watch-list match: how sure are we?
                    level, confidence = alerts.classify(self.cfg, person, score)
                    alert = {"level": level, "confidence": confidence}
                    watch = {k: person["watch"].get(k, "") for k in ("reason", "instructions")}
            else:
                decision, person = "uncertain", None  # in between: not sure
                decided = {"granted": False, "reason": "Identity not confirmed", "alert": False}

            results.append({
                "decision": decision,
                "score": round(score, 3),
                "person": person["name"] if person else None,
                "person_id": person["id"] if person else None,
                "code": person["code"] if person else None,
                "unit": person["unit"] if person else None,
                "person_type": person["person_type"] if person else None,
                "fields": person["fields"] if person else {},
                "bbox": [face.x, face.y, face.w, face.h],
                "access": decided,
                "alert": alert,
                "watch": watch,
            })
        return results

    @staticmethod
    def _best_match(vector, known):
        """Find the registered person whose photo looks most like this face."""
        best_id, best_score = None, 0.0
        for person_id, other in known:
            s = similarity(vector, other)
            if best_id is None or s > best_score:
                best_id, best_score = person_id, s
        return best_id, best_score
