"""Run the app.

    python main.py --customer example                       start the web app
    python main.py --customer example create-user NAME --role admin     add a login

Then open http://127.0.0.1:8000
"""
import argparse
import getpass

import uvicorn

from app import auth
from app.api import create_app
from app.config import load_config, path_in_project
from app.db import Database
from app.faces import FaceEngine
from app.recognize import Recognizer


def open_database(cfg):
    return Database(path_in_project(cfg["storage"]["database"]),
                    path_in_project(cfg["storage"]["photos_dir"]),
                    path_in_project(cfg["storage"]["snapshots_dir"]),
                    cfg["site"]["id_prefix"])


def create_user(cfg, username, role):
    db = open_database(cfg)
    minimum = cfg["security"]["min_password_length"]
    password = getpass.getpass(f"Password (min {minimum} characters): ")
    problem = auth.password_problem(password, username, minimum)
    if problem:
        raise SystemExit(problem)
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match")
    db.add_user(username, auth.hash_password(password), role)
    db.audit("cli", "user_created", {"username": username, "role": role})
    print(f"Created {role} '{username}'")


def serve(cfg, host, port):
    db = open_database(cfg)
    secret = auth.load_secret(path_in_project(cfg["storage"]["secret_file"]))
    engine = FaceEngine(cfg)
    recognizer = Recognizer(cfg, engine, db)
    if db.count_users() == 0:
        print("No users yet. Create one:  python main.py create-user admin --role admin")
    app = create_app(cfg, recognizer, db, secret)
    print(f"Entry Guard: http://{host}:{port}   (Ctrl+C to stop)")
    uvicorn.run(app, host=host, port=port, log_level="warning")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--customer", help="name of a file in config/customers/ (without .yaml)")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    sub = parser.add_subparsers(dest="command")
    cu = sub.add_parser("create-user", help="add a login")
    cu.add_argument("username")
    cu.add_argument("--role", choices=["admin", "viewer"], default="viewer")
    args = parser.parse_args()

    cfg = load_config(args.customer)
    if args.command == "create-user":
        create_user(cfg, args.username, args.role)
    else:
        serve(cfg, args.host or cfg["server"]["host"], args.port or cfg["server"]["port"])


if __name__ == "__main__":
    main()
