"""python -m solavis.sim --package demo   ->   http://127.0.0.1:8101"""
import argparse

import uvicorn

from ..settings import load_package
from .app import create_app

p = argparse.ArgumentParser()
p.add_argument("--package", default="demo")
a = p.parse_args()
port = load_package(a.package).get("simulator", {}).get("port", 8101)
print(f"Camera simulator on http://127.0.0.1:{port}")
uvicorn.run(create_app(a.package), host="127.0.0.1", port=port, log_level="warning")
