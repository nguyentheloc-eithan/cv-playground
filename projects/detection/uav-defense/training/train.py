import argparse
from pathlib import Path

import yaml
from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune a YOLO model for UAV detection.")
    parser.add_argument("--config", type=Path, default=Path("configs/train_yolo.yaml"))
    args = parser.parse_args()

    settings = yaml.safe_load(args.config.read_text())
    model = YOLO(settings.pop("model"))
    model.train(**settings)


if __name__ == "__main__":
    main()
