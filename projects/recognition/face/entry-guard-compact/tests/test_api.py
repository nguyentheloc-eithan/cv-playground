"""API tests. They need fastapi and httpx (pip install -r requirements.txt)."""
import sys
import time
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import api, auth
from test_compact import make

HEADERS = {"X-Requested-With": "entryguard"}      # the page always sends this (cross-site protection)
phones = iter(f"+8491000{n:04d}" for n in range(10000))


@pytest.fixture
def client(tmp_path, monkeypatch):
    # The fake engine treats the "image" as the face vector, so decode "1,0,0,0" -> vector.
    monkeypatch.setattr(api, "decode_image",
                        lambda text: np.array([float(x) for x in text.split(",")], dtype=np.float32))
    recognizer, _ = make(tmp_path)
    recognizer.db.add_user("boss", auth.hash_password("longpassword1"), "admin")
    recognizer.db.add_user("guest", auth.hash_password("longpassword2"), "viewer")
    sent = []                                           # alert messages "sent" (never leaves the test)
    app = api.create_app(recognizer.cfg, recognizer, recognizer.db, b"s" * 32,
                         notify_sender=lambda channel, payload: sent.append((channel, payload)))
    app.state.alerts.background = False                 # deliver inside the request so the test can look at it
    test_client = TestClient(app, headers=HEADERS)
    test_client.db, test_client.cfg, test_client.sent = recognizer.db, recognizer.cfg, sent
    return test_client


def login(client, user, password):
    return client.post("/api/login", json={"username": user, "password": password})


def person_body(**kw):
    return {"name": "An", "phone": next(phones), "person_type": "resident", "unit": "302",
            "fields": {"email": "an@example.com", "id_document": "123456789"},
            "images": ["1,0,0,0"], "consent": True, **kw}


def add_resident(client, **kw):
    login(client, "boss", "longpassword1")
    return client.post("/api/people", json=person_body(**kw)).json()


# ---------------------------------------------------------------- login and roles
def test_login_required(client):
    assert client.get("/api/people").status_code == 401
    assert login(client, "boss", "wrong").status_code == 401
    assert login(client, "boss", "longpassword1").status_code == 200
    assert client.get("/api/me").json() == {"username": "boss", "role": "admin"}
    client.post("/api/logout")
    assert client.get("/api/people").status_code == 401


def test_viewer_cannot_change_things(client):
    login(client, "guest", "longpassword2")
    assert client.get("/api/people").status_code == 200
    assert client.post("/api/people", json=person_body()).status_code == 403
    assert client.get("/api/audit").status_code == 403
    assert client.get("/api/users").status_code == 403


# ----------------------------------------------------------------- people
def test_register_returns_id_and_check_shows_access(client):
    created = add_resident(client, name="An", unit="302")
    assert created["code"].startswith("APT-") and created["name"] == "An"
    result = client.post("/api/check", json={"image": "1,0.01,0,0"}).json()[0]
    assert result["decision"] == "resident" and result["person"] == "An" and result["unit"] == "302"
    assert result["access"]["granted"] is True


def test_people_list_shows_status_and_masks_sensitive_data_for_viewers(client):
    add_resident(client, phone="+84912345678")
    admin_view = client.get("/api/people").json()[0]
    assert admin_view["phone"] == "+84912345678" and admin_view["fields"]["id_document"] == "123456789"
    assert admin_view["status_label"] == "active" and admin_view["type_label"] == "Resident"
    client.post("/api/logout")
    login(client, "guest", "longpassword2")
    viewer_view = client.get("/api/people").json()[0]
    assert viewer_view["phone"] == "•••••• 678"
    assert viewer_view["fields"]["id_document"] == "••••" and viewer_view["fields"]["email"] == "an@example.com"
    assert viewer_view["name"] == "An" and viewer_view["unit"] == "302"           # identity stays visible


def test_person_detail_includes_recent_scans(client):
    pid = add_resident(client)["id"]
    client.post("/api/scan", json={"image": "1,0,0,0"})
    detail = client.get(f"/api/people/{pid}").json()
    assert detail["scans_total"] == 1 and detail["recent_events"][0]["access"] == "granted"


def test_edit_validates_and_a_status_switch_skips_validation(client):
    pid = add_resident(client, name="An")["id"]
    assert client.patch(f"/api/people/{pid}", json={"unit": ""}).json()["error"]["field"] == "unit"
    edited = client.patch(f"/api/people/{pid}", json={"unit": "410", "valid_until": "2099-01-01", "notes": "new"})
    assert edited.status_code == 200 and edited.json()["unit"] == "410" and edited.json()["valid_until"] > time.time()
    disabled = client.patch(f"/api/people/{pid}", json={"status": "disabled"}).json()
    assert disabled["status_label"] == "disabled" and disabled["access"]["reason"] == "Account disabled"
    client.patch(f"/api/people/{pid}", json={"valid_until": ""})                       # clear the date
    assert client.get(f"/api/people/{pid}").json()["valid_until"] is None


def test_scan_of_a_disabled_or_blocked_person_is_denied_and_logged_with_a_reason(client):
    pid = add_resident(client, name="An")["id"]
    client.patch(f"/api/people/{pid}", json={"status": "disabled"})
    scan = client.post("/api/scan", json={"image": "1,0,0,0"}).json()[0]
    assert scan["decision"] == "resident" and scan["access"]["granted"] is False and scan["event_id"]
    event = client.get("/api/events?access_result=denied").json()["events"][0]
    assert event["reason"] == "Account disabled" and event["has_snapshot"] and event["code"].startswith("APT-")
    assert client.get("/api/events/stats").json()["denied"] == 1


def test_delete_removes_the_person_and_is_audited(client):
    pid = add_resident(client)["id"]
    assert client.delete(f"/api/people/{pid}").status_code == 204
    assert client.get("/api/people").json() == []
    actions = [a["action"] for a in client.get("/api/audit").json()]
    assert {"login", "person_created", "person_deleted"} <= set(actions)


def test_error_shape_for_a_missing_required_field(client):
    login(client, "boss", "longpassword1")
    r = client.post("/api/people", json=person_body(phone=""))
    assert r.status_code == 400
    assert r.json()["error"] == {"code": "MISSING_FIELD", "message": "Phone number is required", "field": "phone"}


def test_public_config_describes_the_site_and_person_types(client):
    cfg = client.get("/api/config").json()
    assert cfg["site"]["unit_label"] == "Apartment" and cfg["require_phone"] is True
    assert "visitor" in [t["id"] for t in cfg["person_types"]]
    assert any(f["key"] == "id_document" and f["sensitive"] for f in cfg["fields"])


# --------------------------------------------------------------- security layer
def test_changes_without_the_csrf_header_are_blocked(client):
    login(client, "boss", "longpassword1")
    plain = TestClient(client.app)                       # a client that does NOT send the header
    plain.cookies.update(client.cookies)
    blocked = plain.post("/api/people", json=person_body())
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "CSRF_BLOCKED"
    cross_site = client.post("/api/people", json=person_body(), headers={"Origin": "https://evil.example"})
    assert cross_site.status_code == 403
    assert client.get("/api/people").status_code == 200   # reading needs no header


def test_security_headers_are_sent(client):
    response = client.get("/api/health")
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY" and response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/").headers["content-security-policy"]


def test_login_locks_after_repeated_failures(client):
    limit = client.cfg["security"]["max_failed_logins"]
    for _ in range(limit):
        assert login(client, "boss", "wrong-password").status_code == 401
    locked = login(client, "boss", "longpassword1")                 # even the right password is refused now
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "ACCOUNT_LOCKED"
    assert "login_blocked" in [a["action"] for a in client.db.list_audit()]
    assert login(client, "guest", "longpassword2").status_code == 200    # other accounts are not affected


def test_changing_your_password_signs_out_other_sessions(client):
    second = TestClient(client.app, headers=HEADERS)                # the same user on another device
    assert login(client, "boss", "longpassword1").status_code == 200
    assert login(second, "boss", "longpassword1").status_code == 200
    assert client.post("/api/me/password", json={"current": "nope", "new": "a-brand-new-passw0rd"}).status_code == 400
    assert client.post("/api/me/password", json={"current": "longpassword1", "new": "short"}).json()["error"]["code"] == "WEAK_PASSWORD"
    assert client.post("/api/me/password", json={"current": "longpassword1", "new": "a-brand-new-passw0rd"}).status_code == 200
    assert client.get("/api/me").status_code == 200                 # this device stays signed in
    assert second.get("/api/me").status_code == 401                 # the other device is signed out
    assert login(second, "boss", "a-brand-new-passw0rd").status_code == 200


# ------------------------------------------------------------- user accounts
def test_admin_manages_users(client):
    login(client, "boss", "longpassword1")
    new = {"username": "night.guard", "password": "a-long-passphrase", "role": "viewer"}
    created = client.post("/api/users", json=new)
    assert created.status_code == 201 and "pw_hash" not in created.text
    assert client.post("/api/users", json=new).json()["error"]["code"] == "USER_EXISTS"
    assert client.post("/api/users", json={**new, "username": "x y"}).json()["error"]["code"] == "BAD_USERNAME"
    assert client.post("/api/users", json={**new, "username": "other", "password": "short"}).json()["error"]["code"] == "WEAK_PASSWORD"
    assert {u["username"] for u in client.get("/api/users").json()} == {"boss", "guest", "night.guard"}

    uid = created.json()["id"]
    guard = TestClient(client.app, headers=HEADERS)
    assert login(guard, "night.guard", "a-long-passphrase").status_code == 200
    client.patch(f"/api/users/{uid}", json={"active": False})        # disabling signs them out at once
    assert guard.get("/api/me").status_code == 401
    assert login(guard, "night.guard", "a-long-passphrase").status_code == 401
    client.patch(f"/api/users/{uid}", json={"active": True, "password": "another-long-passphrase"})
    assert login(guard, "night.guard", "another-long-passphrase").status_code == 200


def test_the_last_admin_and_your_own_account_are_protected(client):
    login(client, "boss", "longpassword1")
    boss = next(u for u in client.get("/api/users").json() if u["username"] == "boss")
    assert client.patch(f"/api/users/{boss['id']}", json={"active": False}).json()["error"]["code"] == "LAST_ADMIN"
    guest = next(u for u in client.get("/api/users").json() if u["username"] == "guest")
    client.patch(f"/api/users/{guest['id']}", json={"role": "admin"})                  # now two admins
    assert client.patch(f"/api/users/{boss['id']}", json={"role": "viewer"}).json()["error"]["code"] == "SELF_LOCKOUT"


def test_audit_can_be_verified_and_tampering_shows(client):
    login(client, "boss", "longpassword1")
    assert client.get("/api/audit/verify").json()["ok"] is True
    with client.db.db:
        client.db.db.execute("UPDATE audit SET username = 'someone_else' WHERE id = 1")
    assert client.get("/api/audit/verify").json()["ok"] is False


# ----------------------------------------------------------------- scan log
def test_scan_logs_once_per_cooldown_and_keeps_snapshot_only_when_needed(client):
    add_resident(client)
    first = client.post("/api/scan", json={"image": "1,0.01,0,0"}).json()[0]
    again = client.post("/api/scan", json={"image": "1,0.01,0,0"}).json()[0]
    assert first["decision"] == "resident" and first["event_id"]
    assert again["event_id"] is None                       # same person inside the cooldown
    stranger = client.post("/api/scan", json={"image": "0,1,0,0"}).json()[0]
    assert stranger["decision"] == "unknown" and stranger["event_id"]

    events = client.get("/api/events").json()
    assert events["total"] == 2
    by_decision = {e["decision"]: e for e in events["events"]}
    assert by_decision["resident"]["access"] == "granted" and not by_decision["resident"]["has_snapshot"]
    assert by_decision["unknown"]["access"] == "denied" and by_decision["unknown"]["reason"] == "Not registered"
    assert by_decision["unknown"]["has_snapshot"]
    snapshot = client.get(f"/api/events/{by_decision['unknown']['id']}/snapshot")
    assert snapshot.status_code == 200 and snapshot.content == b"fake-crop"


def test_event_filters_stats_review_and_csv(client):
    add_resident(client, name="An", unit="302")
    client.post("/api/scan", json={"image": "1,0,0,0"})
    unknown_id = client.post("/api/scan", json={"image": "0,1,0,0"}).json()[0]["event_id"]

    assert client.get("/api/events?decision=unknown").json()["total"] == 1
    assert client.get("/api/events?q=An").json()["total"] == 1
    assert client.get("/api/events?q=302").json()["total"] == 1                 # search by unit
    assert client.get("/api/events?q=APT-").json()["total"] == 1                # ...and by ID
    assert client.get("/api/events?after_id=%d" % unknown_id).json()["total"] == 0
    stats = client.get("/api/events/stats").json()
    assert (stats["total"], stats["granted"], stats["denied"], stats["pending_review"]) == (2, 1, 1, 1)

    assert client.patch(f"/api/events/{unknown_id}", json={"reviewed": True}).json()["reviewed"]
    assert client.get("/api/events/stats").json()["pending_review"] == 0

    lines = client.get("/api/events/export.csv").text.splitlines()
    assert lines[0] == "time,camera,decision,access,reason,person,id,unit,score,reviewed" and len(lines) == 3


def test_deleting_a_person_keeps_the_log_but_drops_the_name(client):
    pid = add_resident(client)["id"]
    client.post("/api/scan", json={"image": "1,0,0,0"})
    client.delete(f"/api/people/{pid}")
    event = client.get("/api/events").json()["events"][0]
    assert event["decision"] == "resident" and event["person"] is None and event["access"] == "granted"


def test_enroll_unknown_event_into_a_resident(client, monkeypatch):
    login(client, "boss", "longpassword1")
    event_id = client.post("/api/scan", json={"image": "0,1,0,0"}).json()[0]["event_id"]
    monkeypatch.setattr(api.cv2, "imread", lambda path: np.array([0, 1, 0, 0], dtype=np.float32))
    body = {"name": "Visitor", "phone": "+84911111111", "person_type": "visitor", "unit": "9", "consent": True}
    made = client.post(f"/api/events/{event_id}/enroll", json=body)
    assert made.status_code == 201 and made.json()["code"].startswith("APT-")
    assert client.get("/api/events?reviewed=true").json()["total"] == 1
    assert client.post("/api/scan", json={"image": "0,1,0,0"}).json()[0]["person"] == "Visitor"


# ------------------------------------------------------------------ cameras
def test_laptop_camera_exists_and_is_protected(client):
    login(client, "boss", "longpassword1")
    cams = client.get("/api/cameras").json()
    assert [c["id"] for c in cams] == ["laptop"] and cams[0]["kind"] == "browser"
    assert client.delete("/api/cameras/laptop").status_code == 400


def test_add_ip_camera_hides_password_and_validates(client):
    login(client, "boss", "longpassword1")
    body = {"name": "Door", "host": "192.168.1.210", "username": "cam", "password": "s3cret!",
            "path": "stream1", "direction": "in"}
    created = client.post("/api/cameras", json=body)
    assert created.status_code == 201
    cam = created.json()
    assert "password" not in cam and cam["has_password"]
    assert cam["url"] == "rtsp://cam:***@192.168.1.210:554/stream1"
    assert "s3cret" not in client.get("/api/cameras").text
    assert "s3cret" not in client.get("/api/audit").text

    bad = client.post("/api/cameras", json={"name": "X", "host": "bad host!"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "BAD_HOST"
    assert client.post("/api/cameras", json={"host": "10.0.0.1"}).json()["error"]["field"] == "name"
    assert client.post("/api/cameras", json={**body, "port": 99999}).json()["error"]["code"] == "BAD_PORT"


def test_edit_keeps_password_when_box_is_empty_and_delete_works(client):
    login(client, "boss", "longpassword1")
    cam_id = client.post("/api/cameras", json={"name": "Door", "host": "10.0.0.5",
                                               "username": "a", "password": "pw"}).json()["id"]
    edited = client.patch(f"/api/cameras/{cam_id}", json={"name": "Main door", "password": ""}).json()
    assert edited["name"] == "Main door" and edited["has_password"]
    assert client.delete(f"/api/cameras/{cam_id}").status_code == 204
    assert [c["id"] for c in client.get("/api/cameras").json()] == ["laptop"]


def test_viewer_cannot_manage_cameras(client):
    login(client, "guest", "longpassword2")
    assert client.get("/api/cameras").status_code == 200
    assert client.post("/api/cameras", json={"name": "X", "host": "10.0.0.1"}).status_code == 403
    assert client.post("/api/cameras/test", json={"host": "10.0.0.1"}).status_code == 403


# ------------------------------------------------------------ watch list and alerts
WATCH = {"reason": "Wanted for armed robbery", "source": "City Police", "reference": "CASE-7731",
         "instructions": "Do not approach. Call 113."}


def add_criminal(client, **kw):
    login(client, "boss", "longpassword1")
    body = person_body(name="Karl Weber", person_type="criminal", unit="", watch=WATCH, images=["0,1,0,0"], **kw)
    return client.post("/api/people", json=body).json()


def test_a_criminal_scan_opens_a_critical_alert_for_staff(client):
    made = add_criminal(client)
    assert made["code"].startswith("APT-")
    scan = client.post("/api/scan", json={"image": "0,1,0,0"}).json()[0]
    assert scan["alert"] == {"level": "critical", "confidence": "confirmed"} and scan["alert_id"]
    assert scan["access"]["granted"] is False and scan["watch"]["instructions"] == "Do not approach. Call 113."

    event = client.get("/api/events?access_result=denied").json()["events"][0]
    assert event["alert"] == "critical" and event["has_snapshot"]            # a denied scan always keeps a picture
    alert = client.get("/api/alerts?status=open").json()[0]
    assert alert["level"] == "critical" and alert["person"] == "Karl Weber" and alert["reason"] == "Wanted for armed robbery"
    assert alert["instructions"] == "Do not approach. Call 113." and alert["status"] == "open"
    assert client.get(f"/api/alerts/{alert['id']}/snapshot").status_code == 200
    actions = [a["action"] for a in client.get("/api/audit").json()]
    assert {"watchlist_added", "alert_raised"} <= set(actions)


def test_acknowledging_an_alert_is_recorded_and_closes_it(client):
    add_criminal(client)
    client.post("/api/scan", json={"image": "0,1,0,0"})
    alert_id = client.get("/api/alerts?status=open").json()[0]["id"]
    done = client.post(f"/api/alerts/{alert_id}/ack", json={"note": "Police called, person left"}).json()
    assert done["status"] == "acknowledged" and done["ack_by"] == "boss" and done["ack_note"] == "Police called, person left"
    assert client.get("/api/alerts?status=open").json() == []
    assert client.get("/api/alerts?status=acknowledged").json()[0]["id"] == alert_id
    assert "alert_acknowledged" in [a["action"] for a in client.get("/api/audit").json()]


def test_residents_get_a_minimal_alert_and_nothing_else(client):
    add_criminal(client)
    client.post("/api/scan", json={"image": "0,1,0,0"})
    client.db.add_user("mrs.tran", auth.hash_password("a-long-passphrase"), "resident")
    client.post("/api/logout")
    assert login(client, "mrs.tran", "a-long-passphrase").status_code == 200

    alerts = client.get("/api/alerts?status=open").json()
    assert len(alerts) == 1 and alerts[0]["level"] == "critical"
    text = str(alerts[0])
    for secret in ("Karl", "Weber", "armed robbery", "City Police", "CASE-7731", "APT-", "person_id"):
        assert secret not in text                                              # no name, offence, source, case or ID
    assert "Do not open doors" in alerts[0]["message"]
    assert client.get(f"/api/alerts/{alerts[0]['id']}/snapshot").status_code == 200      # they do see the face
    assert client.post(f"/api/alerts/{alerts[0]['id']}/ack", json={}).status_code == 403  # but cannot dismiss it

    for path in ("/api/people", "/api/events", "/api/cameras", "/api/audit", "/api/users"):
        assert client.get(path).status_code == 403, path
    assert client.post("/api/scan", json={"image": "0,1,0,0"}).status_code == 403
    assert client.get("/api/me").json()["role"] == "resident"


def test_a_resident_account_can_be_created_and_cannot_manage_anything(client):
    login(client, "boss", "longpassword1")
    made = client.post("/api/users", json={"username": "unit302", "password": "a-long-passphrase", "role": "resident"})
    assert made.status_code == 201 and made.json()["role"] == "resident"
    assert client.post("/api/users", json={"username": "x1x", "password": "a-long-passphrase", "role": "king"}).status_code == 400


def test_a_possible_match_on_a_criminal_is_only_a_high_alert(client):
    add_criminal(client)
    weak = "0.9075,0.42,0,0"                      # similarity 0.42: recognised, but not confirmed
    scan = client.post("/api/scan", json={"image": weak}).json()[0]
    assert scan["alert"] == {"level": "high", "confidence": "possible"}
    assert client.get("/api/alerts?status=open").json()[0]["confidence"] == "possible"


def test_watch_list_details_are_masked_for_viewers_but_instructions_stay_visible(client):
    pid = add_criminal(client)["id"]
    assert client.get(f"/api/people/{pid}").json()["watch"]["source"] == "City Police"
    client.post("/api/logout")
    login(client, "guest", "longpassword2")
    watch = client.get(f"/api/people/{pid}").json()["watch"]
    assert watch["source"] == "••••" and watch["reference"] == "••••"
    assert watch["reason"] == "Wanted for armed robbery" and watch["instructions"] == "Do not approach. Call 113."


def test_watch_list_validation_over_the_api(client):
    login(client, "boss", "longpassword1")
    body = person_body(person_type="criminal", unit="", watch={"source": "Police"})
    r = client.post("/api/people", json=body)
    assert r.status_code == 400 and r.json()["error"]["field"] == "watch_reason"
    body = person_body(person_type="criminal", unit="", watch=WATCH, consent=False)
    assert client.post("/api/people", json=body).json()["error"]["code"] == "NO_CONSENT"


def test_alerts_are_sent_to_the_configured_audiences(client):
    client.cfg["alerts"]["channels"] = [{"type": "telegram", "audience": "security", "token": "t", "chat_id": "1"},
                                        {"type": "webhook", "audience": "residents", "url": "http://sms"}]
    add_criminal(client)
    client.post("/api/scan", json={"image": "0,1,0,0"})
    audiences = sorted(p["audience"] for _, p in client.sent)
    assert audiences == ["residents", "security"]
    resident_message = next(p["text"] for _, p in client.sent if p["audience"] == "residents")
    assert "Karl" not in resident_message and "robbery" not in resident_message
    assert next(p["photo"] for _, p in client.sent if p["audience"] == "residents")      # residents get the photo
