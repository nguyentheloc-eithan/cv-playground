import argparse
import shutil
from pathlib import Path

import yaml
from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Export trained YOLO weights to ONNX for the C++ runtime.")
    parser.add_argument("--config", type=Path, default=Path("configs/export_yolo.yaml"))
    args = parser.parse_args()

    settings = yaml.safe_load(args.config.read_text())
    model = YOLO(settings["weights"])
    exported = Path(
        model.export(
            format="onnx",
            imgsz=settings["imgsz"],
            opset=settings["opset"],
            half=settings["half"],
            simplify=settings["simplify"],
            dynamic=False,
        )
    )

    output_dir = Path(settings["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / settings["output_name"]
    shutil.move(str(exported), target)
    print(target)


if __name__ == "__main__":
    main()
