"""번역대 수정분(wsk_translation_edits_*.json)을 scripts/*.json 의 ko 에 반영.
사용: python tools/apply_workbench_edits.py 파일.json   (이후 romkr check / build)"""
import json, sys, os
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
o = json.load(open(sys.argv[1], encoding="utf8"))
assert o.get("format") == "wsk-translation-edits", "형식이 다릅니다"
total = 0
for b, m in o["blocks"].items():
    p = f"{root}/scripts/{b}.json"
    d = json.load(open(p, encoding="utf8")); n = 0
    for e in d:
        if e["id"] in m and e.get("ko") != m[e["id"]]:
            e["ko"] = m[e["id"]]; n += 1
    if n:
        json.dump(d, open(p, "w", encoding="utf8", newline="\n"), ensure_ascii=False, indent=2)
        open(p, "a", encoding="utf8").write("\n")
    print(b, n, "건"); total += n
print("합계", total)
