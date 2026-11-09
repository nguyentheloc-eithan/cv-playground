import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_config
from app.db import Database
from app.faces import Face
from app.recognize import RegisterError, Recognizer


class FakeEngine:
    """Stands in for the AI models: the 'image' is already the face vector."""
    def find_faces(self, image):
        return [Face(0, 0, 100, 100, 0.99, image)]

    def face_vector(self, image, face):
        return image / np.linalg.norm(image)


def make(tmp_path, customer="example"):
    cfg = load_config(customer)
    return Recognizer(cfg, FakeEngine(), Database(tmp_path / "t.db"))


def v(*numbers):
    return np.array(numbers, dtype=np.float32)


def test_customer_overrides_default():
    assert load_config()["policy"]["accept_threshold"] == 0.363
    cfg = load_config("example")
    assert cfg["policy"]["accept_threshold"] == 0.40
    assert cfg["policy"]["reject_threshold"] == 0.30  # kept from default


def test_register_then_check(tmp_path):
    r = make(tmp_path)
    r.register("An", {"unit_no": "302"}, [v(1, 0, 0, 0)])
    assert r.check(v(1, 0.01, 0, 0))[0]["decision"] == "authorized"
    assert r.check(v(1, 0.01, 0, 0))[0]["person"] == "An"
    assert r.check(v(0, 1, 0, 0))[0]["decision"] == "unknown"


def test_form_is_checked_against_customer_fields(tmp_path):
    r = make(tmp_path)
    with pytest.raises(RegisterError):
        r.register("An", {}, [v(1, 0, 0, 0)])                    # unit_no is required
    with pytest.raises(RegisterError):
        r.register("An", {"unit_no": "1", "x": "y"}, [v(1, 0, 0, 0)])  # x is not a field


def test_delete_removes_person(tmp_path):
    r = make(tmp_path)
    pid = r.register("An", {"unit_no": "302"}, [v(1, 0, 0, 0)])
    r.db.delete_person(pid)
    assert r.check(v(1, 0, 0, 0))[0]["decision"] == "unknown"
