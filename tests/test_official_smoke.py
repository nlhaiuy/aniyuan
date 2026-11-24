"""联网检测官方同站源（本地模拟站点）：官方通过 + exclude → 剔除；官方失效 → 自有保留补位；官方通过 + demote → 降档。
站点靠 official_aliases 对上（自有站用 127.0.0.2，官方同站源用 localhost，名字不同）。"""
import copy, json, os, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEARCH = """<html><body><div class="search-box"><ul><li><h3><a href="/detail/1/">葬送的芙莉莲</a></h3></li></ul></div></body></html>"""
DETAIL = """<html><body><div class="playlist"><div class="row"><ul><li><a href="/play/1-1">第1集</a></li><li><a href="/play/1-2">第2集</a></li></ul></div></div></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        path = self.path.split("?")[0]
        code, body = (200, SEARCH) if path == "/search/" else (200, DETAIL) if path == "/detail/1/" else (404, "nf")
        b = body.encode(); self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

def rule(name, base):
    return {"name": name, "version": "1.0", "baseURL": base + "/", "searchURL": base + "/search/?wd=@keyword",
            "searchList": "//div[contains(@class,'search-box')]/ul/li", "searchName": "//h3/a", "searchResult": "//h3/a",
            "chapterRoads": "//div[@class='playlist']/div[@class='row']/ul", "chapterResult": "//li/a", "referer": ""}

def build(tmp, tag, cfg, official=None):
    cpath = os.path.join(tmp, "config-%s.json" % tag)
    json.dump(cfg, open(cpath, "w", encoding="utf-8"))
    out = os.path.join(tmp, "dist-" + tag)
    cmd = [sys.executable, "-m", "aniyuan", "--kazumi", os.path.join(tmp, "rules"), "--baseline", os.path.join(tmp, "none.json"),
           "--state", os.path.join(tmp, "state-%s.json" % tag), "--health", os.path.join(tmp, "health-%s.json" % tag), "--out", out,
           "--config", cpath, "--learned-cache", os.path.join(tmp, "l-%s.json" % tag),
           "--play-cache", os.path.join(tmp, "p-%s.json" % tag), "--smoke"]
    if official:
        cmd += ["--official", official]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return r, {s["id"]: s for s in json.load(open(os.path.join(out, "all.json")))["mediaSources"]}, out

def main():
    srv = HTTPServer(("0.0.0.0", 0), H); port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    tmp = tempfile.mkdtemp(); rules = os.path.join(tmp, "rules"); os.makedirs(rules); os.makedirs(os.path.join(tmp, "ov"))
    own = "http://127.0.0.2:%d" % port
    json.dump(rule("mine", own), open(os.path.join(rules, "mine.json"), "w"))
    json.dump(rule("solo", "http://solo-only.invalid"), open(os.path.join(rules, "solo.json"), "w"))
    json.dump([{"name": "mine", "version": "1.0"}, {"name": "solo", "version": "1.0"}], open(os.path.join(rules, "index.json"), "w"))
    cfg = {"default_tier": 2, "auto_tier": False, "official_demote_tier": 4, "official_aliases": {"0": "localhost"},
           "learn": False, "icons": False, "smoke_both_exits": False, "smoke_fallback_keywords": []}

    r0, base, _ = build(tmp, "base", dict(cfg, official_dedupe="off"))
    mine = copy.deepcopy(base["aniyuan-mine"])
    assert mine["arguments"]["searchConfig"]["searchUrl"].startswith(own), mine["arguments"]["searchConfig"]["searchUrl"]

    def make_official(name, broken):
        d = os.path.join(tmp, "official-" + name); os.makedirs(os.path.join(d, "subs", "web", "t1"))
        o = json.loads(json.dumps(mine).replace("127.0.0.2:%d" % port, "localhost:%d" % port))
        o["id"] = "o-mine"; o["arguments"]["name"] = "官方mine"; o["arguments"]["tier"] = 1
        if broken:
            o["arguments"]["searchConfig"]["searchUrl"] = "http://localhost:%d/gone?wd={keyword}" % port
        json.dump(o, open(os.path.join(d, "subs", "web", "t1", "mine.json"), "w", encoding="utf-8"), ensure_ascii=False)
        return d

    good, broken = make_official("good", False), make_official("broken", True)
    r1, ex, out1 = build(tmp, "exclude", dict(cfg, official_dedupe="exclude"), good)
    r2, dm, _ = build(tmp, "demote", dict(cfg, official_dedupe="demote"), good)
    r3, rescue, out3 = build(tmp, "rescue", dict(cfg, official_dedupe="exclude"), broken)
    rep1 = open(os.path.join(out1, "report.md"), encoding="utf-8").read()
    rep3 = open(os.path.join(out3, "report.md"), encoding="utf-8").read()
    for r in (r0, r1, r2, r3):
        if r.returncode:
            print(r.stdout[-1500:], r.stderr[-1500:])
    tier = lambda d, k: d[k]["arguments"].get("tier")
    checks = [
        ("基线：不处理官方，自有源 ok 且在订阅里", r0.returncode == 0 and "aniyuan-mine" in base and tier(base, "aniyuan-mine") == 2),
        ("官方同站源检测通过 + exclude：自有的被剔除，独有的还在", r1.returncode == 0 and "aniyuan-mine" not in ex and "aniyuan-solo" in ex),
        ("报告写明官方检测 ok、已剔除", "| 官方mine（T1） | ok | 已剔除 |" in rep1),
        ("官方通过 + demote：降到 4，独有的不动", r2.returncode == 0 and tier(dm, "aniyuan-mine") == 4 and tier(dm, "aniyuan-solo") == 2),
        ("官方失效 + exclude：自有源保留补位、档位不动", r3.returncode == 0 and "aniyuan-mine" in rescue and tier(rescue, "aniyuan-mine") == 2),
        ("报告写明官方检测 fail、补位", "| 官方mine（T1） | fail | 保持 |" in rep3 and "补位" in rep3),
    ]
    bad = 0
    for name, ok in checks:
        print(("OK  " if ok else "BAD ") + name); bad += (not ok)
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
