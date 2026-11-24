"""번역대(모바일 HTML) 생성: scripts/*.json + glossary.tsv -> work/translation_workbench.html
사용: python tools/build_workbench.py   (결과 파일을 Artifact 로 게시)"""
import json, glob, os, re
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
order = ["dialog_b4","news_b6","stock_desc_b5","stock_ui_b5","stock_names_b5","stock_cat_b5","menu_b7",
         "password_b7","title_featuring","weekdays","status_cash","status_stocks","stock_list_names_b5"]
blocks = {}
for n in order:
    d = json.load(open(f"{root}/scripts/{n}.json", encoding="utf8"))
    blocks[n] = [{k: e[k] for k in ("id","ja","ko","note","alias_of","max_bytes") if k in e} for e in d]
gl = []
for i, line in enumerate(open(f"{root}/glossary.tsv", encoding="utf8")):
    p = line.rstrip("\n").split("\t")
    if i and len(p) >= 2 and p[0]: gl.append((p + ["", ""])[:4])
data = json.dumps({"order": order, "blocks": blocks, "glossary": gl}, ensure_ascii=False).replace("<", "\u003c")
tpl = open(f"{root}/tools/workbench.template.html", encoding="utf8").read()
os.makedirs(f"{root}/work", exist_ok=True)
out = f"{root}/work/translation_workbench.html"
open(out, "w", encoding="utf8").write(tpl.replace("__DATA__", data))
print(out, os.path.getsize(out))
