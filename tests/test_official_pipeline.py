"""整条流水线 + 官方订阅：不联网（不加 --smoke），验证 --official 能认出重叠站点、降档、写报告；
official_dedupe=off 不处理；写错的值直接失败。"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def rule(name, base):
    return {"name": name, "version": "1.0", "baseURL": base + "/", "searchURL": base + "/search/?wd=@keyword",
            "searchList": "//div[contains(@class,'search-box')]/ul/li", "searchName": "//h3/a", "searchResult": "//h3/a",
            "chapterRoads": "//div[@class='playlist']/div[@class='row']/ul", "chapterResult": "//li/a", "referer": ""}

def run(tmp, cfg, tag):
    cpath = os.path.join(tmp, "config-%s.json" % tag)
    json.dump(cfg, open(cpath, "w", encoding="utf-8"), ensure_ascii=False)
    out = os.path.join(tmp, "dist-" + tag)
    r = subprocess.run([sys.executable, "-m", "aniyuan", "--kazumi", os.path.join(tmp, "rules"), "--official", os.path.join(tmp, "official"),
                        "--baseline", os.path.join(tmp, "none.json"), "--state", os.path.join(tmp, "state-%s.json" % tag),
                        "--health", os.path.join(tmp, "health.json"), "--out", out, "--config", cpath], capture_output=True, text=True, cwd=ROOT)
    return r, out

def main():
    tmp = tempfile.mkdtemp()
    rules = os.path.join(tmp, "rules"); os.makedirs(rules); os.makedirs(os.path.join(tmp, "ov"))
    for n, base in (("lmm", "https://www.lmm-test.com"), ("solo", "https://solo-test.net")):
        json.dump(rule(n, base), open(os.path.join(rules, n + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump([{"name": "lmm", "version": "1.0"}, {"name": "solo", "version": "1.0"}], open(os.path.join(rules, "index.json"), "w"))
    off = os.path.join(tmp, "official", "subs", "web", "t2"); os.makedirs(off)
    json.dump({"id": "o-lmm", "factoryId": "web-selector", "version": 2,
               "arguments": {"name": "路漫漫", "tier": 2, "iconUrl": "", "searchConfig": {
                   "searchUrl": "https://www.lmm-test.org/search?wd={keyword}", "rawBaseUrl": "https://www.lmm-test.org"}}},
              open(os.path.join(off, "路漫漫.json"), "w", encoding="utf-8"), ensure_ascii=False)

    base_cfg = {"default_tier": 2, "auto_tier": False, "official_demote_tier": 4}
    r, out = run(tmp, base_cfg, "demote")
    print(r.stdout[-1200:], r.stderr[-800:])
    sub = {s["id"]: s for s in json.load(open(os.path.join(out, "all.json")))["mediaSources"]}
    tier = lambda sid: sub[sid]["arguments"].get("tier")
    rep = open(os.path.join(out, "report.md"), encoding="utf-8").read()
    rj = json.load(open(os.path.join(out, "report.json")))
    r2, out2 = run(tmp, dict(base_cfg, official_dedupe="off"), "off")
    sub2 = {s["id"]: s for s in json.load(open(os.path.join(out2, "all.json")))["mediaSources"]}
    r3, _ = run(tmp, dict(base_cfg, official_dedupe="dorp"), "bad")
    checks = [
        ("构建成功，两个源都在订阅里", r.returncode == 0 and len(sub) == 2),
        ("重叠的源（lmm，同名不同后缀）降到最低档", [t for k, t in ((k, tier(k)) for k in sub) if "lmm" in k] == [4]),
        ("官方没有的源（solo）档位不动", [t for k, t in ((k, tier(k)) for k in sub) if "solo" in k] == [2]),
        ("报告里有「与官方订阅的重叠」一节，写明 1 个重复 1 个独有", "## 与官方订阅的重叠" in rep and "1 个**和官方订阅重复" in rep and "1 个**是官方没有的" in rep),
        ("报告里写出官方同站源的名字和档位", "路漫漫（T2）" in rep),
        ("report.json 带 official_overlap", len(rj.get("official_overlap", [])) == 1 and rj["official_overlap"][0]["action"] == "demote"),
        ("official_dedupe=off：不降档、不写这一节", r2.returncode == 0 and all(s["arguments"].get("tier") == 2 for s in sub2.values())
            and "与官方订阅的重叠" not in open(os.path.join(out2, "report.md"), encoding="utf-8").read()),
        ("official_dedupe 写错：构建失败而不是悄悄忽略", r3.returncode != 0 and "official_dedupe" in (r3.stderr + r3.stdout)),
    ]
    bad = 0
    for name, ok in checks:
        print(("OK  " if ok else "BAD ") + name); bad += (not ok)
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
