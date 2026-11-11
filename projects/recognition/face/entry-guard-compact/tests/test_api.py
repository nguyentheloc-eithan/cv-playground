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
    recognizer.cfg["security"]["step_up"]["enabled"] = False      # the step-up tests switch it on (see client_su)
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


def test_quality_feedback_is_plain_json_even_with_float32_detector_output(client):
    login(client, "boss", "longpassword1")
    reply = client.post("/api/quality", json={"image": "1,0,0,0,20"})        # a turned head
    assert reply.status_code == 200
    body = reply.json()
    assert body["bbox"] and body["yaw"] == 0.5 and body["ok"] is False and body["code"] == "FACE_ANGLE"
    assert client.post("/api/quality", json={"image": "1,0,0,0,0"}).json()["yaw"] == 0.0


# ------------------------------------------------- step-up confirmation (PIN / face / password)
@pytest.fixture
def client_su(client):
    client.cfg["security"]["step_up"]["enabled"] = True
    return client


def straight():
    return "1,0,0,0,0"


def turned():
    return "1,0,0,0,20"                    # same face, head turned (nose shifted: yaw 0.5)


def confirm(client, action, method="password", **body):
    body = body or ({"password": "longpassword1"} if method == "password" else {})
    return client.post(f"/api/step-up/{method}", json={"action": action, **body})


def setup_pin(client, pin="482915"):
    return client.post("/api/me/security/pin", json={"pin": pin, "current_password": "longpassword1"})


def setup_face(client):
    return client.post("/api/me/security/face", json={"images": [straight()] * 3, "current_password": "longpassword1"})


def test_a_risky_action_needs_a_confirmation_and_the_password_is_the_fallback(client_su):
    pid = add_resident(client_su)["id"]
    blocked = client_su.delete(f"/api/people/{pid}")
    assert blocked.status_code == 403
    err = blocked.json()["error"]
    assert err["code"] == "STEP_UP_REQUIRED" and err["action"] == "person_delete" and err["label"] == "Delete a person"
    assert err["methods"] == ["password"] and err["pin_length"] == 6                 # nothing set up yet: only the password
    assert client_su.get("/api/people").json()[0]["id"] == pid                       # and nothing was deleted

    token = confirm(client_su, "person_delete").json()["token"]
    assert client_su.delete(f"/api/people/{pid}", headers={"X-Step-Up": token}).status_code == 204


def test_a_confirmation_works_once_only_for_its_own_action_and_user(client_su):
    pid = add_resident(client_su)["id"]
    other = add_resident(client_su, name="Bo", images=["0,0,1,0"])["id"]
    wrong_action = confirm(client_su, "camera_delete").json()["token"]
    assert client_su.delete(f"/api/people/{pid}", headers={"X-Step-Up": wrong_action}).status_code == 403
    token = confirm(client_su, "person_delete").json()["token"]
    assert client_su.delete(f"/api/people/{pid}", headers={"X-Step-Up": token}).status_code == 204
    replay = client_su.delete(f"/api/people/{other}", headers={"X-Step-Up": token})      # the same token again
    assert replay.status_code == 403 and replay.json()["error"]["code"] == "STEP_UP_REQUIRED"
    assert client_su.delete(f"/api/people/{other}", headers={"X-Step-Up": "made-up-token"}).status_code == 403
    assert confirm(client_su, "not_an_action").status_code == 400


def test_a_wrong_password_does_not_confirm_and_repeated_failures_lock(client_su):
    login(client_su, "boss", "longpassword1")
    for _ in range(client_su.cfg["security"]["max_failed_logins"]):
        assert confirm(client_su, "person_delete", password="nope").status_code == 401
    locked = confirm(client_su, "person_delete")                                    # even the right one is refused now
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "ACCOUNT_LOCKED"
    assert {"step_up_failed", "step_up_locked"} <= {a["action"] for a in client_su.db.list_audit()}


def test_only_the_protected_actions_ask_for_confirmation(client_su):
    pid = add_resident(client_su)["id"]                                             # registering a resident: no prompt
    assert client_su.patch(f"/api/people/{pid}", json={"unit": "410"}).status_code == 200     # editing one: no prompt
    assert client_su.post("/api/scan", json={"image": "1,0,0,0"}).status_code == 200
    assert client_su.post("/api/users", json={"username": "x.y", "password": "a-long-passphrase", "role": "viewer"}).status_code == 403
    assert client_su.get("/api/events/export.csv").status_code == 403
    cam = client_su.post("/api/cameras", json={"name": "Door", "host": "10.0.0.5"}).json()["id"]   # adding: no prompt
    assert client_su.delete(f"/api/cameras/{cam}").status_code == 403                  # deleting: prompt


def test_watch_list_changes_are_protected_from_start_to_finish(client_su):
    login(client_su, "boss", "longpassword1")
    body = person_body(person_type="criminal", unit="", watch=WATCH, images=["0,1,0,0"])
    assert client_su.post("/api/people", json=body).json()["error"]["action"] == "watchlist_change"
    token = confirm(client_su, "watchlist_change").json()["token"]
    made = client_su.post("/api/people", json=body, headers={"X-Step-Up": token})
    assert made.status_code == 201
    pid = made.json()["id"]
    # even switching a watch-list person off, or editing them, needs a fresh confirmation
    assert client_su.patch(f"/api/people/{pid}", json={"status": "disabled"}).status_code == 403
    token = confirm(client_su, "watchlist_change").json()["token"]
    assert client_su.patch(f"/api/people/{pid}", json={"status": "disabled"}, headers={"X-Step-Up": token}).status_code == 200
    # turning an ordinary resident INTO a criminal is protected as well
    resident = add_resident(client_su, name="Cy", images=["0,0,0,1"])["id"]
    assert client_su.patch(f"/api/people/{resident}", json={"person_type": "criminal", "watch": WATCH}).status_code == 403


def test_pin_setup_rules_and_confirmation(client_su):
    login(client_su, "boss", "longpassword1")
    assert setup_pin(client_su, "12").json()["error"]["code"] == "WEAK_PIN"
    assert setup_pin(client_su, "111111").json()["error"]["code"] == "WEAK_PIN"
    assert setup_pin(client_su, "123456").json()["error"]["code"] == "WEAK_PIN"
    bad = client_su.post("/api/me/security/pin", json={"pin": "482915", "current_password": "wrong"})
    assert bad.json()["error"]["code"] == "WRONG_PASSWORD"                          # setting a PIN needs the password
    state = setup_pin(client_su).json()
    assert state["pin"] == {"set": True, "enabled": True} and state["methods"] == ["pin", "password"]
    assert "482915" not in str(client_su.db.get_pin_hash(1)) and "482915" not in client_su.get("/api/audit").text

    pid = add_resident(client_su)["id"]
    err = client_su.delete(f"/api/people/{pid}").json()["error"]
    assert err["methods"] == ["pin", "password"] and err["preferred"] == "pin"
    assert confirm(client_su, "person_delete", "pin", pin="000111").status_code == 401
    token = confirm(client_su, "person_delete", "pin", pin="482915").json()["token"]
    assert client_su.delete(f"/api/people/{pid}", headers={"X-Step-Up": token}).status_code == 204


def test_the_pin_switch_turns_it_off_and_back_on(client_su):
    login(client_su, "boss", "longpassword1")
    assert client_su.patch("/api/me/security", json={"pin_enabled": True}).json()["error"]["code"] == "NOT_SET_UP"
    setup_pin(client_su)
    assert client_su.patch("/api/me/security", json={"pin_enabled": False}).json()["error"]["code"] == "WRONG_PASSWORD"
    off = client_su.patch("/api/me/security", json={"pin_enabled": False, "current_password": "longpassword1"}).json()
    assert off["pin"] == {"set": True, "enabled": False} and off["methods"] == ["password"]
    assert confirm(client_su, "person_delete", "pin", pin="482915").status_code == 401           # off means off
    on = client_su.patch("/api/me/security", json={"pin_enabled": True}).json()
    assert on["pin"]["enabled"] and on["methods"][0] == "pin"
    gone = client_su.request("DELETE", "/api/me/security/pin", json={"current_password": "longpassword1"}).json()
    assert gone["pin"] == {"set": False, "enabled": False}


def test_face_enrolment_needs_the_password_and_three_good_photos(client_su):
    login(client_su, "boss", "longpassword1")
    assert client_su.post("/api/me/security/face", json={"images": [straight()] * 2, "current_password": "longpassword1"}).json()["error"]["code"] == "PHOTO_COUNT"
    assert client_su.post("/api/me/security/face", json={"images": [straight()] * 3, "current_password": "x"}).json()["error"]["code"] == "WRONG_PASSWORD"
    assert client_su.post("/api/me/security/face", json={"images": [straight(), straight(), turned()], "current_password": "longpassword1"}).json()["error"]["code"] == "FACE_ANGLE"
    state = setup_face(client_su).json()
    assert state["face"] == {"enrolled": True, "enabled": True} and state["methods"] == ["face", "password"]


def test_face_confirmation_needs_the_right_face_turning_its_head(client_su):
    pid = add_resident(client_su)["id"]
    client_su.cfg["security"]["max_failed_logins"] = 50          # this test fails on purpose many times
    setup_face(client_su)
    assert client_su.delete(f"/api/people/{pid}").json()["error"]["preferred"] == "face"

    def face(*images):
        return confirm(client_su, "person_delete", "face", images=list(images))
    assert face(straight()).json()["error"]["message"].startswith("Look straight at the camera, then turn your head slightly")   # a still photo is not enough
    assert face(straight(), straight()).json()["error"]["message"] == "Turn your head slightly to the left or right"
    assert face("0,1,0,0,0", "0,1,0,0,20").json()["error"]["message"] == "Face not recognised"             # someone else
    assert face("1,0,0,0,20", "1,0,0,0,20").json()["error"]["message"] == "Look straight at the camera"     # started turned
    assert face(straight(), "0,1,0,0,20").json()["error"]["message"] == "Face not recognised"                # swapped in a different face
    ok = face(straight(), turned())
    assert ok.status_code == 200 and ok.json()["token"]
    assert client_su.delete(f"/api/people/{pid}", headers={"X-Step-Up": ok.json()["token"]}).status_code == 204
    assert client_su.cfg and any(a["action"] == "step_up_ok" for a in client_su.db.list_audit())


def test_head_turn_can_be_switched_off_in_the_config(client_su):
    login(client_su, "boss", "longpassword1")
    setup_face(client_su)
    client_su.cfg["security"]["step_up"]["require_head_turn"] = False
    assert confirm(client_su, "person_delete", "face", images=[straight()]).status_code == 200


def test_the_face_switch_and_removing_face_data(client_su):
    login(client_su, "boss", "longpassword1")
    setup_face(client_su)
    assert confirm(client_su, "person_delete", "face", images=[straight(), turned()]).status_code == 200
    off = client_su.patch("/api/me/security", json={"face_enabled": False, "current_password": "longpassword1"}).json()
    assert off["face"] == {"enrolled": True, "enabled": False}
    assert confirm(client_su, "person_delete", "face", images=[straight(), turned()]).json()["error"]["code"] == "NOT_SET_UP"
    client_su.request("DELETE", "/api/me/security/face", json={"current_password": "longpassword1"})
    assert client_su.get("/api/me/security").json()["face"] == {"enrolled": False, "enabled": False}
    assert client_su.db.face_vectors(1) == []                                          # the template is really gone


def test_the_last_used_method_is_offered_first(client_su):
    login(client_su, "boss", "longpassword1")
    setup_pin(client_su); setup_face(client_su)
    assert client_su.get("/api/me/security").json()["methods"] == ["face", "pin", "password"]
    confirm(client_su, "person_delete", "pin", pin="482915")
    assert client_su.get("/api/me/security").json()["methods"] == ["pin", "face", "password"]


def test_step_up_can_be_disabled_or_relaxed_per_customer(client_su):
    pid = add_resident(client_su, name="Dee", images=["0,0,1,0"])["id"]
    del client_su.cfg["security"]["step_up"]["actions"]["person_delete"]              # relax one action
    assert client_su.delete(f"/api/people/{pid}").status_code == 204
    client_su.cfg["security"]["step_up"]["enabled"] = False                           # or switch the feature off
    assert client_su.get("/api/events/export.csv").status_code == 200


def test_security_settings_are_private_to_each_user_and_need_a_session(client_su):
    login(client_su, "boss", "longpassword1")
    setup_pin(client_su)
    client_su.post("/api/logout")
    assert client_su.get("/api/me/security").status_code == 401
    login(client_su, "guest", "longpassword2")
    assert client_su.get("/api/me/security").json()["pin"] == {"set": False, "enabled": False}
    pid = client_su.db.add_person({"name": "Zed", "phone": "+84900000009", "unit": "1", "person_type": "resident", "fields": {}},
                                  [np.array([0, 0, 0, 1], dtype=np.float32)], [b"jpg"], "v1")
    token = client_su.post("/api/step-up/password", json={"action": "person_delete", "password": "longpassword2"}).json()["token"]
    assert client_su.delete(f"/api/people/{pid}", headers={"X-Step-Up": token}).status_code == 403   # a confirmation never grants a role


# ------------------------------------------------------------------ sign in with the face
def enable_face_login(client):
    """boss enrols a face (which turns Face authentication on, and with it face sign-in), then signs out."""
    login(client, "boss", "longpassword1")
    r = setup_face(client)
    client.post("/api/logout")
    return r


def face_sign_in(client, username="boss", *images):
    return client.post("/api/login/face", json={"username": username, "images": list(images) or [straight(), turned()]})


def test_face_sign_in_follows_the_single_face_authentication_switch(client):
    login(client, "boss", "longpassword1")
    assert client.get("/api/me/security").json()["face_login"] == {"available": True}       # there is no second switch
    setup_face(client)
    client.post("/api/logout")
    assert face_sign_in(client).status_code == 200                                         # enrolled = face works for sign-in at once
    client.post("/api/logout")
    login(client, "boss", "longpassword1")
    client.patch("/api/me/security", json={"face_enabled": False, "current_password": "longpassword1"})
    client.post("/api/logout")
    refused = face_sign_in(client)                                                         # switched off: no face sign-in either
    assert refused.status_code == 401 and "Face authentication is not switched on" in refused.json()["error"]["message"]
    login(client, "boss", "longpassword1")
    client.patch("/api/me/security", json={"face_enabled": True})                          # back on, no password needed
    client.post("/api/logout")
    assert face_sign_in(client).status_code == 200
    client.request("DELETE", "/api/me/security/face", json={"current_password": "longpassword1"})
    client.post("/api/logout")
    assert face_sign_in(client).status_code == 401                                         # no face data, no face sign-in


def test_signing_in_with_the_right_face_turning_the_head(client):
    enable_face_login(client)
    assert client.get("/api/me").status_code == 401
    ok = face_sign_in(client)
    assert ok.status_code == 200 and ok.json() == {"username": "boss", "role": "admin"}
    assert client.get("/api/me").json()["username"] == "boss"                             # the session cookie is set
    assert any(a["action"] == "login" and a["detail"].get("method") == "face" for a in client.db.list_audit())


def test_face_sign_in_refuses_other_faces_photos_and_accounts_without_it(client):
    enable_face_login(client)
    assert face_sign_in(client, "boss", "0,1,0,0,0", "0,1,0,0,20").status_code == 401        # someone else's face
    still = face_sign_in(client, "boss", straight())                                       # a photo: one still picture
    assert still.status_code == 400 and still.json()["error"]["code"] == "FACE_POSE"
    assert face_sign_in(client, "boss", straight(), straight()).json()["error"]["code"] == "FACE_POSE"   # never turned
    assert client.get("/api/me").status_code == 401
    # an account that did not switch it on, and a user that does not exist, give the SAME answer as a wrong face
    wrong_face = face_sign_in(client, "boss", "0,1,0,0,0", "0,1,0,0,20")
    guest = face_sign_in(client, "guest")
    nobody = face_sign_in(client, "nobody")
    assert (guest.status_code, nobody.status_code) == (401, 401)
    assert guest.json()["error"] == nobody.json()["error"] == wrong_face.json()["error"]


def test_face_sign_in_failures_lock_the_account_like_the_password(client):
    enable_face_login(client)
    for _ in range(client.cfg["security"]["max_failed_logins"]):
        assert face_sign_in(client, "boss", "0,1,0,0,0", "0,1,0,0,20").status_code == 401
    locked = face_sign_in(client)                                                          # even the right face is refused now
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "ACCOUNT_LOCKED"
    # the face lock is its OWN lock: it neither blocks the password nor can be used to lock someone out of it
    assert login(client, "boss", "longpassword1").status_code == 200


def test_face_sign_in_respects_disabled_users_and_the_global_switch(client):
    enable_face_login(client)
    login(client, "boss", "longpassword1")
    client.cfg["security"]["face_login"]["enabled"] = False
    assert face_sign_in(client).status_code == 404 and client.post("/api/login/face/quality", json={"image": straight()}).status_code == 404
    assert client.get("/api/config").json()["face_login"] is False
    client.cfg["security"]["face_login"]["enabled"] = True
    client.db.update_user(1, active=False)                                                 # a disabled account cannot sign in
    client.post("/api/logout")
    assert face_sign_in(client).status_code == 401


def test_the_public_sign_in_camera_feedback_is_rate_limited_and_private(client):
    assert client.get("/api/config").json()["face_login"] is True and client.get("/api/config").json()["head_turn"] is True
    first = client.post("/api/login/face/quality", json={"image": turned()})              # no session needed
    assert first.status_code == 200 and first.json()["yaw"] == 0.5 and "person" not in first.json()
    codes = [client.post("/api/login/face/quality", json={"image": straight()}).status_code for _ in range(30)]
    assert 429 in codes                                                                    # a flood is slowed down


# ---------------------------------------------------------- fixing the photos of a registered person
def photo_ids(client, pid):
    return [p["id"] for p in client.get(f"/api/people/{pid}").json()["photos"]]


def test_replacing_a_wrong_photo_changes_who_is_recognised(client):
    pid = add_criminal(client)["id"]                                  # registered with the WRONG picture ("0,1,0,0")
    assert client.post("/api/check", json={"image": "0,1,0,0"}).json()[0]["person"] == "Karl Weber"
    old_ids = photo_ids(client, pid)
    result = client.post(f"/api/people/{pid}/photos", json={"images": ["0,0,0,1"], "replace": True})
    assert result.status_code == 200
    assert client.post("/api/check", json={"image": "0,1,0,0"}).json()[0]["decision"] == "unknown"      # the wrong face is gone
    right = client.post("/api/check", json={"image": "0,0,0,1"}).json()[0]
    assert right["person"] == "Karl Weber" and right["alert"]["level"] == "critical"                   # the right one now alerts
    new_ids = photo_ids(client, pid)
    assert len(new_ids) == 1 and not set(old_ids) & set(new_ids)
    assert client.get(f"/api/people/{pid}/photos/{new_ids[0]}").status_code == 200
    assert client.get(f"/api/people/{pid}/photo").status_code == 200
    assert "person_photos_changed" in [a["action"] for a in client.get("/api/audit").json()]


def test_adding_and_removing_single_photos_and_keeping_the_last(client):
    pid = add_resident(client)["id"]
    assert client.post(f"/api/people/{pid}/photos", json={"images": ["0.95,0.3,0,0", "0.9,0,0.4,0"], "replace": False}).status_code == 200
    ids = photo_ids(client, pid)
    assert len(ids) == 3
    assert client.delete(f"/api/people/{pid}/photos/{ids[0]}").status_code == 200
    assert client.delete(f"/api/people/{pid}/photos/{ids[1]}").status_code == 200
    last = client.delete(f"/api/people/{pid}/photos/{ids[2]}")
    assert last.status_code == 400 and last.json()["error"]["code"] == "LAST_PHOTO"           # never leave a person faceless
    assert len(photo_ids(client, pid)) == 1
    assert client.delete(f"/api/people/{pid}/photos/99999").status_code == 400


def test_new_photos_are_checked_and_cannot_steal_another_persons_face(client):
    a = add_resident(client, name="An", images=["1,0,0,0"])["id"]
    add_resident(client, name="Bo", images=["0,0,1,0"])
    clash = client.post(f"/api/people/{a}/photos", json={"images": ["0,0,1,0"], "replace": True})   # Bo's face
    assert clash.status_code == 400 and clash.json()["error"]["code"] == "DUPLICATE_FACE" and "Bo" in clash.json()["error"]["message"]
    assert client.post(f"/api/people/{a}/photos", json={"images": ["1,0.05,0,0"], "replace": True}).status_code == 200   # their own face is fine
    assert client.post(f"/api/people/{a}/photos", json={"images": []}).json()["error"]["code"] == "PHOTO_COUNT"
    blurry = client.post(f"/api/people/{a}/photos", json={"images": ["1,0,0,0,40"]})                   # head turned far: not a usable photo
    assert blurry.json()["error"]["code"] == "FACE_ANGLE" and blurry.json()["error"]["field"] == "photos[1]"
    assert len(photo_ids(client, a)) == 1                                                              # failures changed nothing


def test_changing_photos_needs_admin_and_a_confirmation(client_su):
    pid = add_resident(client_su)["id"]
    blocked = client_su.post(f"/api/people/{pid}/photos", json={"images": ["0,0,0,1"]})
    assert blocked.status_code == 403 and blocked.json()["error"]["action"] == "person_photos"
    token = confirm(client_su, "person_photos").json()["token"]
    assert client_su.post(f"/api/people/{pid}/photos", json={"images": ["0,0,0,1"]}, headers={"X-Step-Up": token}).status_code == 200
    only = photo_ids(client_su, pid)[0]
    assert client_su.delete(f"/api/people/{pid}/photos/{only}").status_code == 403                    # removing needs its OWN confirmation
    token = confirm(client_su, "person_photos").json()["token"]
    assert client_su.delete(f"/api/people/{pid}/photos/{only}", headers={"X-Step-Up": token}).json()["error"]["code"] == "LAST_PHOTO"
    client_su.post("/api/logout")
    login(client_su, "guest", "longpassword2")
    assert client_su.post(f"/api/people/{pid}/photos", json={"images": ["0,0,1,0"]}).status_code == 403


def test_a_small_head_turn_is_enough(client_su):
    login(client_su, "boss", "longpassword1")
    setup_face(client_su)
    small = "1,0,0,0,10"                                                                    # yaw 0.25: a small, natural turn
    assert confirm(client_su, "person_delete", "face", images=[straight(), small]).status_code == 200
    tiny = "1,0,0,0,4"                                                                     # yaw 0.1: barely moved
    assert confirm(client_su, "person_delete", "face", images=[straight(), tiny]).json()["error"]["message"] == "Turn your head slightly to the left or right"


def test_failed_face_sign_ins_explain_themselves_to_admins_only(client):
    login(client, "boss", "longpassword1")
    setup_face(client)
    client.patch("/api/me/security", json={"face_enabled": False, "current_password": "longpassword1"})   # face enrolled but switched OFF
    client.post("/api/logout")
    refused = face_sign_in(client, "boss")                       # the right face
    assert refused.status_code == 401
    message = refused.json()["error"]["message"]
    assert "Face authentication is not switched on" in message and "password" in message   # tells the person what to check
    assert face_sign_in(client, "nobody").json()["error"]["message"] == message             # ...and is identical for everyone
    login(client, "boss", "longpassword1")
    client.patch("/api/me/security", json={"face_enabled": True})
    client.post("/api/logout")
    face_sign_in(client, "boss", "0,1,0,0,0", "0,1,0,0,20")                                  # switched on, but a wrong face
    login(client, "boss", "longpassword1")
    failures = [a["detail"] for a in client.get("/api/audit").json() if a["action"] == "login_failed" and a["detail"].get("method") == "face"]
    reasons = [f["reason"] for f in reversed(failures)]
    assert reasons == ["face_authentication_not_switched_on", "no_such_user", "face_not_matching"]
    assert failures[0]["scores"] == [0.0, 0.0]                                              # the match scores, for tuning


def test_a_lockout_can_be_cleared_from_the_computer(client):
    enable_face_login(client)
    for _ in range(client.cfg["security"]["max_failed_logins"]):
        face_sign_in(client, "boss", "0,1,0,0,0", "0,1,0,0,20")
        client.post("/api/login", json={"username": "boss", "password": "wrong-password"})
    assert face_sign_in(client).status_code == 429 and login(client, "boss", "longpassword1").status_code == 429
    assert client.db.clear_failed_logins("boss") >= 10
    assert face_sign_in(client).status_code == 200                                           # both work again at once
    assert login(client, "boss", "longpassword1").status_code == 200
