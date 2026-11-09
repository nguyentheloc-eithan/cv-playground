"""Step 4: the two things the product does.

    register(name, fields, images)  -> save a new person
    check(image)                    -> who is in this picture, and are they allowed?

Everything else in the project exists to feed these two functions.
"""
from .faces import similarity


class RegisterError(Exception):
    """Raised with a short code (for the UI) and a human message."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Recognizer:
    def __init__(self, cfg, engine, db):
        self.cfg, self.engine, self.db = cfg, engine, db

    # ---------------------------------------------------------------- register
    def register(self, name, fields, images):
        cfg = self.cfg["registration"]

        # 1. Check the form against the customer's own list of fields.
        allowed = {f["key"] for f in self.cfg["person_fields"]}
        for f in self.cfg["person_fields"]:
            if f.get("required") and not fields.get(f["key"]):
                raise RegisterError("MISSING_FIELD", f"'{f['label']}' is required")
        extra = set(fields) - allowed
        if extra:
            raise RegisterError("UNKNOWN_FIELD", f"Unknown field(s): {sorted(extra)}")

        # 2. Check the number of photos.
        if not cfg["min_photos"] <= len(images) <= cfg["max_photos"]:
            raise RegisterError(
                "PHOTO_COUNT", f"Send {cfg['min_photos']} to {cfg['max_photos']} photos")

        # 3. Each photo must contain exactly one clear face. Turn it into a vector.
        vectors = []
        for number, image in enumerate(images, start=1):
            faces = self.engine.find_faces(image)
            if len(faces) != 1:
                raise RegisterError("FACE_COUNT", f"Photo {number}: need exactly 1 face, found {len(faces)}")
            if faces[0].size < cfg["min_face_px"]:
                raise RegisterError("FACE_SMALL", f"Photo {number}: face is too small, move closer")
            vectors.append(self.engine.face_vector(image, faces[0]))

        # 4. Save.
        return self.db.add_person(name, fields, vectors)

    # ------------------------------------------------------------------- check
    def check(self, image):
        """Return one result per face found. Each result is a dict the UI can show."""
        policy = self.cfg["policy"]
        faces = [f for f in self.engine.find_faces(image) if f.size >= policy["min_face_px"]]
        if not faces:
            return [{"decision": "no_face", "score": 0, "person": None, "bbox": None}]

        known = self.db.all_vectors()
        results = []
        for face in faces:
            person_id, score = self._best_match(self.engine.face_vector(image, face), known)

            # The decision rule: compare the score with two thresholds from the config.
            if person_id is None or score < policy["reject_threshold"]:
                decision, person = "unknown", None
            elif score >= policy["accept_threshold"]:
                decision, person = "authorized", self.db.get_person(person_id)
            else:
                decision, person = "uncertain", None  # in between: not sure

            results.append({
                "decision": decision,
                "score": round(score, 3),
                "person": person["name"] if person else None,
                "fields": person["fields"] if person else {},
                "bbox": [face.x, face.y, face.w, face.h],
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
