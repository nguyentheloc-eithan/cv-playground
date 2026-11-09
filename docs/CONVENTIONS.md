# Conventions

## Where things go
- `projects/<task>/<project>/`: task is the vision problem (detection, recognition, tracking,
  segmentation, pose, ocr, ...). Add a task folder when the first project needs it.
- A project must run on its own. It never imports from a sibling project.
- Code needed by two or more projects moves to `shared/<package>/` (not before: avoid early abstraction).

## Every project has
| Item | Rule |
|---|---|
| `README.md` | What it does, how to run in 3 commands, status |
| Environment | Own `.venv` (Python) or own CMake build; dependencies pinned in `requirements.txt` / `pyproject.toml` |
| `config/` | Settings as files, no values hard-coded in code |
| `tests/` | Runs without a camera or heavy models |
| `docs/` | Design notes, results, decisions |
| `.gitignore` | Project-specific ignores |

## Data, models and results
- Big files (datasets, weights, videos) are git-ignored; document where to get them in the project README
  (`models/README.md`, `datasets/SOURCES.md`).
- Record experiments in the project's `docs/` with: date, model, data, settings, metric, conclusion.
- Name things `kebab-case`; Python packages `snake_case`.

## Git
- Commits are made by hand, one topic per commit.
- Branch per project area when useful (`uav/...`, `face/...`).
