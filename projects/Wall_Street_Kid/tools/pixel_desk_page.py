"""폰트작업대 페이지 굽기: tools/pixel_desk.py build 결과 JSON 을 tools/pixel_desk.html 에 넣는다.

    python -X utf8 tools/pixel_desk_page.py   -> work/desk/pixel_desk.html (아티팩트로 발행)
"""
import json
import os
import subprocess
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PROJ, "work", "desk", "pixel_data.json")
OUT = os.path.join(PROJ, "work", "desk", "pixel_desk.html")

subprocess.check_call([sys.executable, os.path.join(PROJ, "tools", "pixel_desk.py"), "build", "--out", DATA], cwd=PROJ)
P = json.load(open(DATA, encoding="utf-8"))
tpl = open(os.path.join(PROJ, "tools", "pixel_desk.html"), encoding="utf-8").read()
data = json.dumps(P, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(OUT, "w", encoding="utf-8", newline="\n").write(tpl.replace("/*__DATA__*/", data))
print(f"{len(P['items'])}개 → {OUT} ({os.path.getsize(OUT) // 1024} KB)")
