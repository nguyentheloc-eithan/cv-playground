"""Step-up confirmation, like a banking app.

A risky action (delete a person, change the watch list, manage users...) needs a FRESH confirmation, even
though the admin is already signed in. The admin proves it is really them with one of:

    face      a live face check: look straight, then turn the head (a held-up photo cannot turn)
    pin       a numeric PIN
    password  the account password (always available as the fallback)

A successful check returns a one-time "grant" token. The page repeats the risky request with that token; the server
accepts it once, only for that user and that action, and only for a couple of minutes.
"""
import hashlib
import secrets
import time

from .faces import similarity


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def available_methods(security):
    """Methods this user can use now, the preferred one first. The password is always last."""
    methods = [m for m, on in (("face", security["face_enabled"]), ("pin", security["pin_enabled"])) if on]
    if security["last_method"] in methods:
        methods.remove(security["last_method"])
        methods.insert(0, security["last_method"])
    return methods + ["password"]


def pin_problem(pin, length):
    """Why this PIN is not acceptable, or None."""
    if not (pin.isdigit() and len(pin) == length):
        return f"PIN must be exactly {length} digits"
    if len(set(pin)) == 1:
        return "PIN must not repeat one digit"
    if pin in "01234567890123456789" or pin in "98765432109876543210":
        return "PIN must not be a simple sequence"
    return None


def new_grant(db, user_id, action, method, seconds):
    token = secrets.token_urlsafe(24)
    db.create_grant(token_hash(token), user_id, action, method, time.time() + seconds)
    return token


NOT_RECOGNISED = "Face not recognised"


def _measure(recognizer, cfg, images):
    """Find the face in each live picture. Returns (message, [(yaw, vector), ...]); message is None when fine."""
    su = cfg["security"]["step_up"]
    need = 2 if su["require_head_turn"] else 1
    if len(images) < need:
        return "Look straight at the camera, then turn your head slightly to the left or right", None
    seen = []
    with recognizer.engine_lock:
        for image in images[:need]:
            faces = recognizer.engine.find_faces(image)
            if len(faces) != 1:
                return "Exactly one face must be in view", None
            face = faces[0]
            if face.size < cfg["registration"]["min_face_px"]:
                return "Move closer to the camera", None
            seen.append((face.yaw, recognizer.engine.face_vector(image, face)))
    return None, seen


def _pose_problem(su, seen):
    """The head must look straight in the first picture and be clearly turned in the second."""
    if seen[0][0] > 0.30:
        return "Look straight at the camera"
    if len(seen) == 2 and (seen[1][0] < su["head_turn_min_yaw"] or seen[1][0] - seen[0][0] < 0.12):
        return "Turn your head slightly to the left or right"
    return None


def pose_check(recognizer, cfg, images):
    """Only the pose (one face, straight, then turned). Says nothing about WHO it is. None = fine."""
    message, seen = _measure(recognizer, cfg, images)
    return message or _pose_problem(cfg["security"]["step_up"], seen)


def verify_face(recognizer, cfg, images, user_vectors, scores=None):
    """Check live face pictures against the user's enrolled face. Returns (ok, message).

    With `require_head_turn` two pictures are needed: the first looking straight (must match well), the second
    with the head clearly turned (must still be the same person). A printed photo or a screen picture cannot
    produce that."""
    su = cfg["security"]["step_up"]
    if not user_vectors:
        return False, "No face is enrolled for this account"
    message, seen = _measure(recognizer, cfg, images)
    message = message or _pose_problem(su, seen)
    if message:
        return False, message
    best = [max(similarity(vector, v) for v in user_vectors) for _, vector in seen]
    if scores is not None:                      # for the audit log, so a failed check can be tuned or explained
        scores.extend(round(float(b), 2) for b in best)
    if best[0] < su["face_threshold"]:
        return False, NOT_RECOGNISED
    if len(best) == 2 and best[1] < cfg["policy"]["accept_threshold"]:
        return False, NOT_RECOGNISED
    return True, ""
