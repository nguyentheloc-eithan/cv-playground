"""Turn the page sources in _src/ into standalone HTML you can open with VS Code Live Server.
Run:  python3 make_standalone.py
Adds the doctype, head tags and the Mermaid script that draws the diagrams."""
import re, pathlib
here = pathlib.Path(__file__).parent
HEAD = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n')
TAIL = '''
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<script>
  var dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  mermaid.initialize({ startOnLoad: true, theme: dark ? "dark" : "default", securityLevel: "loose" });
</script>
</body>
</html>
'''
ORDER = [
  ("solavis-srs.html", "SRS: software requirements (SOL-SRS-001)"),
  ("solavis-hardware.html", "Hardware engineering spec (SOL-HW-001)"),
  ("solavis-software.html", "Software and firmware design (SOL-SW-001)"),
  ("solavis-implementation-plan.html", "Implementation plan, business and programme"),
  ("solavis-website.html", "Product website (public draft)"),
  ("gate-camera-mvp.html", "Earlier MVP plan (first version, kept for reference)"),
  ("solar-gate-camera.html", "Original plan: Pi build, ESP32 custom PCB, first enclosure"),
]
for name, _ in ORDER:
    src = (here / "_src" / name).read_text()
    # keep head tags first, body starts right after the style block
    html = src.replace("</style>", "</style>\n<style>body{margin:0}</style>\n</head>\n<body>\n", 1)
    (here / name).write_text(HEAD + html + TAIL)
rows = "\n".join(f'<li><a href="{n}">{t}</a></li>' for n, t in ORDER)
(here / "index.html").write_text(f'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solavis documents</title>
<style>
:root{{--bg:#f4f6f8;--ink:#13202c;--muted:#586979;--brand:#0b3c5d;--card:#fff;--line:#d9e0e6}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0e151c;--ink:#e6edf3;--muted:#97a7b5;--brand:#7cc0ea;--card:#16202a;--line:#293643}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;padding:40px 16px}}
main{{max-width:720px;margin:0 auto}} h1{{margin:0 0 4px}} p{{color:var(--muted)}}
ul{{list-style:none;padding:0;display:flex;flex-direction:column;gap:10px}}
li a{{display:block;padding:14px 18px;background:var(--card);border:1px solid var(--line);border-radius:10px;color:var(--brand);text-decoration:none;font-weight:600}}
li a:hover{{border-color:var(--brand)}}
</style></head><body><main>
<h1>Solavis</h1>
<p>Tài liệu dự án. Mở file này bằng Live Server của VS Code (chuột phải, Open with Live Server). Cần có internet để tải font và vẽ sơ đồ.</p>
<ul>
{rows}
</ul>
<p>Mô hình in 3D (STL): <code>hardware/enclosure/</code></p>
</main></body></html>
''')
print("done:", len(ORDER) + 1, "files")
