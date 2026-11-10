import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import access, auth, privacy
from app.config import load_config
from app.db import Database
from app.faces import Face
from app.recognize import RegisterError, Recognizer


class FakeEngine:
    """Stands in for the AI models: the 'image' is already the face vector.
    Set `sharp` or `yaw_shift` to simulate a blurry or turned face."""
    sharp = 999.0
    yaw_shift = 0.0
    size = 100.0

    def find_faces(self, image):
        nose_x = 50 + self.yaw_shift
        row = np.array([0, 0, self.size, self.size, 30, 40, 70, 40, nose_x, 60, 35, 80, 65, 80, 0.99])
        return [Face(0, 0, self.size, self.size, 0.99, row)]

    def face_vector(self, image, face):
        return image / np.linalg.norm(image)

    def sharpness(self, image, face):
        return self.sharp

    def to_jpeg(self, image):
        return b"fake-jpeg"

    def crop_jpeg(self, image, bbox):
        return b"fake-crop"


def v(*numbers):
    return np.array(numbers, dtype=np.float32)


def make(tmp_path, customer="example"):
    cfg = load_config(customer)
    db = Database(tmp_path / "t.db", tmp_path / "photos", id_prefix=cfg["site"]["id_prefix"])
    engine = FakeEngine()
    return Recognizer(cfg, engine, db), engine


PHONES = iter(f"+8490000{n:04d}" for n in range(10000))


def profile(**kw):
    """A valid resident; tests override single fields."""
    return {"name": "An", "phone": next(PHONES), "person_type": "resident", "unit": "302", "fields": {}, **kw}


def register(r, vector=(1, 0, 0, 0), consent=True, **kw):
    return r.register(profile(**kw), [v(*vector)], consent)


# ------------------------------------------------------------------ config
def test_customer_overrides_default():
    assert load_config()["policy"]["accept_threshold"] == 0.363
    cfg = load_config("example")
    assert cfg["policy"]["accept_threshold"] == 0.40
    assert cfg["policy"]["reject_threshold"] == 0.30              # kept from default
    assert cfg["site"]["unit_label"] == "Apartment" and cfg["site"]["id_prefix"] == "APT"
    assert {t["id"] for t in cfg["person_types"]} >= {"resident", "visitor", "blocked"}


# ------------------------------------------------------------ register / check
def test_register_generates_an_id_and_stores_all_details(tmp_path):
    r, _ = make(tmp_path)
    made = register(r, phone="+84 912 345 678", unit="302", notes=" likes mornings ",
                    fields={"email": "an@example.com", "vehicle_plate": "51A-12345"})
    assert made["code"] == f"APT-{made['id']:05d}"
    person = r.db.get_person(made["id"])
    assert person["phone"] == "+84912345678"                       # tidied
    assert person["unit"] == "302" and person["notes"] == "likes mornings"
    assert person["fields"]["vehicle_plate"] == "51A-12345"
    assert person["consent_at"] and person["consent_version"] == "v1"
    assert (tmp_path / "photos" / str(made["id"]) / "1.jpg").read_bytes() == b"fake-jpeg"
    second = register(r, vector=(0, 1, 0, 0))
    assert second["code"] != made["code"]


def test_check_returns_person_details_and_access(tmp_path):
    r, _ = make(tmp_path)
    register(r, name="An", unit="302")
    hit = r.check(v(1, 0.01, 0, 0))[0]
    assert hit["decision"] == "resident" and hit["person"] == "An" and hit["unit"] == "302"
    assert hit["access"] == {"granted": True, "reason": "", "alert": False}
    miss = r.check(v(0, 1, 0, 0))[0]
    assert miss["decision"] == "unknown" and miss["access"]["granted"] is False
    assert miss["access"]["reason"] == "Not registered"


@pytest.mark.parametrize("change, code, field", [
    ({"name": " "}, "MISSING_NAME", "name"),
    ({"phone": ""}, "MISSING_FIELD", "phone"),
    ({"phone": "abc"}, "BAD_PHONE", "phone"),
    ({"phone": "123"}, "BAD_PHONE", "phone"),
    ({"unit": ""}, "MISSING_FIELD", "unit"),                       # residents need a unit
    ({"person_type": "alien"}, "BAD_TYPE", "person_type"),
    ({"valid_until": "31/12/2026"}, "BAD_DATE", "valid_until"),
    ({"valid_from": "2026-12-31", "valid_until": "2026-12-01"}, "BAD_DATE", "valid_until"),
    ({"fields": {"hobby": "x"}}, "UNKNOWN_FIELD", None),
])
def test_profile_is_validated(tmp_path, change, code, field):
    r, _ = make(tmp_path)
    with pytest.raises(RegisterError) as e:
        register(r, **change)
    assert e.value.code == code and (field is None or e.value.field == field)
    assert r.db.list_people() == []


def test_consent_is_required(tmp_path):
    r, _ = make(tmp_path)
    with pytest.raises(RegisterError) as e:
        register(r, consent=False)
    assert e.value.code == "NO_CONSENT"


def test_the_same_phone_cannot_be_registered_twice(tmp_path):
    r, _ = make(tmp_path)
    register(r, phone="0912345678")
    with pytest.raises(RegisterError) as e:
        register(r, vector=(0, 1, 0, 0), phone="+0912 345 678")
    assert e.value.code == "DUPLICATE_PHONE" and "APT-" in str(e.value)


def test_the_same_face_cannot_be_registered_twice(tmp_path):
    r, _ = make(tmp_path)
    register(r, name="An")
    with pytest.raises(RegisterError) as e:
        register(r, name="Someone else", vector=(1, 0.02, 0, 0))   # same face, different details
    assert e.value.code == "DUPLICATE_FACE" and "An" in str(e.value)


def test_visitors_get_a_default_expiry_and_contractors_need_one(tmp_path):
    r, _ = make(tmp_path)
    made = register(r, person_type="visitor", unit="302")
    until = r.db.get_person(made["id"])["valid_until"]
    assert 0.9 * 86400 < until - time.time() < 2 * 86400            # about one day from now
    cfg = r.cfg
    contractor = next(t for t in cfg["person_types"] if t["id"] == "contractor")
    contractor["default_days"] = None                                # no default: the date must be typed
    with pytest.raises(RegisterError) as e:
        register(r, vector=(0, 1, 0, 0), person_type="contractor")
    assert e.value.field == "valid_until"


def test_unit_must_be_in_the_site_list_when_there_is_one(tmp_path):
    r, _ = make(tmp_path)
    r.cfg["site"]["units"] = [101, 102]
    register(r, unit="101")
    with pytest.raises(RegisterError) as e:
        register(r, vector=(0, 1, 0, 0), unit="999")
    assert e.value.code == "BAD_UNIT"


def test_photo_quality_is_checked(tmp_path):
    r, engine = make(tmp_path)
    engine.sharp = 5.0
    with pytest.raises(RegisterError) as e:
        register(r)
    assert e.value.code == "PHOTO_BLURRY" and e.value.field == "photos[1]"
    engine.sharp, engine.yaw_shift = 999.0, 40.0
    with pytest.raises(RegisterError) as e:
        register(r)
    assert e.value.code == "FACE_ANGLE"
    engine.yaw_shift, engine.size = 0.0, 20.0
    with pytest.raises(RegisterError) as e:
        register(r)
    assert e.value.code == "FACE_SMALL"
    assert r.db.list_people() == []                                 # nothing saved by failed attempts


def test_delete_erases_everything(tmp_path):
    r, _ = make(tmp_path)
    made = register(r)
    r.db.delete_person(made["id"])
    assert r.check(v(1, 0, 0, 0))[0]["decision"] == "unknown"
    assert not (tmp_path / "photos" / str(made["id"])).exists()


# ------------------------------------------------------------ access rules
def test_disabled_person_is_recognised_but_denied(tmp_path):
    r, _ = make(tmp_path)
    made = register(r, name="An")
    r.db.update_person(made["id"], status="disabled")
    hit = r.check(v(1, 0, 0, 0))[0]
    assert hit["decision"] == "resident" and hit["person"] == "An"   # we know who it is...
    assert hit["access"]["granted"] is False and hit["access"]["reason"] == "Account disabled"


WATCH = {"reason": "Wanted for burglary", "source": "City Police", "reference": "CASE-2291",
         "instructions": "Do not approach. Call 113."}


def test_watchlist_people_are_denied_with_an_alert(tmp_path):
    r, _ = make(tmp_path)
    register(r, person_type="criminal", unit="", watch=WATCH)
    result = r.check(v(1, 0, 0, 0))[0]
    assert result["access"]["granted"] is False and result["access"]["alert"] is True
    assert result["access"]["severity"] == "critical"
    assert result["alert"] == {"level": "critical", "confidence": "confirmed"}
    assert result["watch"]["instructions"] == "Do not approach. Call 113."


def test_watchlist_entries_need_a_reason_and_a_source(tmp_path):
    r, _ = make(tmp_path)
    with pytest.raises(RegisterError) as e:
        register(r, person_type="criminal", unit="", watch={"source": "Police"})
    assert (e.value.code, e.value.field) == ("MISSING_FIELD", "watch_reason")
    with pytest.raises(RegisterError) as e:
        register(r, person_type="criminal", unit="", watch={"reason": "Theft"})
    assert e.value.field == "watch_source"
    with pytest.raises(RegisterError) as e:                      # the operator must confirm the legal basis
        register(r, person_type="criminal", unit="", watch=WATCH, consent=False)
    assert e.value.code == "NO_CONSENT" and "authorised" in str(e.value)
    made = register(r, person_type="criminal", unit="", watch={**WATCH, "added_by": "boss", "review_by": "2099-01-01"})
    stored = r.db.get_person(made["id"])["watch"]
    assert stored["added_by"] == "boss" and stored["reference"] == "CASE-2291" and stored["review_by"] > time.time()
    # an ordinary resident carries no watch-list data, even if some was sent
    resident = register(r, vector=(0, 1, 0, 0), watch=WATCH)
    assert r.db.get_person(resident["id"])["watch"] == {}


def test_a_weak_criminal_match_is_only_a_possible_match_and_downgraded(tmp_path):
    r, _ = make(tmp_path)
    register(r, person_type="criminal", unit="", watch=WATCH)
    weak = v(0.42, (1 - 0.42 ** 2) ** 0.5, 0, 0)               # similarity 0.42: above accept (0.40), below confirm (0.45)
    result = r.check(weak)[0]
    assert result["decision"] == "resident"
    assert result["alert"] == {"level": "high", "confidence": "possible"}
    strong = r.check(v(1, 0, 0, 0))[0]
    assert strong["alert"]["level"] == "critical"


def test_a_banned_person_is_a_high_alert_even_when_the_match_is_certain(tmp_path):
    r, _ = make(tmp_path)
    register(r, person_type="blocked", unit="", watch=WATCH)
    assert r.check(v(1, 0, 0, 0))[0]["alert"] == {"level": "high", "confidence": "confirmed"}


def test_expired_and_not_yet_valid(tmp_path):
    r, _ = make(tmp_path)
    cfg, now = r.cfg, time.time()
    base = {"person_type": "resident", "status": "active"}
    assert access.evaluate({**base, "valid_until": now - 86400}, cfg, now)["reason"].startswith("Expired on")
    assert access.evaluate({**base, "valid_from": now + 86400}, cfg, now)["reason"].startswith("Not valid until")
    assert access.evaluate({**base, "valid_until": now + 86400}, cfg, now)["granted"]
    assert access.status_label({**base, "valid_until": now - 86400}, cfg, now) == "expired"
    assert access.status_label({**base, "valid_from": now + 86400}, cfg, now) == "pending"
    assert access.status_label({"person_type": "blocked"}, cfg, now) == "blocked"


def test_hours_and_days_per_person_type(tmp_path):
    r, _ = make(tmp_path)
    cfg = r.cfg
    contractor = {"person_type": "contractor", "status": "active"}            # 07:00-19:00
    saturday_3am = datetime(2026, 11, 14, 3, 0).timestamp()
    saturday_noon = datetime(2026, 11, 14, 12, 0).timestamp()
    assert access.evaluate(contractor, cfg, saturday_3am)["reason"] == "Outside allowed hours (07:00-19:00)"
    assert access.evaluate(contractor, cfg, saturday_noon)["granted"]
    cfg["access"]["days"] = ["mon", "tue", "wed", "thu", "fri"]                # weekdays only, site-wide
    assert access.evaluate({"person_type": "resident", "status": "active"}, cfg, saturday_noon)["reason"] == "Not allowed on Sat"


# ------------------------------------------------------- privacy and auth
def test_masking_for_viewers(tmp_path):
    r, _ = make(tmp_path)
    person = {"phone": "+84 912 345 678", "fields": {"email": "a@b.c", "id_document": "123456789"}}
    assert privacy.visible(person, r.cfg, "admin") == person
    seen = privacy.visible(person, r.cfg, "viewer")
    assert seen["phone"] == "•••••• 678" and seen["fields"]["id_document"] == "••••"
    assert seen["fields"]["email"] == "a@b.c"                                  # not marked sensitive


def test_password_and_token(tmp_path):
    stored = auth.hash_password("correct horse battery")
    assert auth.verify_password("correct horse battery", stored)
    assert not auth.verify_password("wrong", stored)
    secret = b"k" * 32
    token = auth.make_token(secret, 7, hours=1, epoch=3)
    assert auth.read_token(secret, token) == (7, 3)
    flipped = token[:-1] + ("1" if token[-1] == "0" else "0")
    assert auth.read_token(secret, flipped) is None                            # tampered
    assert auth.read_token(secret, auth.make_token(secret, 7, hours=-1)) is None  # expired
    assert auth.read_token(b"other" * 8, token) is None                        # wrong key


def test_password_policy():
    assert auth.password_problem("short", "an", 12)
    assert auth.password_problem("aaaaaaaaaaaaaaaa", "an", 12)                 # too repetitive
    assert auth.password_problem("an-and-a-long-one", "an", 12)                # contains the user name
    assert auth.password_problem("correct-horse-battery", "an", 12) is None


def test_audit_chain_detects_tampering(tmp_path):
    db = Database(tmp_path / "t.db", tmp_path / "photos")
    for n in range(4):
        db.audit("admin", f"action_{n}", {"n": n})
    assert db.verify_audit() == {"ok": True, "checked": 4, "legacy": 0, "broken_at": None}
    with db.db:                                                                # an attacker edits an old line
        db.db.execute("UPDATE audit SET action = 'nothing_happened' WHERE id = 2")
    broken = db.verify_audit()
    assert broken["ok"] is False and broken["broken_at"] == 2


# ------------------------------------------------------------ alert service and notifications
from app import alerts as alerts_module


def alert_setup(tmp_path, channels):
    r, _ = make(tmp_path)
    r.cfg["alerts"]["channels"] = channels
    sent = []
    service = alerts_module.AlertService(r.cfg, r.db, sender=lambda ch, payload: sent.append((ch, payload)), background=False)
    made = register(r, name="Karl Weber", person_type="criminal", unit="", watch=WATCH)
    return r, service, sent, r.db.get_person(made["id"])


def test_one_alert_per_incident_and_two_audiences(tmp_path):
    channels = [{"type": "telegram", "audience": "security", "token": "t", "chat_id": "1"},
                {"type": "webhook", "audience": "residents", "url": "http://x"}]
    r, service, sent, person = alert_setup(tmp_path, channels)
    result = r.check(v(1, 0, 0, 0))[0]
    first = service.raise_for(result, None, "laptop", b"jpg", person)
    again = service.raise_for(result, None, "laptop", b"jpg", person)          # re-detected within the cooldown
    assert first["id"] == again["id"] and again["count"] == 2 and first["level"] == "critical"
    assert len(sent) == 2                                                    # notified once per channel, not again

    security = next(p for ch, p in sent if p["audience"] == "security")["text"]
    residents = next(p for ch, p in sent if p["audience"] == "residents")["text"]
    assert "Karl Weber" in security and "Wanted for burglary" in security and "Do not approach" in security
    assert "Verify identity" in security
    assert "Karl" not in residents and "burglary" not in residents and "KR" not in residents   # no name, no offence
    assert "Do not open doors" in residents


def test_a_broken_channel_does_not_stop_the_others_and_is_audited(tmp_path):
    r, service, sent, person = alert_setup(tmp_path, [{"type": "webhook", "audience": "security", "url": "http://down"},
                                                      {"type": "webhook", "audience": "residents", "url": "http://up"}])

    def flaky(channel, payload):
        if channel["url"] == "http://down":
            raise ConnectionError("no route")
        sent.append(payload)
    service.sender = flaky
    service.raise_for(r.check(v(1, 0, 0, 0))[0], None, "laptop", b"jpg", person)
    assert [p["audience"] for p in sent] == ["residents"]
    actions = [a["action"] for a in r.db.list_audit()]
    assert "alert_send_failed" in actions and "alert_sent" in actions and "alert_raised" in actions


def test_no_channels_configured_means_no_notifications(tmp_path):
    r, service, sent, person = alert_setup(tmp_path, [])
    service.raise_for(r.check(v(1, 0, 0, 0))[0], None, "laptop", b"jpg", person)
    assert sent == [] and r.db.list_alerts("open")[0]["level"] == "critical"
