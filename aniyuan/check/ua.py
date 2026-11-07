"""统一 User-Agent：整条检测流程（requests、无头浏览器、图标下载）只用这里的一个 UA。

为什么要统一：
  * 以前 smoke.py 和 playcheck.py 各写了一份 Chrome/120 的字符串。而无头浏览器发请求时，
    Sec-CH-UA 客户端提示写的是真实版本（并且带着 "HeadlessChrome"），于是出现 UA 说 120、
    客户端提示说 153 的自相矛盾 —— 这正是 Cloudflare 一类反爬最容易抓的特征，
    也是海外检测里一批 403（blocked）的可能原因之一。
  * 现在 UA 的大版本号以实际启动的 Chromium 为准（没有浏览器时用 FALLBACK_MAJOR），
    requests 和浏览器用同一个字符串；浏览器的客户端提示（Sec-CH-UA / navigator.userAgentData）
    也一并改成同一个版本，去掉 HeadlessChrome 品牌。
  * 源自己在 searchConfig.userAgent 里写了 UA 的，检测时照它的来（Animeko 就是这么请求的），
    只有没写的才用这里的统一 UA。
  * config.json 的 user_agent 可以整体覆盖。

audit() 是“UA 体检”：起一个本地回显服务，实际发请求，核对 requests 和浏览器发出去的
UA 一致、浏览器客户端提示的版本和 UA 一致、没有 HeadlessChrome。结果写进报告。
"""
import re

# 没有浏览器可参照时用的 Chrome 大版本（只影响没带 --playcheck 的运行；带了会以实际浏览器为准）
FALLBACK_MAJOR = 153
ACCEPT_LANGUAGE = "zh-CN,zh;q=0.9"
_TEMPLATE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/%d.0.0.0 Safari/537.36")
_CHROME_RE = re.compile(r"Chrome/(\d+)")
_state = {"major": FALLBACK_MAJOR, "override": ""}


def reset():
    _state.update(major=FALLBACK_MAJOR, override="")


def chrome_ua(major):
    return _TEMPLATE % int(major)


def parse_major(text):
    """从 UA 字符串或浏览器版本号（153.0.8010.12）里取 Chrome 大版本；取不到返回 None。"""
    m = _CHROME_RE.search(text or "") or re.match(r"^(\d+)\.", text or "")
    return int(m.group(1)) if m else None


def configure(config=None):
    """读取 config.json 里的 user_agent（整体覆盖，留空表示自动）。"""
    _state["override"] = str((config or {}).get("user_agent") or "").strip()


def adopt_browser_version(version):
    """用实际启动的 Chromium 的大版本；已经用 config 整体覆盖了的不动。返回采用的大版本。"""
    major = parse_major(version)
    if major and not _state["override"]:
        _state["major"] = major
    return _state["major"]


def current():
    return _state["override"] or chrome_ua(_state["major"])


def request_headers(ua=None):
    """requests 用的请求头。ua：源自己指定的 UA（searchConfig.userAgent），空就用统一的。"""
    return {"User-Agent": (ua or "").strip() or current(), "Accept-Language": ACCEPT_LANGUAGE}


def client_hints(ua=None):
    """浏览器 CDP 的 userAgentMetadata：让 Sec-CH-UA / navigator.userAgentData 和 UA 字符串同一个版本。
    UA 不是 Chrome 系（比如源指定了 Firefox 的 UA）时返回 None，不伪造客户端提示。"""
    text = (ua or "").strip() or current()
    major = parse_major(text) if "Chrome/" in text else None
    if not major:
        return None
    m = str(major)
    return {
        "brands": [{"brand": "Chromium", "version": m}, {"brand": "Google Chrome", "version": m},
                   {"brand": "Not_A Brand", "version": "24"}],
        "fullVersionList": [{"brand": "Chromium", "version": m + ".0.0.0"},
                            {"brand": "Google Chrome", "version": m + ".0.0.0"},
                            {"brand": "Not_A Brand", "version": "24.0.0.0"}],
        "platform": "Windows" if "Windows" in text else "Linux", "platformVersion": "10.0.0",
        "architecture": "x86", "bitness": "64", "model": "", "mobile": "Mobile" in text, "wow64": False,
    }


def _major_from_sec_ch_ua(value):
    m = re.search(r'"(?:Google Chrome|Chromium|HeadlessChrome)";v="(\d+)"', value or "")
    return int(m.group(1)) if m else None


def audit(pc=None, timeout=5):
    """UA 体检。返回 [(检查项, 是否通过, 说明)]。pc：PlayChecker（没有就只查 requests 这一路）。
    只访问本机的回显服务，不联网。"""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    import requests

    from . import smoke

    seen = {}

    class Echo(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            seen[self.path.split("?")[0]] = {k.lower(): v for k, v in self.headers.items()}
            body = b"<html><body>ok</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", 0), Echo)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    want = current()
    out = []
    try:
        s = requests.Session()
        s.trust_env = False   # 回显服务在本机，不要被环境里的代理带偏
        try:
            smoke._get(base + "/req", s, timeout)
            got = (seen.get("/req") or {}).get("user-agent")
            out.append(("requests 的 UA 与统一 UA 一致", got == want, "发出：%s" % got))
        except Exception as e:
            out.append(("requests 的 UA 与统一 UA 一致", False, "请求失败：%s" % type(e).__name__))
        if pc is None:
            out.append(("浏览器的 UA 与客户端提示一致", True, "没有启用浏览器（--playcheck），跳过"))
            return out
        try:
            pc.fetch(base + "/browser")
            h = seen.get("/browser") or {}
            got_ua, hint = h.get("user-agent"), h.get("sec-ch-ua", "")
            out.append(("浏览器的 UA 与统一 UA 一致", got_ua == want, "发出：%s" % got_ua))
            if client_hints(want):
                hm, um = _major_from_sec_ch_ua(hint), parse_major(want)
                out.append(("浏览器的客户端提示（Sec-CH-UA）版本与 UA 一致", hm == um,
                            "UA 写 Chrome/%s，Sec-CH-UA 写 %s" % (um, hint or "（没有）")))
                out.append(("浏览器没有暴露 HeadlessChrome 品牌", "Headless" not in hint, hint or "（没有）"))
            else:
                out.append(("浏览器的客户端提示", True, "UA 不是 Chrome 系，不改客户端提示"))
        except Exception as e:
            out.append(("浏览器的 UA 与客户端提示一致", False, "浏览器请求失败：%s" % type(e).__name__))
    finally:
        srv.shutdown()
        srv.server_close()
    return out
