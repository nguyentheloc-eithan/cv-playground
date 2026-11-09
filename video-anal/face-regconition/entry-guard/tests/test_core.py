import numpy as np
import pytest

from entryguard.config import load_settings
from entryguard.core.service import EnrollmentError, FaceService
from entryguard.core.types import Decision, Detection
from entryguard.store.sqlite import SqliteStore

ROOT = "config"


def test_default_and_customer_override(monkeypatch):
    monkeypatch.delenv("ENTRYGUARD_CUSTOMER", raising=False)
    s = load_settings(config_dir=ROOT)
    assert s.policy.accept_threshold == 0.363
    s = load_settings("example", config_dir=ROOT)
    assert s.policy.accept_threshold == 0.40
    assert s.policy.reject_threshold == 0.30  # inherited from default
    assert [f.key for f in s.person_schema] == ["unit_no", "phone"]  # lists replace


def test_env_override(monkeypatch):
    monkeypatch.setenv("ENTRYGUARD__POLICY__ACCEPT_THRESHOLD", "0.5")
    assert load_settings(config_dir=ROOT).policy.accept_threshold == 0.5


def test_bad_thresholds(monkeypatch):
    monkeypatch.setenv("ENTRYGUARD__POLICY__REJECT_THRESHOLD", "0.9")
    with pytest.raises(Exception):
        load_settings(config_dir=ROOT)


class FakeDetector:
    name = "fake"
    def detect(self, image):
        return [Detection((0, 0, 100, 100), 0.99, ())]


class FakeEmbedder:
    name, space_id = "fake", "fake_4"
    def embed(self, image, det):
        v = image.flatten()[:4].astype(np.float32)
        return v / np.linalg.norm(v)


class FakeLive:
    name = "fake"
    def score(self, image, det):
        return 1.0


def img(*v):
    return np.array(v, dtype=np.float32).reshape(1, 4)


def make(tmp_path, customer="example"):
    s = load_settings(customer, config_dir=ROOT)
    return FaceService(s, FakeDetector(), FakeEmbedder(), FakeLive(),
                       SqliteStore(tmp_path / "t.db"))


def test_enroll_and_check(tmp_path):
    svc = make(tmp_path)
    p = svc.enroll("An", {"unit_no": "302"}, [img(1, 0, 0, 0)])
    r = svc.check_image(img(1, 0.01, 0, 0))[0]
    assert r.decision is Decision.AUTHORIZED and r.person.id == p.id
    assert svc.check_image(img(0, 1, 0, 0))[0].decision is Decision.UNKNOWN


def test_required_field_and_unknown_field(tmp_path):
    svc = make(tmp_path)
    with pytest.raises(EnrollmentError) as e:
        svc.enroll("An", {}, [img(1, 0, 0, 0)])
    assert e.value.code == "MISSING_FIELD"
    with pytest.raises(EnrollmentError) as e:
        svc.enroll("An", {"unit_no": "1", "x": "y"}, [img(1, 0, 0, 0)])
    assert e.value.code == "UNKNOWN_FIELD"


def test_disabled_person_not_authorized(tmp_path):
    svc = make(tmp_path)
    p = svc.enroll("An", {"unit_no": "302"}, [img(1, 0, 0, 0)])
    svc.store.set_status(p.id, "disabled")
    assert svc.check_image(img(1, 0, 0, 0))[0].decision is Decision.UNKNOWN
