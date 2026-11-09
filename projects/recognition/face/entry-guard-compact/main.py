"""Start the app:   python main.py --customer example
Then open http://127.0.0.1:8000 in your browser."""
import argparse

from app.config import load_config, path_in_project
from app.db import Database
from app.faces import FaceEngine
from app.recognize import Recognizer
from app.server import run_server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--customer", help="name of a file in config/customers/ (without .yaml)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    cfg = load_config(args.customer)                              # 1. settings
    engine = FaceEngine(cfg)                                      # 2. AI models
    db = Database(path_in_project(cfg["storage"]["database"]))    # 3. saved people
    recognizer = Recognizer(cfg, engine, db)                      # 4. register / check logic
    run_server(cfg, recognizer, db, args.host, args.port)         # 5. web page


if __name__ == "__main__":
    main()
