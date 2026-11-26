# Assets to capture or render

| Asset | How | Notes |
|---|---|---|
| Architecture diagram | render `diagrams/architecture.mmd` to SVG | no cost data |
| Tamper state diagram | `diagrams/tamper-states.mmd` | |
| Power chain | `diagrams/power-chain.mmd` | |
| Face-login flow | `diagrams/president-auth.mmd` | |
| Enclosure renders | open `hardware/enclosure/*.stl` in a viewer; 6 angles + exploded | mark "design, not printed" |
| Enclosure front drawing | from `docs/solavis/solavis-hardware.html` section 5 | |
| Customer app screenshots | run demo, `owner@demo.vn`: Dashboard, Devices, Alerts, Visitors, Billing | light + dark |
| ERP screenshots | `president@solavis.vn` (Security log, Organisation), `sales.head@` (scoped dashboard) | blur demo emails if desired |
| Face dialog | ERP login with webcam (use a stand-in face, not a private person) | no real people without consent |
| Simulator | claim, visitor, "Turn 40°" lock moment | |
| 60 s demo video | story in `06-software-products.md` | screen record, no audio needed |
| Test run | terminal screenshot `157 passed` | |
Do not show: plan prices, margins, supplier names, secrets, `data/` photos, the real President email.
Run commands: see `solavis/RUN.md` in the repo.
