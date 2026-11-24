"""端到端：构建时选的浏览器起不来就退回 chromium，不丢播放检测；选得动的浏览器照常用。
本地假站点 + 真实的 python -m aniyuan --smoke --playcheck 流程，不联网。"""
import json, os, shutil, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SEARCH = "<html><body><div class='box'><ul><li><h3><a href='/detail/1/'>葬送的芙莉莲</a></h3></li></ul></div></body></html>"
DETAIL = "<html><body><div class='pl'><div class='row'><ul><li><a href='/p/1'>第1集</a></li><li><a href='/p/2'>第2集</a></li></ul></div></div></body></html>"
PLAY = "<html><body><video src='/v/1.m3u8'></video></body></html>"


class Site(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body):
        b = body.encode(); self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/search/": return self.send(200, SEARCH)
        if p == "/detail/1/": return self.send(200, DETAIL)
        if p.startswith("/p/"): return self.send(200, PLAY)
        self.send(404, "nf")


srv = HTTPServer(("127.0.0.1", 0), Site)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_address[1]
tmp = tempfile.mkdtemp(); rules = os.path.join(tmp, "rules"); os.makedirs(rules); os.makedirs(os.path.join(tmp, "ov"))
json.dump({"name": "demo", "version": "1.0", "baseURL": base + "/", "searchURL": base + "/search/?wd=@keyword",
           "searchList": "//div[contains(@class,'box')]/ul/li", "searchName": "//h3/a", "searchResult": "//h3/a",
           "chapterRoads": "//div[@class='pl']/div[@class='row']/ul", "chapterResult": "//li/a", "referer": ""},
          open(os.path.join(rules, "demo.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump([{"name": "demo", "version": "1"}], open(os.path.join(rules, "index.json"), "w"))

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


def run(browser):
    out = os.path.join(tmp, "dist_" + browser)
    cfg = os.path.join(tmp, "config_%s.json" % browser)
    c = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    c.update(browser=browser, play_wait_ms=1500, play_check_max=1, icons=False, learn=False, smoke_fallback_keywords=[])
    json.dump(c, open(cfg, "w", encoding="utf-8"))
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "aniyuan_proxy", "aniyuan_browser")}
    env["NO_PROXY"] = "127.0.0.1,localhost"
    r = subprocess.run([sys.executable, "-m", "aniyuan", "--kazumi", rules, "--baseline", os.path.join(tmp, "none.json"),
                        "--state", os.path.join(tmp, "s_%s.json" % browser), "--health", os.path.join(tmp, "h_%s.json" % browser),
                        "--out", out, "--config", cfg, "--smoke", "--playcheck"],
                       capture_output=True, text=True, cwd=ROOT, env=env, timeout=240)
    return r


r = run("chromium")
check("chromium：正常，用的是 chromium，没有退回提示", r.returncode == 0 and "播放检测用的浏览器：chromium" in r.stdout and "退回" not in r.stderr)

r = run("firefox")
if r.returncode:
    print(r.stdout[-800:], r.stderr[-800:])
check("firefox 没装 / 起不来：退回 chromium，流程照常结束", r.returncode == 0 and "播放检测用的浏览器：chromium" in r.stdout
      and "浏览器 firefox 起不来" in r.stderr and "退回 chromium" in r.stderr)

r = run("edge")
check("写了不认识的浏览器名：同样退回 chromium，不崩", r.returncode == 0 and "播放检测用的浏览器：chromium" in r.stdout and "退回 chromium" in r.stderr)

if shutil.which("google-chrome") or shutil.which("google-chrome-stable"):
    r = run("chrome")
    if r.returncode:
        print(r.stdout[-800:], r.stderr[-800:])
    check("chrome：装了就直接用它，不退回", r.returncode == 0 and "播放检测用的浏览器：chrome" in r.stdout and "退回" not in r.stderr)
else:
    print("SKIP chrome（没装 Google Chrome）")

srv.shutdown()
print("\n%d 项未通过" % bad if bad else "\n全部通过")
sys.exit(1 if bad else 0)
