"""Składa podgląd aplikacji w jeden plik HTML (dane wbudowane) do obejrzenia bez instalacji."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "preview.html"

html = (APP / "index.html").read_text(encoding="utf-8")
body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
body = body.replace('<script src="app.js"></script>', "")
data = {
    "events": json.loads((APP / "data" / "events.json").read_text(encoding="utf-8")),
    "sources": json.loads((APP / "data" / "sources.json").read_text(encoding="utf-8")),
    "excluded": json.loads((APP / "data" / "excluded.json").read_text(encoding="utf-8")),
}
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
page = f"""<title>EventManager – podgląd</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..100,500..800&family=Public+Sans:wght@400;500;600&display=swap">
<style>
{(APP / "style.css").read_text(encoding="utf-8")}
</style>
{body}
<script>window.EM_DATA = {blob};</script>
<script>
{(APP / "app.js").read_text(encoding="utf-8")}
</script>
"""
out.write_text(page, encoding="utf-8")
print(out, len(page))
