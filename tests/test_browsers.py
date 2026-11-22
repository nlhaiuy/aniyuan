"""可选浏览器的自测：浏览器名解析、启动参数、UA 处理、多浏览器抓取 + 对比表；
最后用本机页面对能启动的浏览器各做一次真实抓取（没装的浏览器跳过，不算失败）。不联网。"""
import json, os, shutil, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from aniyuan import capture as C
from aniyuan.check import playcheck as P, smoke as smoke_mod, ua as ua_mod

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


# ---------- 浏览器名 ----------
os.environ.pop("ANIYUAN_BROWSER", None)
check("默认 chromium", P.browser_name() == "chromium" and P.browser_name("") == "chromium")
os.environ["ANIYUAN_BROWSER"] = "Firefox"
check("环境变量生效，大小写不敏感", P.browser_name() == "firefox")
check("参数优先于环境变量", P.browser_name("webkit") == "webkit")
os.environ.pop("ANIYUAN_BROWSER")
try:
    P.browser_name("edge"); ok = False
except ValueError as e:
    ok = "edge" in str(e) and "firefox" in str(e)
check("不认识的名字报错（不悄悄换成别的）", ok)


# ---------- 启动参数 ----------
class FakeLauncher:
    def __init__(self, calls, name): self.calls, self.name = calls, name
    def launch(self, **kw): self.calls.append((self.name, kw)); return "B-" + self.name

class FakePW:
    def __init__(self):
        self.calls = []
        for n in ("chromium", "firefox", "webkit"):
            setattr(self, n, FakeLauncher(self.calls, n))

pw = FakePW()
P._launch(pw, {"server": "http://p:1"}, "chromium")
n, kw = pw.calls[-1]
check("chromium：无头 + --no-sandbox + 代理，和以前一样", n == "chromium" and kw["headless"] is True and "--no-sandbox" in kw["args"] and kw["proxy"] == {"server": "http://p:1"} and "channel" not in kw)
os.environ.pop("DISPLAY", None)
P._launch(pw, None, "chrome")
n, kw = pw.calls[-1]
check("chrome：走 chromium 内核的 chrome 通道；没有 DISPLAY 就无头", n == "chromium" and kw["channel"] == "chrome" and kw["headless"] is True and "proxy" not in kw)
os.environ["DISPLAY"] = ":99"
P._launch(pw, None, "chrome")
check("chrome：有 DISPLAY（xvfb）就有头", pw.calls[-1][1]["headless"] is False)
os.environ.pop("DISPLAY")
P._launch(pw, {"server": "socks5://x:1"}, "firefox")
n, kw = pw.calls[-1]
check("firefox：自己的内核，不带 Chromium 的参数，代理照给", n == "firefox" and kw == {"headless": True, "proxy": {"server": "socks5://x:1"}})
P._launch(pw, None, "webkit")
check("webkit：自己的内核", pw.calls[-1][0] == "webkit" and "args" not in pw.calls[-1][1])


# ---------- UA：Chromium 系用统一 UA，Firefox / WebKit 用自带 ----------
class FakeBrowser:
    def __init__(self): self.ctx = []
    def new_context(self, **kw): self.ctx.append(kw); return "ctx"

def bare(name):
    pc = object.__new__(P.PlayChecker)
    pc.browser_name, pc.browser = name, FakeBrowser()
    return pc

ua_mod.reset()
c = bare("chromium"); c.new_context()
check("chromium：套统一 UA", c.browser.ctx[0]["user_agent"] == ua_mod.current())
f = bare("firefox"); f.new_context()
check("firefox：不套 Chrome 的 UA（引擎和 UA 对不上更容易被识别）", "user_agent" not in f.browser.ctx[0])
f.new_context("MyUA/1.0")
check("源自己写了 UA 的照它来（任何浏览器）", f.browser.ctx[1]["user_agent"] == "MyUA/1.0")

class NoCDP:
    def new_page(self): return "page"
    def new_cdp_session(self, p): raise AssertionError("非 Chromium 不该碰 CDP")
check("firefox 不发 CDP 命令", bare("firefox").new_page(NoCDP()) == "page")


# ---------- UA 体检：非 Chromium 跳过核对 ----------
class FakeFF:
    browser_name = "firefox"
    def fetch(self, url): raise AssertionError("firefox 不该走统一 UA 核对")
res = ua_mod.audit(FakeFF())
check("UA 体检：firefox 跳过浏览器 UA 核对、不误报失败", all(ok for _, ok, _ in res) and any("firefox" in d for _, _, d in res))


# ---------- 抓取：多浏览器 + 对比表 ----------
class Resp:
    def __init__(self, status, text, url): self.status_code, self.text, self.url = status, text, url

SEARCH = '<html><body>' + ''.join('<div class="module-card-item-title"><a href="/voddetail/%d.html">%s</a></div>' % (i, "葬送的芙莉莲" if i == 1 else "别的%d" % i) for i in range(1, 4)) + '<p>' + 'x' * 600 + '</p></body></html>'
DETAIL = '<html><body><div class="module-play-list-content"><a href="/vodplay/1-1-1.html">第1集</a><a href="/vodplay/1-1-2.html">第2集</a></div><p>' + 'y' * 1600 + '</p></body></html>'

def fake_get(url, session, timeout, ua=None):
    if "/voddetail/1.html" in url: return Resp(200, DETAIL, url)
    if "/vodplay/1-1-1.html" in url: return Resp(200, "<html>player</html>", url)
    if "/index.php/vod/search.html" in url:   # 乱码关键词（探测“什么都返回结果”的站）返回空页
        return Resp(200, "<html>空</html>" if "zqxjkv" in url else SEARCH, url)
    return Resp(404, "", url)

MEDIA = json.dumps({"data": {"url": "https://cdn.x.com/a/index.m3u8"}})
XHR_BY_BROWSER = {"chromium": [{"url": "https://x/a", "method": "GET", "post": None, "headers": {}, "status": 200, "ctype": "", "text": "{}"}],
                  "chrome": [{"url": "https://x/a", "method": "GET", "post": None, "headers": {}, "status": 200, "ctype": "", "text": "{}"},
                             {"url": "https://x/p", "method": "POST", "post": "{}", "headers": {}, "status": 200, "ctype": "", "text": MEDIA}]}

class FakePC:
    def __init__(self, proxy=None, browser=None):
        self.browser_name = P.browser_name(browser)
        if self.browser_name == "webkit":
            raise RuntimeError("Executable doesn't exist\n（没装 webkit）")
    def fetch(self, *a, **k): raise AssertionError
    def capture(self, url, wait_ms=20000, **k): return list(XHR_BY_BROWSER[self.browser_name])
    def close(self): pass

orig_get, orig_pc = smoke_mod._get, P.PlayChecker
tmp = tempfile.mkdtemp()
try:
    smoke_mod._get, P.PlayChecker = fake_get, FakePC
    sites = os.path.join(tmp, "sites.json")
    json.dump([dict(key=k, origin="https://%s.example.com" % k, keywords=["葬送的芙莉莲"]) for k in ("a", "b")], open(sites, "w"))

    out = os.path.join(tmp, "multi")
    rc = C.main(["--sites", sites, "--out", out, "--browsers", "chromium,chrome,webkit,chromium"])
    idx = open(os.path.join(out, "INDEX.md"), encoding="utf-8").read()
    check("多浏览器：每个浏览器一个子目录，重复的名字只抓一次", rc == 0 and os.path.exists(os.path.join(out, "chromium", "a", "meta.json"))
          and os.path.exists(os.path.join(out, "chrome", "b", "play-xhr.json")) and not os.path.exists(os.path.join(out, "webkit", "a")))
    m = json.load(open(os.path.join(out, "chrome", "a", "meta.json"), encoding="utf-8"))
    check("meta.json 记录浏览器和播放页 XHR 统计（总数 / 带视频地址）", m["browser"] == "chrome" and m["play_xhr"] == {"count": 2, "media": 1})
    check("每个浏览器目录里也有自己的 INDEX.md（带 XHR 列）", "播放页 XHR" in open(os.path.join(out, "chromium", "INDEX.md"), encoding="utf-8").read())
    check("对比表：各浏览器的 XHR 数、哪个浏览器抓到视频地址", "| a | 1 条 / 带视频地址 0 条 | 2 条 / 带视频地址 1 条 | 起不来 | chrome |" in idx)
    check("对比表：起不来的浏览器写明原因，不拖垮其它浏览器", "webkit没起来" in idx.replace("（", "").replace("）", "") or "没起来" in idx)

    out1 = os.path.join(tmp, "single")
    rc = C.main(["--sites", sites, "--out", out1, "--browser", "chrome"])
    check("单个浏览器：目录结构和以前一样（不加浏览器子目录）", rc == 0 and os.path.exists(os.path.join(out1, "a", "meta.json")))

    rc = C.main(["--sites", sites, "--out", os.path.join(tmp, "nb"), "--no-browser"])
    check("--no-browser 照常工作", rc == 0 and os.path.exists(os.path.join(tmp, "nb", "INDEX.md")))

    try:
        C.main(["--sites", sites, "--out", os.path.join(tmp, "bad"), "--browsers", "chromium,edge"]); ok = False
    except SystemExit as e:
        ok = e.code != 0
    check("不认识的浏览器名：命令行直接报错退出", ok)
finally:
    smoke_mod._get, P.PlayChecker = orig_get, orig_pc


# ---------- 真实浏览器：本机页面，页面里用 fetch 取一个带 m3u8 的 JSON ----------
PAGE = b"<html><body>player<script>fetch('/api/play?id=7').then(r=>r.json()).then(d=>{document.title='done'})</script></body></html>"

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/api/play"):
            body, ct = json.dumps({"data": {"url": "https://cdn.demo.com/v/index.m3u8"}}).encode(), "application/json"
        else:
            body, ct = PAGE, "text/html; charset=utf-8"
        self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = "http://127.0.0.1:%d/play" % srv.server_port
tried = 0
for name in P.BROWSERS:
    if name == "chrome" and not (shutil.which("google-chrome") or shutil.which("google-chrome-stable")):
        print("SKIP chrome（没装 Google Chrome）"); continue
    try:
        pc = P.PlayChecker(None, name)
    except Exception as e:
        print("SKIP %s（起不来：%s）" % (name, str(e).strip().splitlines()[0][:70])); continue
    tried += 1
    try:
        entries = pc.capture(url, wait_ms=3000)
        check("真实 %s：抓到播放页的 fetch 请求，响应里有视频地址（%s）" % (name, pc.browser.version),
              C._media_count(entries) == 1 and any("/api/play?id=7" in e["url"] for e in entries))
        ctx = pc.new_context(); page = ctx.new_page(); page.goto(url); ua = page.evaluate("navigator.userAgent"); ctx.close()
        if name in P.CHROMIUM_FAMILY:
            check("真实 %s：UA 是统一 UA，没有 HeadlessChrome" % name, ua == ua_mod.current() and "Headless" not in ua)
        else:
            check("真实 %s：用自己的 UA（不是 Chrome 的）" % name, "Chrome/" not in ua and ua)
    finally:
        pc.close()
check("至少有一个真实浏览器跑通（本机至少有 chromium）", tried >= 1)
srv.shutdown()
print("\n%d 项未通过" % bad if bad else "\n全部通过")
sys.exit(1 if bad else 0)
