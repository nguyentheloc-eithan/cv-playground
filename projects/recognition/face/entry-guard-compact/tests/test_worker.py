"""Live IP camera tests. A fake capture stands in for the RTSP stream (no camera needed)."""
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
from app.config import load_config
from app.db import Database
from app.faces import Face
from app.recognize import Recognizer


class FakeCapture:
    """Pretends to be cv2.VideoCapture: `frames` pictures, then the stream ends (or never ends)."""
    def __init__(self, opened=True, frames=None):
        self.opened, self.left = opened, frames

    def isOpened(self):
        return self.opened

    def read(self):
        if self.left is not None:
            if self.left <= 0:
                return False, None
            self.left -= 1
        time.sleep(0.02)
        return True, np.full((360, 640, 3), 80, np.uint8)

    def release(self):
        pass

    def set(self, *args):
        pass


class FaceEngine:
    """Always sees one face and always the same vector, whatever the picture is."""
    vector = np.array([1, 0, 0, 0], dtype=np.float32)

    def find_faces(self, image):
        row = np.array([50, 50, 100, 100, 70, 80, 110, 80, 90, 100, 75, 120, 105, 120, 0.99])
        return [Face(50, 50, 100, 100, 0.99, row)]

    def face_vector(self, image, face):
        return self.vector

    def sharpness(self, image, face):
        return 999.0

    def to_jpeg(self, image):
        return b"jpg"

    def crop_jpeg(self, image, bbox):
        return b"crop"


def build(tmp_path, opener, reachable=lambda host, port: True):
    cfg = load_config("example")
    db = Database(tmp_path / "t.db", tmp_path / "photos")
    recognizer = Recognizer(cfg, FaceEngine(), db)
    db.add_user("boss", auth.hash_password("longpassword1"), "admin")
    app = api.create_app(cfg, recognizer, db, b"s" * 32, opener=opener, reachable=reachable)
    client = TestClient(app, headers={"X-Requested-With": "entryguard"})
    client.post("/api/login", json={"username": "boss", "password": "longpassword1"})
    return client, app, db


def add_camera(client, **extra):
    body = {"name": "Door", "host": "192.168.1.210", "username": "admin", "password": "pw",
            "path": "/h264/ch1/main/av_stream", **extra}
    return client.post("/api/cameras", json=body).json()["id"]


def wait_for(check, seconds=5):
    end = time.time() + seconds
    while time.time() < end:
        value = check()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("timed out waiting")


@pytest.fixture
def rig(tmp_path):
    made = []

    def make(opener, reachable=lambda host, port: True):
        client, app, db = build(tmp_path, opener, reachable)
        made.append(app)
        return client, app, db
    yield make
    for app in made:
        app.state.workers.stop_all()


def test_live_status_and_stream(rig):
    client, app, db = rig(lambda cam: FakeCapture())
    cam_id = add_camera(client)
    status = wait_for(lambda: (s := client.get(f"/api/cameras/{cam_id}/status").json())["state"] == "live"
                      and s["size"] and s)
    assert status["size"] == [640, 360] and status["error"] == ""

    with client.stream("GET", f"/api/cameras/{cam_id}/stream") as response:
        assert response.headers["content-type"].startswith("multipart/x-mixed-replace")
        chunk = next(response.iter_bytes())
        assert chunk.startswith(b"--frame") and b"image/jpeg" in chunk


def test_unreachable_camera_reports_reconnecting(rig):
    client, app, db = rig(lambda cam: FakeCapture(opened=False))
    cam_id = add_camera(client)
    status = wait_for(lambda: (s := client.get(f"/api/cameras/{cam_id}/status").json())["state"] == "reconnecting" and s)
    assert "Cannot connect" in status["error"]


def test_stream_that_ends_reconnects(rig):
    opened = []

    def opener(cam):
        opened.append(1)
        return FakeCapture(frames=5 if len(opened) == 1 else None)   # first stream dies after 5 pictures
    client, app, db = rig(opener)
    cam_id = add_camera(client)
    client.get(f"/api/cameras/{cam_id}/status")          # viewing the camera starts its worker
    wait_for(lambda: len(opened) >= 2, seconds=8)
    assert wait_for(lambda: client.get(f"/api/cameras/{cam_id}/status").json()["state"] == "live")


def test_live_scan_logs_events(rig):
    client, app, db = rig(lambda cam: FakeCapture())
    db.add_person({"name": "An", "phone": "+84900000001", "unit": "1", "person_type": "resident", "fields": {}},
                  [FaceEngine.vector], [b"jpg"], "v1")
    cam_id = add_camera(client)
    status = wait_for(lambda: (s := client.get(f"/api/cameras/{cam_id}/status").json())["events"] and s)
    assert status["events"][0]["decision"] == "resident" and status["events"][0]["person"] == "An"
    assert client.get(f"/api/cameras/{cam_id}/status?since={status['seq']}").json()["events"] == []
    logged = client.get("/api/events").json()
    assert logged["total"] == 1 and logged["events"][0]["camera_id"] == cam_id


def test_only_enabled_ip_cameras_have_a_live_view(rig):
    client, app, db = rig(lambda cam: FakeCapture())
    assert client.get("/api/cameras/laptop/status").status_code == 404      # browser camera
    assert client.get("/api/cameras/nope/status").status_code == 404
    cam_id = add_camera(client, enabled=False)
    assert client.get(f"/api/cameras/{cam_id}/status").status_code == 404   # disabled
    assert client.get("/api/cameras/%s/status" % cam_id).json()["error"]["code"] == "NO_ENABLED_IP_CAMERA_WITH_THIS_ID"


def test_live_view_needs_login(rig):
    client, app, db = rig(lambda cam: FakeCapture())
    cam_id = add_camera(client)
    client.post("/api/logout")
    assert client.get(f"/api/cameras/{cam_id}/status").status_code == 401
    assert client.get(f"/api/cameras/{cam_id}/stream").status_code == 401


# ------------------------------------------------- stream path catalog, templates, discovery
def test_presets_catalog_has_many_brands_with_placeholders(rig):
    client, app, db = rig(lambda cam: FakeCapture())
    data = client.get("/api/camera-presets").json()
    brands = {b["brand"].split(" (")[0] for b in data["brands"]}
    assert {"Hikvision", "Dahua", "Reolink", "TP-Link Tapo", "Axis", "Generic ONVIF / unknown brand"} <= brands
    paths = [s["path"] for b in data["brands"] for s in b["streams"]]
    assert len(paths) >= 25 and "/Streaming/Channels/{ch}01" in paths
    assert data["templates"] == []


def test_custom_templates_can_be_saved_listed_replaced_and_deleted(rig):
    client, app, db = rig(lambda cam: FakeCapture())
    body = {"name": "Warehouse cams", "path": "cam/live?x=1", "port": 8554, "username": "viewer", "transport": "udp"}
    assert client.post("/api/camera-templates", json=body).status_code == 201
    client.post("/api/camera-templates", json={**body, "path": "/other"})          # same name: replaced
    templates = client.get("/api/camera-presets").json()["templates"]
    assert len(templates) == 1 and templates[0]["path"] == "/other" and templates[0]["port"] == 8554
    assert client.post("/api/camera-templates", json={**body, "name": " "}).status_code == 400
    assert client.delete(f"/api/camera-templates/{templates[0]['id']}").status_code == 204
    assert client.get("/api/camera-presets").json()["templates"] == []


def test_custom_path_with_query_is_kept_as_typed(rig):
    client, app, db = rig(lambda cam: FakeCapture())
    cam = client.post("/api/cameras", json={"name": "Odd", "host": "10.0.0.9",
                                            "path": "cam/realmonitor?channel=2&subtype=1"}).json()
    assert cam["url"] == "rtsp://10.0.0.9:554/cam/realmonitor?channel=2&subtype=1"


def test_discover_finds_the_working_paths(rig):
    working = {"/Streaming/Channels/101", "/stream1"}
    client, app, db = rig(lambda cam: FakeCapture(opened=cam["path"] in working))
    client.post("/api/camera-templates", json={"name": "mine", "path": "/my/own/path"})
    result = client.post("/api/cameras/discover", json={"host": "10.0.0.9", "username": "a", "password": "b"}).json()
    assert result["reachable"] and result["tried"] >= 25
    assert [h["path"] for h in result["found"]] == ["/Streaming/Channels/101", "/stream1"]   # catalog order
    assert result["found"][0]["width"] == 640

    working.add("/my/own/path")      # user templates are tried too
    again = client.post("/api/cameras/discover", json={"host": "10.0.0.9"}).json()
    assert "/my/own/path" in [h["path"] for h in again["found"]]


def test_discover_expands_the_channel_number(rig):
    seen = []
    client, app, db = rig(lambda cam: (seen.append(cam["path"]), FakeCapture(opened=False))[1])
    client.post("/api/cameras/discover?channel=3", json={"host": "10.0.0.9"})
    assert "/Streaming/Channels/301" in seen and "/h264Preview_03_main" in seen


def test_discover_stops_quickly_when_the_host_is_unreachable(rig):
    called = []
    client, app, db = rig(lambda cam: called.append(1) or FakeCapture(), reachable=lambda host, port: False)
    result = client.post("/api/cameras/discover", json={"host": "10.0.0.9"}).json()
    assert result == {"reachable": False, "tried": 0, "found": []} and called == []


def test_viewer_cannot_use_templates_or_discovery(rig):
    client, app, db = rig(lambda cam: FakeCapture())
    db.add_user("guest", auth.hash_password("longpassword2"), "viewer")
    client.post("/api/logout")
    client.post("/api/login", json={"username": "guest", "password": "longpassword2"})
    assert client.get("/api/camera-presets").status_code == 200
    assert client.post("/api/camera-templates", json={"name": "x"}).status_code == 403
    assert client.post("/api/cameras/discover", json={"host": "10.0.0.9"}).status_code == 403


def test_test_and_discover_do_not_need_a_camera_name(rig):
    client, app, db = rig(lambda cam: FakeCapture(opened=cam["path"] == "/stream1"))
    form = {"name": "", "host": "10.0.0.9", "port": "", "path": "", "username": "", "password": ""}   # an untouched form
    assert client.post("/api/cameras/test", json={**form, "path": "/stream1"}).json()["ok"] is True
    found = client.post("/api/cameras/discover", json=form).json()["found"]
    assert [h["path"] for h in found] == ["/stream1"]
