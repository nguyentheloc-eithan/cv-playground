# Entry Guard Compact

Register faces, then check whether a face is authorized. Built to be read top to bottom in
about 20 minutes. No frameworks, no classes you must learn first.

## Run
```
pip install -r requirements.txt
python main.py --customer example
```
Open http://127.0.0.1:8000, allow the camera, register yourself, then press **Check now**.
Models are in `models/` (see `models/README.md`).

## How it works (read the files in this order)
```
browser ──► server.py ──► recognize.py ──► faces.py   (AI: find face, make vector)
 (page)     (HTTP)        register / check  db.py      (SQLite: people and vectors)
                              ▲
                          config.py  (settings from config/*.yaml)
```
| File | One job |
|---|---|
| `main.py` | Wire the 5 parts together and start |
| `app/config.py` | Load `default.yaml` + customer file |
| `app/faces.py` | Detect faces, turn a face into 128 numbers |
| `app/db.py` | Save and load people |
| `app/recognize.py` | The two features: `register` and `check` |
| `app/server.py` | Web server and the page |

**Register:** photo → one face → vector → save with the name.
**Check:** photo → vector → compare with every saved vector → highest score decides:
`>= accept_threshold` authorized, `< reject_threshold` unknown, between = uncertain.

## Per-customer settings
Each customer is one small file in `config/customers/`. It only lists what is different from
`config/default.yaml`. Examples: form fields (`person_fields`), thresholds (`policy`), model
files (`models`). Start with `--customer name` or `ENTRYGUARD_CUSTOMER=name`.

## Tests
`pytest` runs without models or a camera (a fake engine stands in for the AI).

## Not in this version (on purpose)
Live camera streams, tracking people across frames, liveness (photo-of-a-photo) detection,
login, door control. Add them one at a time after this works.
