"""端到端：配了国内出口代理时，国内（走代理）和海外（直连）都测，并在报告里对比。
本地模拟：站点对“没经过代理”的请求返回 403（=海外被拦），经过代理（带 Via: cn-exit）才放行。"""
import json, os, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SEARCH = "<html><body><div class='box'><ul><li><h3><a href='/detail/1/'>葬送的芙莉莲</a></h3></li></ul></div></body></html>"
DETAIL = "<html><body><div class='pl'><div class='row'><ul><li><a href='/p/1'>第1集</a></li><li><a href='/p/2'>第2集</a></li></ul></div></div></body></html>"


class Site(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body):
        b = body.encode(); self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/geo/search/":   # 只对国内出口放行
            return self.send(200, SEARCH) if self.headers.get("Via") == "cn-exit" else self.send(403, "Forbidden")
        if p == "/search/": return self.send(200, SEARCH)
        if p == "/detail/1/": return self.send(200, DETAIL)
        self.send(404, "nf")


class Proxy(BaseHTTPRequestHandler):
    """最简单的 http 代理：把绝对地址的 GET 转发出去，并加上 Via: cn-exit。"""
    def log_message(self, *a): pass
    def do_GET(self):
        req = urllib.request.Request(self.path, headers={"Via": "cn-exit"})
        try:
            r = urllib.request.urlopen(req, timeout=10); code, body = r.status, r.read()
        except urllib.error.HTTPError as e:
            code, body = e.code, e.read()
        self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


def serve(h):
    s = HTTPServer(("0.0.0.0", 0), h)   # 规则用 127.0.0.N 区分站点，所以要绑定所有回环地址
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s

site, prox = serve(Site), serve(Proxy)
port = site.server_address[1]
tmp = tempfile.mkdtemp(); rules = os.path.join(tmp, "rules"); os.makedirs(rules); os.makedirs(os.path.join(tmp, "ov"))
n = [1]
def w(name, path):
    n[0] += 1   # 每条规则一个不同的回环地址，避免被当成同一个站
    base = "http://127.0.0.%d:%d" % (n[0], port)
    json.dump({"name": name, "version": "1.0", "baseURL": base + "/", "searchURL": base + path + "?wd=@keyword",
               "searchList": "//div[contains(@class,'box')]/ul/li", "searchName": "//h3/a", "searchResult": "//h3/a",
               "chapterRoads": "//div[@class='pl']/div[@class='row']/ul", "chapterResult": "//li/a", "referer": ""},
              open(os.path.join(rules, name + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
w("both1", "/search/")   # 两个出口都通
w("geo1", "/geo/search/")   # 只有国内出口通，海外直连被拦
json.dump([{"name": x, "version": "1"} for x in ("both1", "geo1")], open(os.path.join(rules, "index.json"), "w"))

def run(extra_cfg, proxy):
    out = os.path.join(tmp, "dist_%s" % ("p" if proxy else "n") + str(extra_cfg.get("smoke_both_exits")))
    cfg = os.path.join(tmp, "config_%d.json" % len(os.listdir(tmp)))
    base = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8")); base.update(extra_cfg)
    json.dump(base, open(cfg, "w", encoding="utf-8"))
    env = dict(os.environ); env.pop("ANIYUAN_PROXY", None); env.pop("ANIYUAN_PROXY_NOTE", None)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(k, None)
    env["NO_PROXY"] = "127.0.0.1,localhost"
    if proxy:
        env["ANIYUAN_PROXY"] = "http://127.0.0.1:%d" % prox.server_address[1]
    r = subprocess.run([sys.executable, "-m", "aniyuan", "--kazumi", rules, "--baseline", os.path.join(tmp, "none.json"), "--state", os.path.join(tmp, "s_%s.json" % os.path.basename(out)),
                        "--health", os.path.join(tmp, "h_%s.json" % os.path.basename(out)), "--out", out, "--overrides", os.path.join(tmp, "ov"), "--config", cfg, "--smoke"],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    if r.returncode:
        print(r.stdout[-1500:], r.stderr[-1500:])
    return r, out

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)

r, out = run({"smoke_direct_wait": 0, "smoke_fallback_keywords": []}, proxy=True)
rep = open(os.path.join(out, "report.md"), encoding="utf-8").read()
cand = {e["key"]: e for e in json.load(open(os.path.join(out, "report.json")))["candidates"]}
check("流水线正常结束", r.returncode == 0)
check("两个出口的结果都记下了：geo1 国内 ok、海外 blocked", cand["geo1"]["smoke"]["status"] == "ok" and cand["geo1"]["smoke_direct"]["status"] == "blocked")
check("两边都通的：both1 国内 ok、海外 ok", cand["both1"]["smoke"]["status"] == "ok" and cand["both1"]["smoke_direct"]["status"] == "ok")
check("报告抬头写明国内出口 + 海外对照", "检测出口：国内出口（代理 http://127.0.0.1:" in rep and "海外服务器直连也测了一遍" in rep)
check("全部候选表的自动检测列带海外结果", "| ok（海外：blocked） |" in rep and "| ok（海外：ok） |" in rep)
check("有「国内外出口对比」一节，计数正确", "## 国内外出口对比" in rep and "| 两边都通过 | 1 |" in rep and "| 只有国内通过 | 1 |" in rep and "| 只有海外通过 | 0 |" in rep)
check("差异清单列出 geo1 并说明符合预期", "| kazumi:geo1 | ok | blocked |" in rep and "符合预期" in rep)
check("排名只看国内出口：geo1 没有被海外的 403 拖累", cand["geo1"]["smoke"]["status"] == "ok" and not any("海外检测被拦" in x for x in cand["geo1"]["notes"]))
sub = json.load(open(os.path.join(out, "all.json")))
check("订阅里两个源都在，没有“自动检测未通过”前缀", {"aniyuan-both1", "aniyuan-geo1"} <= {s["id"] for s in sub["mediaSources"]}
      and not any(s["arguments"]["description"].startswith("[自动检测未通过") for s in sub["mediaSources"]))

r, out = run({"smoke_both_exits": False}, proxy=True)
rep = open(os.path.join(out, "report.md"), encoding="utf-8").read()
cand = {e["key"]: e for e in json.load(open(os.path.join(out, "report.json")))["candidates"]}
check("smoke_both_exits=false：不做海外对照、报告没有对比一节", all("smoke_direct" not in c for c in cand.values()) and "## 国内外出口对比" not in rep and "（海外：" not in rep)
check("smoke_both_exits=false：抬头只写国内出口", "检测出口：国内出口（代理 http://127.0.0.1:" in rep and "海外服务器直连" not in rep.split("## ")[0])

r, out = run({}, proxy=False)
rep = open(os.path.join(out, "report.md"), encoding="utf-8").read()
cand = {e["key"]: e for e in json.load(open(os.path.join(out, "report.json")))["candidates"]}
check("没配代理：和以前一样，只有海外一个出口", "检测出口：GitHub 海外服务器" in rep and "## 国内外出口对比" not in rep and all("smoke_direct" not in c for c in cand.values()))
check("没配代理：geo1 在海外被拦（blocked）", cand["geo1"]["smoke"]["status"] == "blocked" and cand["both1"]["smoke"]["status"] == "ok")
sys.exit(1 if bad else 0)
