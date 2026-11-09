# Entry Guard (MVP)

Register faces from photos, then check whether a face in an image or video stream is authorized.
Everything customer-specific lives in config; nothing is hard-coded.

## Setup
```
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```
Download the two models listed in `models/MODELS.md`.

## Per-customer config
`config/default.yaml` holds all defaults. Create `config/customers/<id>.yaml` with only the
differences (see `example.yaml`), then use `--customer <id>` or `ENTRYGUARD_CUSTOMER=<id>`.
Order: default < customer < env (`ENTRYGUARD__POLICY__ACCEPT_THRESHOLD=0.4`).
`${VAR}` pulls secrets such as camera URLs from the environment.

What a customer can change: AI models (`models`), person fields (`person_schema`), thresholds and
decision rules (`policy`), enrollment limits, storage, cameras and their sources.

## Use
```
eg --customer example config
eg --customer example enroll --name An --attr unit_no=302 photos/an1.jpg photos/an2.jpg
eg --customer example check test.jpg
eg --customer example run --camera lobby
eg --customer example list | events | remove <id>
```

## Layout
`src/entryguard/core` (ports, policy, tracker, service; no model libraries) ·
`adapters` (YuNet, SFace, sources) · `store` (SQLite) · `registry.py` (config name to adapter) ·
`config/` · `docs/` (spec) · `tests/`.
Add a model by writing an adapter and one line in `registry.py`.
