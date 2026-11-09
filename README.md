# CV Playground

Personal computer vision lab. One repo, many self-contained projects, grouped by **task**.

## Layout
```
projects/<task>/<project>/   one folder per experiment or product, self-contained
shared/                      code reused by 2+ projects (only add when a second project needs it)
docs/                        notes and conventions for the whole playground
```

## Projects
| Task | Project | What | Stack | Status |
|---|---|---|---|---|
| detection | [uav-defense](projects/detection/uav-defense) | UAV detection, localization and tracking | C++, ONNX, YOLO | early development |
| recognition/face | [entry-guard](projects/recognition/face/entry-guard) | Face register and authorize, ports-and-adapters architecture | Python, OpenCV | MVP |
| recognition/face | [entry-guard-compact](projects/recognition/face/entry-guard-compact) | Same MVP, small codebase easy to read | Python, OpenCV | MVP |

## Adding a project
Follow [docs/CONVENTIONS.md](docs/CONVENTIONS.md). Short version: copy nothing, create
`projects/<task>/<name>/` with a README, its own environment, config and tests.

## License
AGPL-3.0, see [LICENSE](LICENSE) (some projects depend on AGPL components such as Ultralytics).
