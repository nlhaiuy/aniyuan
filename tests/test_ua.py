"""统一 UA / UA 体检 / 出口代理的自测（只访问本机的回显服务，不联网）。"""
import os, re, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import requests
from aniyuan.check import network, smoke, ua

bad = 0
def check(name, ok):
    global bad
    print(("OK  " if ok else "BAD ") + name); bad += (not ok)


# 1. 只有一个 UA 来源：检测代码里不再写死 Chrome/版本号
hard = []
for d in ("aniyuan/check", "aniyuan"):
    for fn in os.listdir(os.path.join(ROOT, d)):
        if fn.endswith(".py") and fn != "ua.py" and not fn.startswith("anibaka"):
            txt = open(os.path.join(ROOT, d, fn), encoding="utf-8").read()
            if re.search(r"Chrome/\d+", txt) and d == "aniyuan/check":
                hard.append(fn)
check("检测代码里没有写死的 Chrome/版本号（只有 ua.py 一处）", not hard)

# 2. 请求头
ua.reset()
check("默认 UA 是 Chrome 系", "Chrome/%d.0.0.0" % ua.FALLBACK_MAJOR in ua.current())
check("源自己指定了 UA 就用它", ua.request_headers("MyUA/1.0")["User-Agent"] == "MyUA/1.0")
check("源没指定（空串/空白）用统一 UA", ua.request_headers("  ")["User-Agent"] == ua.current())
ua.configure({"user_agent": "Custom/9"})
check("config.user_agent 整体覆盖", ua.current() == "Custom/9")
ua.adopt_browser_version("200.0.1.2")
check("整体覆盖后不会被浏览器版本改掉", ua.current() == "Custom/9")
ua.reset()
check("采用实际浏览器的大版本", ua.adopt_browser_version("153.0.8010.12") == 153 and "Chrome/153.0.0.0" in ua.current())
check("parse_major", ua.parse_major("Mozilla/5.0 Chrome/58.0.3029.110 Safari/537.3") == 58 and ua.parse_major("x") is None)

# 3. 客户端提示
h = ua.client_hints()
check("客户端提示的版本和 UA 一致且没有 HeadlessChrome",
      h["brands"][0]["version"] == "153" and not any("Headless" in b["brand"] for b in h["brands"]))
check("非 Chrome 系的 UA 不伪造客户端提示", ua.client_hints("Mozilla/5.0 Gecko/20100101 Firefox/120.0") is None)
check("旧 Chrome 的 UA 按它自己的版本", ua.client_hints("Mozilla/5.0 (Windows NT 10.0) Chrome/58.0.3029.110 Safari/537.3")["brands"][0]["version"] == "58")

# 4. smoke._get 真的带了统一 UA / 源 UA
seen = []
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        seen.append(self.headers.get("User-Agent"))
        b = b"ok"
        self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b)
srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d/" % srv.server_address[1]
s = requests.Session(); s.trust_env = False
smoke._get(base, s, 5); smoke._get(base, s, 5, "SrcUA/2")
check("smoke._get：默认统一 UA，源指定则用源的", seen == [ua.current(), "SrcUA/2"])

# 5. 出口代理
check("没设 ANIYUAN_PROXY 就是不用代理", (os.environ.pop(network.ENV, None), network.proxy_url())[1] == "")
sess = network.new_session("http://u:p%40w@127.0.0.1:8888")
check("requests 走代理，并且不被环境变量的代理盖过", sess.proxies.get("https") == "http://u:p%40w@127.0.0.1:8888" and sess.trust_env is False)
check("没有代理时 session 保持默认", network.new_session(None).proxies == {})
pw = network.playwright_proxy("http://u:p%40w@127.0.0.1:8888")
check("Playwright 代理：地址和账号密码分开、密码解码", pw == {"server": "http://127.0.0.1:8888", "username": "u", "password": "p@w"})
check("socks5 代理也能解析", network.playwright_proxy("socks5://h.example:1080") == {"server": "socks5://h.example:1080"})
check("描述里不含密码", "p@w" not in network.describe("http://u:p%40w@127.0.0.1:8888") and "p%40w" not in network.describe("http://u:p%40w@127.0.0.1:8888"))

# 6. UA 体检：requests 一路（不用浏览器）
ua.reset()
res = ua.audit(None)
check("体检（只查 requests）通过", all(ok for _, ok, _ in res) and len(res) >= 1)

# 7. UA 体检：带真浏览器
from aniyuan.check.playcheck import PlayChecker
pc = PlayChecker()
try:
    res = ua.audit(pc)
    for n, ok, d in res: print("    ", "通过" if ok else "未通过", n, "|", d[:110])
    check("体检（带真浏览器）：UA、客户端提示、无 HeadlessChrome 全部通过", all(ok for _, ok, _ in res) and len(res) >= 4)
    # 反例：不做客户端提示修正时，体检应该能发现不一致（证明体检不是空转）
    orig = PlayChecker.new_page
    PlayChecker.new_page = lambda self, ctx, u=None: ctx.new_page()
    try:
        res2 = ua.audit(pc)
    finally:
        PlayChecker.new_page = orig
    check("体检能发现客户端提示和 UA 不一致（反例）", any(not ok for _, ok, _ in res2))
finally:
    pc.close()

# 8. 出口代理端到端：本地假代理，requests 和浏览器的请求都应该经过它（Chromium 对 127.0.0.1 不走代理，所以用假域名）
proxied = []
class P(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        proxied.append((self.path, self.headers.get("Proxy-Authorization")))
        b = "<html><body>via proxy</body></html>".encode()
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
psrv = HTTPServer(("127.0.0.1", 0), P); threading.Thread(target=psrv.serve_forever, daemon=True).start()
purl = "http://127.0.0.1:%d" % psrv.server_address[1]
r = network.new_session(purl).get("http://only-reachable-via-proxy.test/a", timeout=5)
check("requests 的请求经过代理", r.status_code == 200 and "via proxy" in r.text and proxied and proxied[-1][0].startswith("http://only-reachable-via-proxy.test/a"))
proxied.clear()
pc = PlayChecker(purl)
try:
    got = pc.fetch("http://only-reachable-via-proxy.test/b")
    check("浏览器的请求经过代理", got[0] == 200 and "via proxy" in got[1] and any("only-reachable-via-proxy.test/b" in p for p, _ in proxied))
finally:
    pc.close()

# 9. 配置了出口代理时，UA 体检用的本机回显服务（127.0.0.1）不能被带去代理（线上曾因此一直「浏览器请求失败」）
proxied.clear()
pc = PlayChecker(purl)
try:
    res = ua.audit(pc)
    check("配置了出口代理时，UA 体检（本机回显）也能通过", res and all(ok for _, ok, _ in res))
    check("本机地址没有被带去代理", not any("127.0.0.1" in p for p, _ in proxied))
finally:
    pc.close()
sys.exit(1 if bad else 0)
